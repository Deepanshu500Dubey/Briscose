"""Shared test helpers.

Accounts are provisioned by a Manager/Admin via POST /users, not
self-registration (see app/api/users.py) — so tests that just need *a*
user to exist create it directly against the DB, exactly like the seed
script does, then log in for real through /auth/login to get tokens.
"""
import uuid
from datetime import date, datetime, time, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.availability import Availability
from app.models.employee_location import EmployeeLocation
from app.models.location import Location
from app.models.manager_location import ManagerLocation
from app.models.shift import Shift, ShiftStatus
from app.models.shift_assignment import AssignmentStatus, ShiftAssignment
from app.models.user import User, UserRole

DEFAULT_PASSWORD = "correct-horse"


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


def create_user(
    db_session: Session,
    *,
    email: str | None = None,
    password: str = DEFAULT_PASSWORD,
    role: UserRole = UserRole.EMPLOYEE,
    home_location_id: uuid.UUID | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        email=email or unique_email(role.value),
        hashed_password=hash_password(password),
        role=role,
        home_location_id=home_location_id,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> dict:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def create_location(
    db_session: Session, name: str | None = None, timezone: str = "Australia/Sydney"
) -> Location:
    location = Location(
        name=name or f"Store {uuid.uuid4().hex}", address="1 Test St", timezone=timezone
    )
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)
    return location


def assign_manager(db_session: Session, manager: User, location: Location) -> None:
    db_session.add(ManagerLocation(manager_id=manager.id, location_id=location.id))
    db_session.commit()


def assign_employee(db_session: Session, employee: User, location: Location) -> None:
    db_session.add(EmployeeLocation(employee_id=employee.id, location_id=location.id))
    db_session.commit()


def set_availability(
    db_session: Session,
    employee: User,
    on: date,
    *,
    is_available: bool = True,
    start_time: time | None = time(8, 0),
    end_time: time | None = time(16, 0),
    created_at: datetime | None = None,
) -> Availability:
    """Direct-to-DB availability write, bypassing PATCH /availability, so
    tests can control `created_at` precisely — needed to test the "first to
    submit" auto-reassignment ordering rule (Section 10)."""
    availability = Availability(
        employee_id=employee.id,
        date=on,
        is_available=is_available,
        start_time=start_time if is_available else None,
        end_time=end_time if is_available else None,
    )
    db_session.add(availability)
    db_session.commit()
    if created_at is not None:
        availability.created_at = created_at
        db_session.commit()
    db_session.refresh(availability)
    return availability


def create_shift(
    db_session: Session,
    location: Location,
    created_by: User,
    *,
    on: date,
    start_time: time = time(8, 0),
    end_time: time = time(16, 0),
    min_staff: int = 1,
    max_staff: int = 2,
) -> Shift:
    shift = Shift(
        location_id=location.id,
        date=on,
        start_time=start_time,
        end_time=end_time,
        min_staff=min_staff,
        max_staff=max_staff,
        status=ShiftStatus.OPEN,
        created_by=created_by.id,
    )
    db_session.add(shift)
    db_session.commit()
    db_session.refresh(shift)
    return shift


def create_accepted_assignment(
    db_session: Session, shift: Shift, employee: User, offered_by: User
) -> ShiftAssignment:
    """Directly seed an ACCEPTED assignment, bypassing the offer/accept
    endpoints, for tests that only care about what happens once a shift is
    already staffed (e.g. clocking in against it)."""
    assignment = ShiftAssignment(
        shift_id=shift.id,
        employee_id=employee.id,
        status=AssignmentStatus.ACCEPTED,
        offered_by=offered_by.id,
        shift_starts_at=datetime.combine(shift.date, shift.start_time),
        shift_ends_at=datetime.combine(shift.date, shift.end_time),
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)
    return assignment


def freeze_time_clock_now(monkeypatch, fixed_now: datetime) -> None:
    """Freeze `datetime.now()` inside app.services.time_clock_service so
    clock-in/out tests are deterministic regardless of wall-clock time —
    `datetime.combine`, `.date()`, etc. still behave normally since this
    only overrides `.now()` on a real datetime subclass."""
    import app.services.time_clock_service as time_clock_service

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now.astimezone(tz) if tz else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(time_clock_service, "datetime", _FrozenDateTime)
