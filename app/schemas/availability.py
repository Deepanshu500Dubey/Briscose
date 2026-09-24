"""Request/response schemas for availability."""
import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class AvailabilityDayInput(BaseModel):
    date: date
    is_available: bool
    start_time: time | None = None
    end_time: time | None = None

    @model_validator(mode="after")
    def _check_times(self) -> "AvailabilityDayInput":
        if self.is_available:
            if self.start_time is None or self.end_time is None:
                raise ValueError(
                    "start_time and end_time are required when is_available is true"
                )
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be before end_time")
        else:
            # A "not available" day carries no meaningful time range.
            self.start_time = None
            self.end_time = None
        return self


class AvailabilityUpsertRequest(BaseModel):
    days: list[AvailabilityDayInput]

    @field_validator("days")
    @classmethod
    def _no_duplicate_dates(cls, days: list[AvailabilityDayInput]) -> list[AvailabilityDayInput]:
        seen: set[date] = set()
        for day in days:
            if day.date in seen:
                raise ValueError(f"duplicate date in request: {day.date.isoformat()}")
            seen.add(day.date)
        return days


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    date: date
    is_available: bool
    start_time: time | None
    end_time: time | None
    created_at: datetime
    updated_at: datetime
