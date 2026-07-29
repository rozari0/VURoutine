import json
import logging
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from pydantic import BaseModel, RootModel

from scrape import get_html_response, get_structured_data, make_soup

logger = logging.getLogger(__name__)


Sections = {
    1: ["A", "B", "C", "D", "E", "F"],
    2: ["A", "B", "C", "D"],
    3: ["A", "B", "C", "D", "E", "F"],
    4: ["A", "B", "C"],
    5: ["A", "B", "C", "D", "E", "F", "G"],
    6: ["A", "B", "C", "D"],
    7: ["A", "B", "C", "D", "E", "F"],
    8: ["A", "B"],
}


class ClassInfo(BaseModel):
    teacher_name: str | None = None
    designation: str | None = None
    course: str
    course_name: str | None = None
    section: str | None = None
    room: str | None = None
    end_time: str | None = None


class ErrorResponse(BaseModel):
    error: str


TimeSlot = Optional[ClassInfo]


class DaySchedule(RootModel[dict[str, TimeSlot]]):
    pass


class WeeklySchedule(BaseModel):
    Sunday: DaySchedule
    Monday: DaySchedule
    Tuesday: DaySchedule
    Wednesday: DaySchedule
    Thursday: DaySchedule


Semester = Literal["1", "2", "3", "4", "5", "6", "7", "8"]

with open("data/Teachers.json", "r") as f:
    teachers = json.load(f)


def get_teacher_info(teacher_name: str) -> dict[str, str]:
    teacher = teachers.get(teacher_name)
    return teacher if teacher else {}


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
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Bad Request",
        }
    },
    tags=["CSE Routine"],
    summary="Get CSE Routine",
)
@cache(expire=60 * 10)
async def get_routine(
    semester: Semester = "6",
    section: Literal["A", "B", "C", "D", "E", "F", "G", "H"] = "B",
):
    sem = int(semester)

    print(Sections.get(sem, []))

    if section not in Sections.get(sem, []):
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Section {section} is not available for semester {semester}"
            },
        )

    if sem < 1 or sem > 8:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Semester {semester} is not valid. It should be between 1 and 8."
            },
        )

    sec: int = ord(section) - 64

    html = await run_in_threadpool(get_html_response, sem, sec)
    days = await run_in_threadpool(make_soup, html)
    data = await run_in_threadpool(get_structured_data, days)

    return data


@app.get(
    "/cse/sections/",
    response_model=dict[int, list[str]],
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Bad Request",
        }
    },
    tags=["CSE Routine"],
    summary="Get Sections for a Semester",
)
async def get_sections(semester: Semester | None = None):
    if semester:
        if int(semester) < 1 or int(semester) > 8:
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"Semester {semester} is not valid. It should be between 1 and 8."
                },
            )

        return {
            semester: Sections.get(int(semester), []),
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
