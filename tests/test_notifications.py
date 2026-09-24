import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def _today():
    return datetime.now(timezone.utc).date()


def test_employee_receives_notification_on_offer(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)

    client.post(
        f"/shifts/{shift.id}/assignments",
        json={"employee_id": str(employee.id)},
        headers=auth_headers(mgr_tokens),
    )

    emp_tokens = login(client, employee.email)
    response = client.get("/notifications", headers=auth_headers(emp_tokens))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["type"] == "offer"
    assert body[0]["shift_id"] == str(shift.id)
    assert body[0]["is_read"] is False


def test_mark_notification_read(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)
    client.post(
        f"/shifts/{shift.id}/assignments",
        json={"employee_id": str(employee.id)},
        headers=auth_headers(mgr_tokens),
    )

    emp_tokens = login(client, employee.email)
    notification_id = client.get("/notifications", headers=auth_headers(emp_tokens)).json()[0]["id"]

    response = client.patch(
        f"/notifications/{notification_id}/read", headers=auth_headers(emp_tokens)
    )

    assert response.status_code == 200
    assert response.json()["is_read"] is True


def test_cannot_mark_others_notification_read(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    other_employee = create_user(db_session, role=UserRole.EMPLOYEE)
    mgr_tokens = login(client, manager.email)
    client.post(
        f"/shifts/{shift.id}/assignments",
        json={"employee_id": str(employee.id)},
        headers=auth_headers(mgr_tokens),
    )

    emp_tokens = login(client, employee.email)
    notification_id = client.get("/notifications", headers=auth_headers(emp_tokens)).json()[0]["id"]

    other_tokens = login(client, other_employee.email)
    response = client.patch(
        f"/notifications/{notification_id}/read", headers=auth_headers(other_tokens)
    )

    assert response.status_code == 404


def test_mark_nonexistent_notification_read_404(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.patch(f"/notifications/{uuid.uuid4()}/read", headers=auth_headers(tokens))

    assert response.status_code == 404


def test_notifications_requires_authentication(client: TestClient) -> None:
    response = client.get("/notifications")
    assert response.status_code == 401
