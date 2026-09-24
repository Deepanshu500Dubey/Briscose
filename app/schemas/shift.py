"""Request/response schemas for shifts."""
import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator

from app.models.shift import ShiftStatus
from app.models.shift_assignment import AssignmentStatus


class ShiftCreate(BaseModel):
    location_id: uuid.UUID
    date: date
    start_time: time
    end_time: time
    min_staff: int = Field(default=3, ge=1)
    max_staff: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def _check(self) -> "ShiftCreate":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        if self.min_staff > self.max_staff:
            raise ValueError("min_staff must be <= max_staff")
        return self


class AssignedEmployee(BaseModel):
    id: uuid.UUID
    email: str


class ShiftResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    date: date
    start_time: time
    end_time: time
    min_staff: int
    max_staff: int
    status: ShiftStatus
    roster_locked_at: datetime | None
    created_by: uuid.UUID
    created_at: datetime
    # Computed at read time — never stored (project blueprint, Section 7's
    # "reconciling the two status vocabularies" callout).
    accepted_count: int
    offered_count: int
    board_label: str
    # Who's actually on this shift — the roster's per-employee chips (MGR-04)
    # and a shift detail's "coworkers rostered" (EMP-04) both need this;
    # visible to anyone who can see the shift at all.
    accepted_employees: list[AssignedEmployee] = []
    # Populated for an Employee caller only — see app/api/shifts.py's
    # _to_response(). Null for Manager/Admin callers and for an Employee
    # with no assignment on this shift.
    my_assignment_id: uuid.UUID | None = None
    my_assignment_status: AssignmentStatus | None = None


class CandidateResponse(BaseModel):
    employee_id: uuid.UUID
    email: str
    available_start_time: time
    available_end_time: time
    # The moment this employee first submitted availability for this date —
    # what auto-reassignment ordering reads from (Section 10).
    available_since: datetime
