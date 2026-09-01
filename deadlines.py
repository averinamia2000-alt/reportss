from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select

from config import settings
from db import Session, Report
from projects import PROJECTS

TZ = ZoneInfo(settings.timezone)


def weekly_period(report_type: str, now: datetime | None = None) -> tuple[date, date]:
    """Return the report period expected at the current/most recent deadline.

    Operational: previous Monday-Sunday, due Tuesday 20:00.
    Global: Friday-Thursday immediately before the Friday deadline.
    """
    now = (now or datetime.now(TZ)).astimezone(TZ)
    d = now.date()
    if report_type == "operational":
        # Most recent Tuesday (or today when Tuesday).
        days_since_tue = (d.weekday() - 1) % 7
        due_day = d - timedelta(days=days_since_tue)
        end = due_day - timedelta(days=2)       # Sunday
        start = end - timedelta(days=6)         # Monday
        return start, end
    if report_type == "global":
        # Most recent Friday (or today when Friday).
        days_since_fri = (d.weekday() - 4) % 7
        due_day = d - timedelta(days=days_since_fri)
        end = due_day - timedelta(days=1)       # Thursday
        start = end - timedelta(days=6)         # Friday
        return start, end
    raise ValueError(report_type)


def monthly_period(now: datetime | None = None) -> tuple[date, date]:
    now = (now or datetime.now(TZ)).astimezone(TZ)
    first_this = now.date().replace(day=1)
    end = first_this - timedelta(days=1)
    start = end.replace(day=1)
    return start, end


def deadline_for(report_type: str, period_start: date, period_end: date) -> datetime:
    if report_type == "operational":
        due_date = period_end + timedelta(days=2)  # Tuesday after Sunday
        return datetime.combine(due_date, time(20, 0), TZ)
    if report_type == "global":
        due_date = period_end + timedelta(days=1)  # Friday after Thursday
        return datetime.combine(due_date, time(20, 0), TZ)
    if report_type == "monthly":
        if period_end.month == 12:
            y, m = period_end.year + 1, 1
        else:
            y, m = period_end.year, period_end.month + 1
        return datetime(y, m, 4, 12, 0, tzinfo=TZ)
    raise ValueError(report_type)


async def missing_projects(report_type: str, period_start: date, period_end: date) -> list[dict]:
    async with Session() as s:
        rows = (await s.execute(
            select(Report.project).where(
                Report.report_type == report_type,
                Report.period_start == period_start,
                Report.period_end == period_end,
            )
        )).scalars().all()
    received = set(rows)
    return [p for p in PROJECTS if p["name"] not in received]


def fmt_period(start: date, end: date) -> str:
    if start.year == end.year:
        return f"{start:%d.%m}–{end:%d.%m.%Y}"
    return f"{start:%d.%m.%Y}–{end:%d.%m.%Y}"
