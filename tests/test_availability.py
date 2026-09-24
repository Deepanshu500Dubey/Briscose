from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.employee_location import EmployeeLocation
from app.models.location import Location
from app.models.manager_location import ManagerLocation
from app.models.user import UserRole
from tests.helpers import auth_headers, create_user, login


def _today():
    return datetime.now(timezone.utc).date()


def _create_location(db_session: Session, name: str) -> Location:
    location = Location(name=name, address="1 Test St", timezone="Australia/Sydney")
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)
    return location


# ---------------------------------------------------------------------------
# PATCH /availability — bulk upsert
# ---------------------------------------------------------------------------


def test_upsert_creates_rows_for_self(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)
    today = _today()

    response = client.patch(
        "/availability",
        json={
            "days": [
                {
                    "date": today.isoformat(),
                    "is_available": True,
                    "start_time": "08:00:00",
                    "end_time": "16:00:00",
                },
                {"date": (today + timedelta(days=1)).isoformat(), "is_available": False},
            ]
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["employee_id"] == str(employee.id)
    assert body[0]["is_available"] is True
    assert body[0]["start_time"] == "08:00:00"
    assert body[1]["is_available"] is False
    assert body[1]["start_time"] is None


def test_upsert_requires_authentication(client: TestClient) -> None:
    response = client.patch("/availability", json={"days": []})
    assert response.status_code == 401


def test_upsert_requires_times_when_available(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.patch(
        "/availability",
        json={"days": [{"date": _today().isoformat(), "is_available": True}]},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422


def test_upsert_rejects_start_after_end(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.patch(
        "/availability",
        json={
            "days": [
                {
                    "date": _today().isoformat(),
                    "is_available": True,
                    "start_time": "16:00:00",
                    "end_time": "08:00:00",
                }
            ]
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422


def test_upsert_rejects_duplicate_dates_in_payload(
    client: TestClient, db_session: Session
) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)
    today = _today().isoformat()

    response = client.patch(
        "/availability",
        json={
            "days": [
                {"date": today, "is_available": False},
                {"date": today, "is_available": True, "start_time": "08:00:00", "end_time": "12:00:00"},
            ]
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422


def test_upsert_rejects_dates_outside_rolling_window(
    client: TestClient, db_session: Session
) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)
    too_far = (_today() + timedelta(days=30)).isoformat()

    response = client.patch(
        "/availability",
        json={"days": [{"date": too_far, "is_available": False}]},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 400


def test_edit_preserves_original_created_at(client: TestClient, db_session: Session) -> None:
    """The ordering-critical invariant from Section 10: editing a day never
    changes its created_at — the moment the employee first said they were
    free, which is what auto-reassignment ordering will read from once
    shifts exist."""
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)
    today = _today().isoformat()

    first = client.patch(
        "/availability",
        json={
            "days": [
                {"date": today, "is_available": True, "start_time": "08:00:00", "end_time": "12:00:00"}
            ]
        },
        headers=auth_headers(tokens),
    )
    original_created_at = first.json()[0]["created_at"]

    second = client.patch(
        "/availability",
        json={
            "days": [
                {"date": today, "is_available": True, "start_time": "09:00:00", "end_time": "17:00:00"}
            ]
        },
        headers=auth_headers(tokens),
    )

    assert second.status_code == 200
    body = second.json()[0]
    assert body["start_time"] == "09:00:00"
    assert body["created_at"] == original_created_at


def test_upsert_only_ever_writes_callers_own_rows(
    client: TestClient, db_session: Session
) -> None:
    employee_a = create_user(db_session, role=UserRole.EMPLOYEE)
    employee_b = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens_a = login(client, employee_a.email)
    today = _today().isoformat()

    client.patch(
        "/availability",
        json={"days": [{"date": today, "is_available": False}]},
        headers=auth_headers(tokens_a),
    )

    tokens_b = login(client, employee_b.email)
    response = client.get(
        f"/availability?employee_id={employee_b.id}", headers=auth_headers(tokens_b)
    )
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /availability
# ---------------------------------------------------------------------------


def test_get_requires_authentication(client: TestClient) -> None:
    response = client.get("/availability")
    assert response.status_code == 401


def test_get_defaults_to_self(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)
    today = _today().isoformat()
    client.patch(
        "/availability",
        json={"days": [{"date": today, "is_available": False}]},
        headers=auth_headers(tokens),
    )

    response = client.get("/availability", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["employee_id"] == str(employee.id)


def test_get_rejects_from_after_to(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)
    today = _today()

    response = client.get(
        f"/availability?from={today.isoformat()}&to={(today - timedelta(days=1)).isoformat()}",
        headers=auth_headers(tokens),
    )

    assert response.status_code == 400


def test_employee_cannot_view_other_employee_availability(
    client: TestClient, db_session: Session
) -> None:
    viewer = create_user(db_session, role=UserRole.EMPLOYEE)
    target = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, viewer.email)

    response = client.get(f"/availability?employee_id={target.id}", headers=auth_headers(tokens))

    assert response.status_code == 403


def test_manager_can_view_shared_location_employee_availability(
    client: TestClient, db_session: Session
) -> None:
    location = _create_location(db_session, "Shared Store")
    manager = create_user(db_session, role=UserRole.MANAGER)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    db_session.add(ManagerLocation(manager_id=manager.id, location_id=location.id))
    db_session.add(EmployeeLocation(employee_id=employee.id, location_id=location.id))
    db_session.commit()

    employee_tokens = login(client, employee.email)
    today = _today().isoformat()
    client.patch(
        "/availability",
        json={
            "days": [
                {"date": today, "is_available": True, "start_time": "08:00:00", "end_time": "16:00:00"}
            ]
        },
        headers=auth_headers(employee_tokens),
    )

    manager_tokens = login(client, manager.email)
    response = client.get(
        f"/availability?employee_id={employee.id}", headers=auth_headers(manager_tokens)
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_manager_without_shared_location_forbidden(
    client: TestClient, db_session: Session
) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, manager.email)

    response = client.get(f"/availability?employee_id={employee.id}", headers=auth_headers(tokens))

    assert response.status_code == 403


def test_admin_can_view_any_employee_availability(
    client: TestClient, db_session: Session
) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, admin.email)

    response = client.get(f"/availability?employee_id={employee.id}", headers=auth_headers(tokens))

    assert response.status_code == 200
