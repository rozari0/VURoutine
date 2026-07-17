import json
import logging
import re
from contextlib import asynccontextmanager
from enum import Enum
from typing import Optional

import pandas as pd
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from pydantic import BaseModel, RootModel

logger = logging.getLogger(__name__)

URL = "https://docs.google.com/spreadsheets/d/1Sdmr60rcZeBCa2ofswUr9mxIreIj71W9HYM1RRhvfMM/export?format=csv"


class Semester(str, Enum):
    first = 1
    second = 2
    third = 3
    fourth = 4
    fifth = 5
    sixth = 6
    seventh = 7
    eighth = 8


Sections = {
    Semester.first: ["A", "B", "C", "D", "E", "F"],
    Semester.second: ["A", "B", "C", "D"],
    Semester.third: ["A", "B", "C", "D", "E", "F"],
    Semester.fourth: ["A", "B", "C"],
    Semester.fifth: ["A", "B", "C", "D", "E", "F", "G"],
    Semester.sixth: ["A", "B", "C", "D"],
    Semester.seventh: ["A", "B", "C", "D", "E", "F"],
    Semester.eighth: ["A", "B"],
}

GIDS = {
    Semester.first: 0,
    Semester.second: 1739684797,
    Semester.third: 1812971555,
    Semester.fourth: 1642366900,
    Semester.fifth: 1698922910,
    Semester.sixth: 1687685897,
    Semester.seventh: 2130237812,
    Semester.eighth: 1780568258,
}


class ClassInfo(BaseModel):
    teacher_name: str
    designation: Optional[str] = None
    course: str
    course_name: Optional[str] = None
    section: str
    room: str


TimeSlot = Optional[list[ClassInfo]]


class DaySchedule(RootModel[dict[str, TimeSlot]]):
    pass


class WeeklySchedule(BaseModel):
    Sunday: DaySchedule
    Monday: DaySchedule
    Tuesday: DaySchedule
    Wednesday: DaySchedule
    Thursday: DaySchedule


def course_code_to_name(course_code: str) -> str:
    with open("data/courses.json", "r") as f:
        courses = json.load(f)
    return courses.get(course_code, {}).get("title", "")


with open("data/Teachers.json", "r") as f:
    teachers = json.load(f)


def get_teacher_info(teacher_name: str) -> dict[str, str]:
    teacher = teachers.get(teacher_name)
    return teacher if teacher else {}


def get_routine_data(url: str) -> dict[str, dict[str, list[dict[str, str]] | None]]:
    df = pd.read_csv(url)
    df["Day / Slot"] = df["Day / Slot"].ffill()
    df = df.rename(columns={df.columns[0]: "Day / Slot"})

    grouped = df.groupby("Day / Slot")
    result: dict[str, dict[str, list[dict[str, str]] | None]] = {}
    for day_name, group in grouped:
        day_data: dict[str, list[dict[str, str]] | None] = {}

        slot_columns = sorted(
            [col for col in df.columns if col.startswith("Slot")],
            key=lambda c: int(c.split("Slot")[1].split("\n")[0]),
        )

        for slot_col in slot_columns:
            slot_values = group[slot_col].dropna().tolist()
            time_key = slot_col.split("\n")[-1].strip()

            for i, val in enumerate(slot_values):
                lines = val.splitlines()
                name = lines[0]

                course_line = lines[1] if len(lines) > 1 else ""
                course = (
                    course_line.split("(")[0].strip()
                    if "(" in course_line
                    else course_line.strip()
                )

                section_match = re.search(r"([A-Z])\s*Sec", val)
                section = section_match.group(1) if section_match else ""

                room_line = lines[-1]
                room = (
                    room_line.split("Room:")[-1].strip()
                    if "Room:" in room_line
                    else room_line.strip()
                )

                if "," in name:
                    names = [n.strip() for n in name.split(",")]
                    teachers_info = []
                    for n in names:
                        info = get_teacher_info(n)
                        if info:
                            teachers_info.append(info.get("designation", "Lecturer"))
                        else:
                            teachers_info.append("Lecturer")
                    teachers_info = ", ".join(teachers_info)
                else:
                    teachers_info = get_teacher_info(name).get(
                        "designation", "Lecturer"
                    )

                data = {
                    "teacher_name": name,
                    "designation": teachers_info if teachers_info else None,
                    "course": course,
                    "course_name": course_code_to_name(course),
                    "section": section,
                    "room": room,
                }
                slot_values[i] = ClassInfo(**data)

            if len(slot_values):
                day_data[time_key] = slot_values
            else:
                day_data[time_key] = None

            result[day_name] = day_data

    return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    FastAPICache.init(InMemoryBackend())
    yield


app = FastAPI(
    title="CSE Routine API",
    version="2.0.0",
    description="API to get CSE routine for different semesters.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")


@app.get(
    "/cse/",
    response_model=WeeklySchedule,
    tags=["CSE Routine"],
    summary="Get CSE Routine",
)
@cache(expire=60)
async def get_routine(semester: Semester) -> WeeklySchedule:
    logger.info("Gid is: %s", GIDS[semester])
    url_with_gid = f"{URL}&gid={GIDS[semester]}"
    routine_data = await run_in_threadpool(get_routine_data, url_with_gid)
    return routine_data


@app.get(
    "/cse/sections/",
    response_model=dict[int, list[str]],
    tags=["CSE Routine"],
    summary="Get Sections for a Semester",
)
async def get_sections(semester: Semester | None = None):
    if semester:
        return {
            semester: Sections.get(semester, []),
        }

    return Sections


@app.get(
    "/cse/teachers/",
    tags=["CSE Routine"],
    summary="Get CSE Info",
)
async def get_info():
    return teachers


@app.get(
    "/health/",
    tags=["Health Check"],
)
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
