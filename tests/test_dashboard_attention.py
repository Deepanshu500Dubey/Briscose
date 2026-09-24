"""Tests for GET /dashboard/attention.

Covers all three item types:
  * open_or_understaffed   — shift in next 48 h with accepted < min_staff
  * offer_pending_long     — OFFERED assignment older than 24 h
  * rostered_not_clocked_in — employee on an in-progress shift with no open entry

Also checks:
  * empty result when no issues exist
  * location scoping (manager only sees their own locations)
  * employee and non-manager callers are rejected (403 / 401)
"""
from datetime import date, datetime, time, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.shift import Shift, ShiftStatus
from app.models.shift_assignment import AssignmentStatus, ShiftAssignment
from app.models.time_entry import TimeEntry, TimeEntryFlag
from app.models.user import UserRole
from tests.helpers import (
    assign_employee,
    assign_manager,
    auth_headers,
    create_location,
    create_shift,
    create_user,
    login,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> date:
    return datetime.now(timezone.utc).date()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _add_offered_assignment(
    db_session: Session,
    shift: Shift,
    employee,
    offered_by,
    *,
    offered_at: datetime,
) -> ShiftAssignment:
    """Seed an OFFERED assignment with a controlled offered_at timestamp."""
    assignment = ShiftAssignment(
        shift_id=shift.id,
        employee_id=employee.id,
        status=AssignmentStatus.OFFERED,
        offered_by=offered_by.id,
        offered_at=offered_at,
        shift_starts_at=datetime.combine(shift.date, shift.start_time),
        shift_ends_at=datetime.combine(shift.date, shift.end_time),
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)
    return assignment


def _add_accepted_assignment(
    db_session: Session,
    shift: Shift,
    employee,
    offered_by,
) -> ShiftAssignment:
    from tests.helpers import create_accepted_assignment
    return create_accepted_assignment(db_session, shift, employee, offered_by)


def _add_open_time_entry(
    db_session: Session,
    employee,
    location,
    *,
    clock_in: datetime,
) -> TimeEntry:
    entry = TimeEntry(
        employee_id=employee.id,
        shift_id=None,
        clock_in=clock_in,
        clock_out=None,
        location_id=location.id,
        flag=TimeEntryFlag.NONE,
    )
    db_session.add(entry)
    db_session.commit()
    return entry


def _attention(client: TestClient, tokens: dict):
    return client.get("/dashboard/attention", headers=auth_headers(tokens))


# ---------------------------------------------------------------------------
# Auth / role guard
# ---------------------------------------------------------------------------

def test_attention_requires_auth(client: TestClient) -> None:
    resp = client.get("/dashboard/attention")
    assert resp.status_code == 401


def test_attention_rejects_employee(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)
    resp = _attention(client, tokens)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Empty result when nothing needs attention
# ---------------------------------------------------------------------------

def test_attention_empty_when_all_good(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    # Fully-staffed confirmed shift tomorrow
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    tomorrow = _today() + timedelta(days=1)
    shift = create_shift(
        db_session, location, manager, on=tomorrow, min_staff=1, max_staff=1
    )
    _add_accepted_assignment(db_session, shift, employee, manager)
    # Update shift status to confirmed so it doesn't surface as open
    shift.status = ShiftStatus.CONFIRMED
    db_session.commit()

    tokens = login(client, manager.email)
    resp = _attention(client, tokens)
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# open_or_understaffed
# ---------------------------------------------------------------------------

def test_open_shift_appears_as_understaffed(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    # Open shift (no assignments) within next 48 h
    shift = create_shift(
        db_session, location, manager,
        on=_today() + timedelta(days=1),
        min_staff=2, max_staff=3,
    )

    tokens = login(client, manager.email)
    resp = _attention(client, tokens)

    assert resp.status_code == 200
    items = resp.json()
    understaffed = [i for i in items if i["type"] == "open_or_understaffed"]
    assert len(understaffed) == 1
    item = understaffed[0]
    assert item["shift_id"] == str(shift.id)
    assert item["location_id"] == str(location.id)
    assert item["accepted_count"] == 0
    assert item["min_staff"] == 2
    assert "needs 2 more staff" in item["label"]


def test_partially_staffed_shift_appears(
    client: TestClient, db_session: Session
) -> None:
    """confirmed shift with accepted < min_staff must still appear."""
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    shift = create_shift(
        db_session, location, manager,
        on=_today() + timedelta(days=1),
        min_staff=3, max_staff=5,
    )
    # Only 1 accepted out of min_staff=3
    _add_accepted_assignment(db_session, shift, employee, manager)
    shift.status = ShiftStatus.PENDING_ACCEPTANCE
    db_session.commit()

    tokens = login(client, manager.email)
    resp = _attention(client, tokens)

    items = resp.json()
    understaffed = [i for i in items if i["type"] == "open_or_understaffed"]
    assert any(i["shift_id"] == str(shift.id) for i in understaffed)
    match = next(i for i in understaffed if i["shift_id"] == str(shift.id))
    assert match["accepted_count"] == 1
    assert match["min_staff"] == 3


def test_shift_beyond_48h_not_returned(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    # 3 days out — outside the 48 h window
    create_shift(
        db_session, location, manager,
        on=_today() + timedelta(days=3),
        min_staff=1, max_staff=1,
    )

    tokens = login(client, manager.email)
    resp = _attention(client, tokens)

    understaffed = [i for i in resp.json() if i["type"] == "open_or_understaffed"]
    assert understaffed == []


def test_cancelled_shift_not_returned(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(
        db_session, location, manager,
        on=_today() + timedelta(days=1),
        min_staff=1, max_staff=1,
    )
    shift.status = ShiftStatus.CANCELLED
    db_session.commit()

    tokens = login(client, manager.email)
    resp = _attention(client, tokens)

    understaffed = [i for i in resp.json() if i["type"] == "open_or_understaffed"]
    assert understaffed == []


# ---------------------------------------------------------------------------
# offer_pending_long
# ---------------------------------------------------------------------------

def test_stale_offer_appears(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    shift = create_shift(
        db_session, location, manager,
        on=_today() + timedelta(days=1),
        min_staff=1, max_staff=1,
    )
    stale_time = _now_utc() - timedelta(hours=25)
    assignment = _add_offered_assignment(
        db_session, shift, employee, manager, offered_at=stale_time
    )

    tokens = login(client, manager.email)
    resp = _attention(client, tokens)

    items = resp.json()
    stale = [i for i in items if i["type"] == "offer_pending_long"]
    assert len(stale) == 1
    assert stale[0]["assignment_id"] == str(assignment.id)
    assert stale[0]["employee_id"] == str(employee.id)
    assert stale[0]["hours_pending"] >= 25.0


def test_fresh_offer_not_returned(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    shift = create_shift(
        db_session, location, manager,
        on=_today() + timedelta(days=1),
        min_staff=1, max_staff=1,
    )
    # Only 1 h old — well within the 24 h window
    _add_offered_assignment(
        db_session, shift, employee, manager,
        offered_at=_now_utc() - timedelta(hours=1),
    )

    tokens = login(client, manager.email)
    resp = _attention(client, tokens)

    stale = [i for i in resp.json() if i["type"] == "offer_pending_long"]
    assert stale == []


# ---------------------------------------------------------------------------
# rostered_not_clocked_in
# ---------------------------------------------------------------------------

def test_rostered_employee_without_clock_in_appears(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)

    # Shift that spans right now (00:00 – 23:59 today)
    today = _today()
    shift = create_shift(
        db_session, location, manager, on=today,
        start_time=time(0, 0), end_time=time(23, 59),
        min_staff=1, max_staff=1,
    )
    _add_accepted_assignment(db_session, shift, employee, manager)
    # No time entry → employee hasn't clocked in

    tokens = login(client, manager.email)
    resp = _attention(client, tokens)

    absent = [i for i in resp.json() if i["type"] == "rostered_not_clocked_in"]
    assert len(absent) == 1
    assert absent[0]["employee_id"] == str(employee.id)
    assert absent[0]["shift_id"] == str(shift.id)


def test_rostered_employee_who_is_clocked_in_not_returned(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)

    today = _today()
    shift = create_shift(
        db_session, location, manager, on=today,
        start_time=time(0, 0), end_time=time(23, 59),
        min_staff=1, max_staff=1,
    )
    _add_accepted_assignment(db_session, shift, employee, manager)
    _add_open_time_entry(db_session, employee, location, clock_in=_now_utc())

    tokens = login(client, manager.email)
    resp = _attention(client, tokens)

    absent = [i for i in resp.json() if i["type"] == "rostered_not_clocked_in"]
    assert absent == []


# ---------------------------------------------------------------------------
# Location scoping
# ---------------------------------------------------------------------------

def test_manager_does_not_see_other_locations(
    client: TestClient, db_session: Session
) -> None:
    """A manager scoped to location A must not see items for location B."""
    loc_a = create_location(db_session)
    loc_b = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, loc_a)  # scoped to A only

    other_manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, other_manager, loc_b)

    # Open shift at location B — should NOT appear for manager of A
    create_shift(
        db_session, loc_b, other_manager,
        on=_today() + timedelta(days=1),
        min_staff=1, max_staff=1,
    )

    tokens = login(client, manager.email)
    resp = _attention(client, tokens)

    assert resp.status_code == 200
    assert resp.json() == []


def test_admin_sees_all_locations(
    client: TestClient, db_session: Session
) -> None:
    loc_a = create_location(db_session)
    loc_b = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, loc_a)
    assign_manager(db_session, manager, loc_b)
    admin = create_user(db_session, role=UserRole.ADMIN)

    create_shift(
        db_session, loc_a, manager,
        on=_today() + timedelta(days=1),
        min_staff=1, max_staff=1,
    )
    create_shift(
        db_session, loc_b, manager,
        on=_today() + timedelta(days=1),
        min_staff=1, max_staff=1,
    )

    tokens = login(client, admin.email)
    resp = _attention(client, tokens)

    assert resp.status_code == 200
    understaffed = [i for i in resp.json() if i["type"] == "open_or_understaffed"]
    location_ids = {i["location_id"] for i in understaffed}
    assert str(loc_a.id) in location_ids
    assert str(loc_b.id) in location_ids
