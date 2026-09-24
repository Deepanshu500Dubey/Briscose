"""Request/response schemas for time entries."""
import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict

from app.models.time_entry import TimeEntryFlag


class ClockInRequest(BaseModel):
    # Only needed to disambiguate the rare case of two accepted shifts on
    # the same day with a gap between them (Section 10) — omit otherwise.
    shift_id: uuid.UUID | None = None


class TimeEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    shift_id: uuid.UUID | None
    clock_in: datetime
    clock_out: datetime | None
    location_id: uuid.UUID
    flag: TimeEntryFlag


class ShiftChoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date: date
    start_time: time
    end_time: time
    location_id: uuid.UUID


class ForceCloseRequest(BaseModel):
    clock_out: datetime
