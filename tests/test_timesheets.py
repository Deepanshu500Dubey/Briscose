"""Tests for GET /timesheets (project blueprint, Section 8 & 10)."""
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.time_entry import TimeEntry, TimeEntryFlag
from app.models.user import UserRole
from tests.helpers import assign_employee, assign_manager, auth_headers, create_location, create_user, login


def _week_monday(d: date) -> date:
    return d - timedelta(days=d.isoweekday() - 1)


def _add_closed_entry(db_session: Session, employee, location, clock_in: datetime, hours: float) -> TimeEntry:
    entry = TimeEntry(
        employee_id=employee.id,
        shift_id=None,
        clock_in=clock_in,
        clock_out=clock_in + timedelta(hours=hours),
        location_id=location.id,
        flag=TimeEntryFlag.NONE,
    )
    db_session.add(entry)
    db_session.commit()
    return entry


def test_self_timesheet_sums_hours_per_day_and_week(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session, timezone="UTC")
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    monday = _week_monday(datetime.now(timezone.utc).date())
    monday_dt = datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)

    _add_closed_entry(db_session, employee, location, monday_dt, 8)
    _add_closed_entry(db_session, employee, location, monday_dt + timedelta(days=1), 6)

    tokens = login(client, employee.email)
    response = client.get(f"/timesheets?week={monday.isoformat()}", headers=auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["week_start"] == monday.isoformat()
    assert body["weekly_total_hours"] == 14
    assert body["days"][0]["total_hours"] == 8
    assert body["days"][0]["over_daily_limit"] is False
    assert body["over_weekly_limit"] is False


def test_timesheet_flags_over_daily_and_weekly_limits(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session, timezone="UTC")
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    monday = _week_monday(datetime.now(timezone.utc).date())
    monday_dt = datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=6)

    for i in range(6):
        _add_closed_entry(db_session, employee, location, monday_dt + timedelta(days=i), 9)

    tokens = login(client, employee.email)
    response = client.get(f"/timesheets?week={monday.isoformat()}", headers=auth_headers(tokens))

    body = response.json()
    assert body["weekly_total_hours"] == 54
    assert body["over_weekly_limit"] is True
    assert body["days"][0]["over_daily_limit"] is True


def test_open_entry_excluded_from_totals(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session, timezone="UTC")
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    entry = TimeEntry(
        employee_id=employee.id,
        shift_id=None,
        clock_in=datetime.now(timezone.utc),
        clock_out=None,
        location_id=location.id,
        flag=TimeEntryFlag.NONE,
    )
    db_session.add(entry)
    db_session.commit()

    tokens = login(client, employee.email)
    response = client.get("/timesheets", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert response.json()["weekly_total_hours"] == 0


def test_employee_cannot_view_others_timesheet(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    other = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.get(f"/timesheets?employee_id={other.id}", headers=auth_headers(tokens))

    assert response.status_code == 403


def test_manager_can_view_shared_location_employee_timesheet(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session, timezone="UTC")
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)

    tokens = login(client, manager.email)
    response = client.get(f"/timesheets?employee_id={employee.id}", headers=auth_headers(tokens))

    assert response.status_code == 200


def test_manager_without_shared_location_forbidden(
    client: TestClient, db_session: Session
) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, manager.email)

    response = client.get(f"/timesheets?employee_id={employee.id}", headers=auth_headers(tokens))

    assert response.status_code == 403


def test_admin_can_view_any_timesheet(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, admin.email)

    response = client.get(f"/timesheets?employee_id={employee.id}", headers=auth_headers(tokens))

    assert response.status_code == 200


def test_timesheet_requires_authentication(client: TestClient) -> None:
    response = client.get("/timesheets")
    assert response.status_code == 401
