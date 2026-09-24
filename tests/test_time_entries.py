"""Tests for clock in/out — the six explicit cases from the project
blueprint, Section 10."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.time_entry import TimeEntry
from app.models.user import UserRole
from tests.helpers import (
    assign_employee,
    assign_manager,
    auth_headers,
    create_accepted_assignment,
    create_location,
    create_shift,
    create_user,
    freeze_time_clock_now,
    login,
)

# A fixed Monday noon UTC — deterministic regardless of when tests actually
# run, via freeze_time_clock_now().
FIXED_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


def test_clock_in_within_grace_window_no_flag(client: TestClient, db_session: Session, monkeypatch) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    shift = create_shift(
        db_session, location, manager, on=FIXED_NOW.date(),
        start_time=(FIXED_NOW - timedelta(hours=2)).time(),
        end_time=(FIXED_NOW + timedelta(hours=2)).time(),
        min_staff=1, max_staff=1,
    )
    create_accepted_assignment(db_session, shift, employee, manager)
    tokens = login(client, employee.email)

    response = client.post("/time-entries/clock-in", json={}, headers=auth_headers(tokens))

    assert response.status_code == 201
    body = response.json()
    assert body["shift_id"] == str(shift.id)
    assert body["flag"] == "none"


def test_clock_in_before_grace_window_flags_early_start(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    # Starts 1 hour from now — outside the 15-minute grace window.
    shift = create_shift(
        db_session, location, manager, on=FIXED_NOW.date(),
        start_time=(FIXED_NOW + timedelta(hours=1)).time(),
        end_time=(FIXED_NOW + timedelta(hours=5)).time(),
        min_staff=1, max_staff=1,
    )
    create_accepted_assignment(db_session, shift, employee, manager)
    tokens = login(client, employee.email)

    response = client.post(
        "/time-entries/clock-in", json={"shift_id": str(shift.id)}, headers=auth_headers(tokens)
    )

    assert response.status_code == 201
    assert response.json()["flag"] == "early_start"


def test_clock_in_after_shift_end_flags_after_shift_end(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    shift = create_shift(
        db_session, location, manager, on=FIXED_NOW.date(),
        start_time=(FIXED_NOW - timedelta(hours=5)).time(),
        end_time=(FIXED_NOW - timedelta(hours=1)).time(),
        min_staff=1, max_staff=1,
    )
    create_accepted_assignment(db_session, shift, employee, manager)
    tokens = login(client, employee.email)

    response = client.post(
        "/time-entries/clock-in", json={"shift_id": str(shift.id)}, headers=auth_headers(tokens)
    )

    assert response.status_code == 201
    assert response.json()["flag"] == "after_shift_end"


def test_clock_in_with_no_shift_flags_unscheduled(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    employee = create_user(db_session, role=UserRole.EMPLOYEE, home_location_id=location.id)
    tokens = login(client, employee.email)

    response = client.post("/time-entries/clock-in", json={}, headers=auth_headers(tokens))

    assert response.status_code == 201
    body = response.json()
    assert body["shift_id"] is None
    assert body["flag"] == "unscheduled"
    assert body["location_id"] == str(location.id)


def test_clock_in_with_no_shift_and_no_home_location_rejected(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.post("/time-entries/clock-in", json={}, headers=auth_headers(tokens))

    assert response.status_code == 400


def test_clock_in_ambiguous_gap_returns_choose_shift(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)

    morning = create_shift(
        db_session, location, manager, on=FIXED_NOW.date(),
        start_time=(FIXED_NOW - timedelta(hours=6)).time(),
        end_time=(FIXED_NOW - timedelta(hours=2)).time(),
        min_staff=1, max_staff=1,
    )
    afternoon = create_shift(
        db_session, location, manager, on=FIXED_NOW.date(),
        start_time=(FIXED_NOW + timedelta(hours=2)).time(),
        end_time=(FIXED_NOW + timedelta(hours=6)).time(),
        min_staff=1, max_staff=1,
    )
    create_accepted_assignment(db_session, morning, employee, manager)
    create_accepted_assignment(db_session, afternoon, employee, manager)
    tokens = login(client, employee.email)

    response = client.post("/time-entries/clock-in", json={}, headers=auth_headers(tokens))

    assert response.status_code == 409
    choice_ids = {c["id"] for c in response.json()["choose_shift"]}
    assert choice_ids == {str(morning.id), str(afternoon.id)}


def test_clock_in_requested_shift_not_in_candidates_forbidden(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    other_shift = create_shift(db_session, location, manager, on=FIXED_NOW.date())
    tokens = login(client, employee.email)

    response = client.post(
        "/time-entries/clock-in",
        json={"shift_id": str(other_shift.id)},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 403


def test_clock_in_while_already_open_is_soft_success(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    employee = create_user(db_session, role=UserRole.EMPLOYEE, home_location_id=location.id)
    tokens = login(client, employee.email)

    first = client.post("/time-entries/clock-in", json={}, headers=auth_headers(tokens))
    assert first.status_code == 201

    second = client.post("/time-entries/clock-in", json={}, headers=auth_headers(tokens))
    assert second.status_code == 409
    assert second.json()["id"] == first.json()["id"]


def test_clock_out_closes_open_entry(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    employee = create_user(db_session, role=UserRole.EMPLOYEE, home_location_id=location.id)
    tokens = login(client, employee.email)
    client.post("/time-entries/clock-in", json={}, headers=auth_headers(tokens))

    response = client.post("/time-entries/clock-out", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert response.json()["clock_out"] is not None


def test_clock_out_without_open_entry_rejected(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.post("/time-entries/clock-out", headers=auth_headers(tokens))

    assert response.status_code == 409


def test_manager_can_force_close_stale_entry(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE, home_location_id=location.id)
    emp_tokens = login(client, employee.email)
    client.post("/time-entries/clock-in", json={}, headers=auth_headers(emp_tokens))
    entry_id = db_session.query(TimeEntry).filter(TimeEntry.employee_id == employee.id).one().id

    mgr_tokens = login(client, manager.email)
    response = client.patch(
        f"/time-entries/{entry_id}",
        json={"clock_out": (FIXED_NOW + timedelta(hours=8)).isoformat()},
        headers=auth_headers(mgr_tokens),
    )

    assert response.status_code == 200
    assert response.json()["clock_out"] is not None


def test_manager_cannot_force_close_already_closed_entry(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE, home_location_id=location.id)
    emp_tokens = login(client, employee.email)
    client.post("/time-entries/clock-in", json={}, headers=auth_headers(emp_tokens))
    client.post("/time-entries/clock-out", headers=auth_headers(emp_tokens))
    entry_id = db_session.query(TimeEntry).filter(TimeEntry.employee_id == employee.id).one().id

    mgr_tokens = login(client, manager.email)
    response = client.patch(
        f"/time-entries/{entry_id}",
        json={"clock_out": (FIXED_NOW + timedelta(hours=8)).isoformat()},
        headers=auth_headers(mgr_tokens),
    )

    assert response.status_code == 400


def test_manager_cannot_force_close_at_unmanaged_location(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    freeze_time_clock_now(monkeypatch, FIXED_NOW)
    location = create_location(db_session, timezone="UTC")
    employee = create_user(db_session, role=UserRole.EMPLOYEE, home_location_id=location.id)
    emp_tokens = login(client, employee.email)
    client.post("/time-entries/clock-in", json={}, headers=auth_headers(emp_tokens))
    entry_id = db_session.query(TimeEntry).filter(TimeEntry.employee_id == employee.id).one().id

    other_manager = create_user(db_session, role=UserRole.MANAGER)
    mgr_tokens = login(client, other_manager.email)
    response = client.patch(
        f"/time-entries/{entry_id}",
        json={"clock_out": (FIXED_NOW + timedelta(hours=1)).isoformat()},
        headers=auth_headers(mgr_tokens),
    )

    assert response.status_code == 403


def test_manager_cannot_clock_in(client: TestClient, db_session: Session) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)

    response = client.post("/time-entries/clock-in", json={}, headers=auth_headers(tokens))

    assert response.status_code == 403


def test_clock_in_requires_authentication(client: TestClient) -> None:
    response = client.post("/time-entries/clock-in", json={})
    assert response.status_code == 401
