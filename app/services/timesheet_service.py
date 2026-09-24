"""Timesheet rollup logic (project blueprint, Section 10).

Hours are always computed server-side from clock_out - clock_in, never
trusted from the client. A day's total sums every closed entry for that
employee on that date regardless of `flag` — an unscheduled or early/late
entry still counts as worked time, it's just marked for review. An entry
with no clock_out is "in progress" and excluded from totals.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.time_entry import TimeEntry

DAILY_OVERTIME_HOURS = 8
WEEKLY_OVERTIME_HOURS = 40


def _tz(name: str | None) -> ZoneInfo:
    return ZoneInfo(name) if name else ZoneInfo("UTC")


def build_timesheet(db: Session, employee_id: uuid.UUID, week_start: date, week_end: date) -> dict:
    # Broad UTC bound first (padded a day either side to absorb timezone
    # shifts), then bucket precisely by each entry's own location-local
    # date in Python — a shift crossing midnight attributes correctly
    # either way (Section 10).
    lower = datetime.combine(week_start - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    upper = datetime.combine(week_end + timedelta(days=1), datetime.max.time(), tzinfo=timezone.utc)

    entries = list(
        db.scalars(
            select(TimeEntry).where(
                TimeEntry.employee_id == employee_id,
                TimeEntry.clock_in >= lower,
                TimeEntry.clock_in <= upper,
            )
        ).all()
    )

    location_tz_cache: dict[uuid.UUID, ZoneInfo] = {}

    def tz_for(location_id: uuid.UUID) -> ZoneInfo:
        if location_id not in location_tz_cache:
            location = db.get(Location, location_id)
            location_tz_cache[location_id] = _tz(location.timezone if location else None)
        return location_tz_cache[location_id]

    entries_by_day: dict[date, list[TimeEntry]] = {}
    for entry in entries:
        local_date = entry.clock_in.astimezone(tz_for(entry.location_id)).date()
        if week_start <= local_date <= week_end:
            entries_by_day.setdefault(local_date, []).append(entry)

    days = []
    weekly_total = 0.0
    current = week_start
    while current <= week_end:
        day_entries = sorted(entries_by_day.get(current, []), key=lambda e: e.clock_in)
        day_total = sum(
            (e.clock_out - e.clock_in).total_seconds() / 3600
            for e in day_entries
            if e.clock_out is not None
        )
        weekly_total += day_total
        days.append(
            {
                "date": current,
                "entries": day_entries,
                "total_hours": round(day_total, 2),
                "over_daily_limit": day_total > DAILY_OVERTIME_HOURS,
            }
        )
        current += timedelta(days=1)

    return {
        "employee_id": employee_id,
        "week_start": week_start,
        "week_end": week_end,
        "days": days,
        "weekly_total_hours": round(weekly_total, 2),
        "over_weekly_limit": weekly_total > WEEKLY_OVERTIME_HOURS,
    }
