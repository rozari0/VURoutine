from enum import Enum
from typing import Optional

import pandas as pd
from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from pydantic import BaseModel, RootModel

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
    nighth = 9


GIDS = {
    Semester.first: 0,
    Semester.second: 1739684797,
    Semester.third: 1812971555,
    Semester.fourth: 1642366900,
    Semester.fifth: 1698922910,
    Semester.sixth: 1687685897,
    Semester.seventh: 2130237812,
    Semester.eighth: 1780568258,
    Semester.nighth: 614628609,
}

TimeSlot = Optional[list[str]]


class DaySchedule(RootModel[dict[str, TimeSlot]]):
    pass


class WeeklySchedule(BaseModel):
    Monday: DaySchedule
    Tuesday: DaySchedule
    Wednesday: DaySchedule
    Thursday: DaySchedule
    Sunday: DaySchedule


def get_routine_data(url):
    df = pd.read_csv(url)
    df["Day / Slot"].fillna(method="ffill", inplace=True)
    df.rename(columns={df.columns[0]: "Day / Slot"}, inplace=True)
    grouped = df.groupby("Day / Slot")
    result = {}
    for day_name, group in grouped:
        day_data = {}

        slot_columns = [col for col in df.columns if col.startswith("Slot")]

        for slot_col in slot_columns:
            slot_values = group[slot_col].dropna().tolist()
            time_key = slot_col.split("\n")[-1].strip()

            if len(slot_values) > 1:
                day_data[time_key] = slot_values
            elif len(slot_values) == 1:
                day_data[time_key] = slot_values
            else:
                day_data[time_key] = None

            result[day_name] = day_data

    return result


app = FastAPI()


@app.on_event("startup")
def startup():
    FastAPICache.init(InMemoryBackend())


@app.get("/")
@cache(expire=60)
def get_routine(semester: Semester) -> WeeklySchedule:
    print("Gid is: ", GIDS[semester])
    url_with_gid = f"{url}&gid={GIDS[semester]}"
    routine_data = get_routine_data(url_with_gid)
    return routine_data
