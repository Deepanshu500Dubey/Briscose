"""Request/response schemas for timesheets."""
import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.time_entry import TimeEntryResponse


class TimesheetDayResponse(BaseModel):
    date: date
    entries: list[TimeEntryResponse]
    total_hours: float
    over_daily_limit: bool


class TimesheetResponse(BaseModel):
    employee_id: uuid.UUID
    week_start: date
    week_end: date
    days: list[TimesheetDayResponse]
    weekly_total_hours: float
    over_weekly_limit: bool
