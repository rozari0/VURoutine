import re
from contextlib import asynccontextmanager
from enum import Enum
from typing import Optional

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from pydantic import BaseModel, RootModel
from fastapi.concurrency import run_in_threadpool


url = "https://docs.google.com/spreadsheets/d/1Sdmr60rcZeBCa2ofswUr9mxIreIj71W9HYM1RRhvfMM/export?format=csv"


class Semester(str, Enum):
    first = 1
    second = 2
    third = 3
    fourth = 4
    fifth = 5
    sixth = 6
    seventh = 7
    eighth = 8
    ninth = 9


Sections = {
    Semester.first: ["A", "B", "C", "D"],
    Semester.second: ["A", "B", "C", "D", "E", "F"],
    Semester.third: ["A", "B", "C"],
    Semester.fourth: ["A", "B", "C", "D", "E", "F", "G"],
    Semester.fifth: ["A", "B", "C", "D"],
    Semester.sixth: ["A", "B", "C", "D", "E", "F"],
    Semester.seventh: ["A", "B"],
    Semester.eighth: ["A", "B", "C", "D", "E", "F"],
    Semester.ninth: ["A", "B"],
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
    Semester.ninth: 614628609,
}


class ClassInfo(BaseModel):
    teacher_name: str
    course: str
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


def get_routine_data(url):
    df = pd.read_csv(url)
    df["Day / Slot"] = df["Day / Slot"].ffill()
    df = df.rename(columns={df.columns[0]: "Day / Slot"})

    grouped = df.groupby("Day / Slot")
    result = {}
    for day_name, group in grouped:
        day_data = {}

        slot_columns = [col for col in df.columns if col.startswith("Slot")]

        for slot_col in slot_columns:
            slot_values = group[slot_col].dropna().tolist()
            time_key = slot_col.split("\n")[-1].strip()

            for i, val in enumerate(slot_values):
                name = val.splitlines()[0]
                val_splited = val.splitlines()

                # course_match = re.search(r"(CSE \d+)", val)
                course = val_splited[1].split("(")[0].strip()
                section_match = re.search(r"([A-Z])\s*Sec", val)
                room = val_splited[-1].split("Room:")[-1].strip()

                data = {
                    "teacher_name": name,
                    "course": course,
                    "section": section_match.group(1),
                    "room": room,
                }
                slot_values[i] = data

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
    version="1.0.0",
    description="API to get CSE routine for different semesters.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/cse/",
    response_model=WeeklySchedule,
    tags=["CSE Routine"],
    summary="Get CSE Routine",
)
@cache(expire=60)
async def get_routine(semester: Semester) -> WeeklySchedule:
    print("Gid is: ", GIDS[semester])
    url_with_gid = f"{url}&gid={GIDS[semester]}"
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
