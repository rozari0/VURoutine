import json
from collections.abc import Iterable
from os import environ

import ua_generator
from bs4 import BeautifulSoup
from httpx import Client

from auth import authenticate

# client = Client(http2=True, follow_redirects=True)
LOGIN_URL = "http://160.187.25.3:8083/front/student/login"
ROUTINE_URL = (
    "http://160.187.25.3:8083/front/student/routine/load?semester_id=6&section_id=2"
)
VU_ID = environ.get("VU_ID", "")
VU_PASSWORD = environ.get("VU_PASSWORD", "")

if not VU_ID or not VU_PASSWORD:
    raise ValueError("VU_ID and VU_PASSWORD must be set in environment variables.")

client = authenticate(VU_ID, VU_PASSWORD, LOGIN_URL, ROUTINE_URL)

ua = ua_generator.generate(browser=["chrome", "edge"])

with open("data/Teachers.json", "r") as f:
    teachers = json.load(f)


def get_teachers_info(name):
    if "," in name:
        names = [n.strip() for n in name.split(",")]
        teachers_info = []
        for n in names:
            t_info = teachers.get(n, {})
            if t_info:
                teachers_info.append(t_info.get("designation", "Lecturer"))
            else:
                teachers_info.append("Lecturer")
        teachers_info = ", ".join(teachers_info)
    else:
        teachers_info = teachers.get(name, {}).get("designation", "Lecturer")

    return teachers_info


def get_html_response(semester_id: int = 1, section_id: int = 1):
    global client
    headers = ua.headers.get()
    headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
            "Cache-Control": "private, no-store, max-age=0",
        }
    )
    url = f"http://160.187.25.3:8083/front/student/routine/load?semester_id={semester_id}&section_id={section_id}"

    print("Requesting to: ", url)
    response = client.get(url, headers=headers)

    if response.status_code in (301, 302):
        client = authenticate(VU_ID, VU_PASSWORD, LOGIN_URL, ROUTINE_URL)

        response = client.get(url, headers=headers)
    return response.text


def make_soup(html):
    soup = BeautifulSoup(html, "html.parser")
    routine_main = soup.find_all("div", class_="visible-xs-block")[1]
    routine_days = routine_main.find_all("div", class_="routine-day")
    return routine_days


def get_structured_data(days):
    data = {}
    for day in days:
        parsed = parse_routine_days(day)
        data.update(parsed)
    return data


def parse_routine_days(days):
    """
    Parse one or more .routine-day elements.

    Returns:
    {
        "Sunday": {
            "09:00 AM": {
                    "teacher_name": "...",
                    "course": "...",
                    "course_name": "...",
                    "section": "...",
                    "room": "..."
                },
            "10:05 AM": None,
            ...
        },
        ...
    }
    """

    if not isinstance(days, Iterable) or hasattr(days, "select"):
        days = [days]

    result = {}

    for day in days:
        day_name = day.select_one(".routine-day-header").get_text(strip=True)
        schedule = {}

        for slot in day.select(".routine-slot"):
            meta = slot.select_one(".routine-slot-meta").get_text(" ", strip=True)

            # "Slot 1 | 09:00 AM - 10:05 AM"
            time_range = meta.split("|", 1)[1].strip()
            start_time = time_range.split(" - ")[0]
            end_time = time_range.split(" - ")[1]

            # No class
            if slot.select_one(".text-muted"):
                schedule[start_time] = None
                continue

            details = slot.select_one(".routine-item-details")

            info = {}
            for div in details.find_all("div", recursive=False):
                strong = div.find("strong")
                key = strong.get_text(strip=True).rstrip(":").lower()
                value = (
                    div.get_text(" ", strip=True)
                    .replace(strong.get_text(strip=True), "", 1)
                    .strip()
                )
                info[key] = value

            teachers_info = get_teachers_info(info.get("teacher", ""))

            schedule[start_time] = {
                "teacher_name": info.get("teacher"),
                "course": slot.select_one(".course-code-chip").get_text(strip=True),
                "course_name": info.get("course"),
                "section": info.get("class"),  # rename if needed
                "room": info.get("room"),
                "end_time": end_time,
                "designation": teachers_info,
            }

        result[day_name] = schedule

    return result
