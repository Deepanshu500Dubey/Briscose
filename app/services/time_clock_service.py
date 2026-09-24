"""Clock in/out business logic (project blueprint, Section 10 & 11).

Implements the six explicit cases from Section 10's table: before-shift,
after-shift, no confirmed shift, multiple shifts in a day, clock-out, and
an already-open entry.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.location import Location
from app.models.shift import Shift
from app.models.shift_assignment import AssignmentStatus, ShiftAssignment
from app.models.time_entry import TimeEntry, TimeEntryFlag
from app.models.user import User

GRACE = timedelta(minutes=settings.CLOCK_GRACE_MINUTES)


def _tz(name: str | None) -> ZoneInfo:
    return ZoneInfo(name) if name else ZoneInfo("UTC")


def local_today(db: Session, employee: User) -> date:
    """"Today" in the employee's home location's timezone, falling back to
    UTC if they have none set."""
    tz_name = None
    if employee.home_location_id:
        location = db.get(Location, employee.home_location_id)
        tz_name = location.timezone if location else None
    return datetime.now(_tz(tz_name)).date()


def get_open_time_entry_for_update(db: Session, employee_id: uuid.UUID) -> TimeEntry | None:
    return db.execute(
        select(TimeEntry)
        .where(TimeEntry.employee_id == employee_id, TimeEntry.clock_out.is_(None))
        .with_for_update()
    ).scalar_one_or_none()


def accepted_shifts_for_employee_on(db: Session, employee_id: uuid.UUID, on: date) -> list[Shift]:
    stmt = (
        select(Shift)
        .join(ShiftAssignment, ShiftAssignment.shift_id == Shift.id)
        .where(
            ShiftAssignment.employee_id == employee_id,
            ShiftAssignment.status == AssignmentStatus.ACCEPTED,
            Shift.date == on,
        )
    )
    return list(db.scalars(stmt).all())


def _shift_window(db: Session, shift: Shift) -> tuple[datetime, datetime]:
    location = db.get(Location, shift.location_id)
    tz = _tz(location.timezone if location else None)
    start = datetime.combine(shift.date, shift.start_time, tzinfo=tz)
    end = datetime.combine(shift.date, shift.end_time, tzinfo=tz)
    return start, end


def clock_in(
    db: Session, employee: User, requested_shift_id: uuid.UUID | None
) -> tuple[int, TimeEntry | dict]:
    """Returns (http_status_code, TimeEntry | {"choose_shift": [Shift, ...]})."""
    open_entry = get_open_time_entry_for_update(db, employee.id)
    if open_entry is not None:
        return status.HTTP_409_CONFLICT, open_entry  # soft-success — client syncs UI

    today = local_today(db, employee)
    candidates = accepted_shifts_for_employee_on(db, employee.id, today)
    now = datetime.now(timezone.utc)

    if requested_shift_id is not None:
        shift = next((s for s in candidates if s.id == requested_shift_id), None)
        if shift is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not one of your accepted shifts today",
            )
    else:
        in_window = [
            candidate
            for candidate in candidates
            if (lambda w: w[0] - GRACE <= now <= w[1] + GRACE)(_shift_window(db, candidate))
        ]
        if len(in_window) > 1:
            # Unreachable in practice: the overlap-prevention exclusion
            # constraint (Section 11) guarantees an employee's accepted
            # shifts on one day never overlap in time.
            raise AssertionError("unreachable: overlapping accepted shifts")
        elif len(in_window) == 1:
            shift = in_window[0]
        elif candidates:
            return status.HTTP_409_CONFLICT, {"choose_shift": candidates}
        else:
            shift = None

    if shift is None:
        if employee.home_location_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No accepted shift today and no home location set — cannot clock in",
            )
        flag, location_id = TimeEntryFlag.UNSCHEDULED, employee.home_location_id
    else:
        start, end = _shift_window(db, shift)
        if now < start - GRACE:
            flag, location_id = TimeEntryFlag.EARLY_START, shift.location_id
        elif now > end + GRACE:
            flag, location_id = TimeEntryFlag.AFTER_SHIFT_END, shift.location_id
        else:
            flag, location_id = TimeEntryFlag.NONE, shift.location_id

    entry = TimeEntry(
        employee_id=employee.id,
        shift_id=shift.id if shift else None,
        clock_in=now,
        location_id=location_id,
        flag=flag,
    )
    db.add(entry)
    db.flush()
    return status.HTTP_201_CREATED, entry


def clock_out(db: Session, employee: User) -> TimeEntry:
    entry = get_open_time_entry_for_update(db, employee.id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Not currently clocked in"
        )
    entry.clock_out = datetime.now(timezone.utc)
    db.flush()
    return entry


def force_close(db: Session, entry: TimeEntry, clock_out_at: datetime) -> TimeEntry:
    """Manager-only correction for a forgotten clock-out (Section 10) — the
    one case in this app where a manager writes another person's time data
    directly."""
    if entry.clock_out is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This entry is already closed"
        )
    if clock_out_at.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="clock_out must include a timezone"
        )
    if clock_out_at <= entry.clock_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="clock_out must be after clock_in"
        )
    entry.clock_out = clock_out_at
    db.flush()
    return entry
