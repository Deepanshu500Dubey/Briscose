import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import UserRole
from tests.helpers import (
    assign_employee,
    assign_manager,
    auth_headers,
    create_accepted_assignment,
    create_location,
    create_shift,
    create_user,
    login,
    set_availability,
)


def _today():
    return datetime.now(timezone.utc).date()


def test_manager_can_create_shift(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    tokens = login(client, manager.email)

    response = client.post(
        "/shifts",
        json={
            "location_id": str(location.id),
            "date": _today().isoformat(),
            "start_time": "08:00:00",
            "end_time": "16:00:00",
            "min_staff": 2,
            "max_staff": 3,
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert body["board_label"] == "Needs Staff"
    assert body["accepted_count"] == 0
    assert body["roster_locked_at"] is None


def test_admin_creating_shift_at_nonexistent_location_returns_404(
    client: TestClient, db_session: Session
) -> None:
    """Admins bypass the manager-location check unconditionally, so a
    garbage location_id needs its own guard — otherwise it would hit an
    unhandled FK violation on commit instead of a clean 404."""
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)

    response = client.post(
        "/shifts",
        json={
            "location_id": str(uuid.uuid4()),
            "date": _today().isoformat(),
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 404


def test_manager_cannot_create_shift_at_unmanaged_location(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)

    response = client.post(
        "/shifts",
        json={
            "location_id": str(location.id),
            "date": _today().isoformat(),
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 403


def test_employee_cannot_create_shift(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.post(
        "/shifts",
        json={
            "location_id": str(uuid.uuid4()),
            "date": _today().isoformat(),
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 403


def test_shift_rejects_start_after_end(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    tokens = login(client, manager.email)

    response = client.post(
        "/shifts",
        json={
            "location_id": str(location.id),
            "date": _today().isoformat(),
            "start_time": "16:00:00",
            "end_time": "08:00:00",
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422


def test_shift_rejects_min_greater_than_max(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    tokens = login(client, manager.email)

    response = client.post(
        "/shifts",
        json={
            "location_id": str(location.id),
            "date": _today().isoformat(),
            "start_time": "08:00:00",
            "end_time": "16:00:00",
            "min_staff": 5,
            "max_staff": 2,
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422


def test_manager_lists_shifts_for_week(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    tokens = login(client, manager.email)

    response = client.get(f"/shifts?location_id={location.id}", headers=auth_headers(tokens))

    assert response.status_code == 200
    ids = {s["id"] for s in response.json()}
    assert str(shift.id) in ids


def test_manager_list_shifts_requires_location_id(
    client: TestClient, db_session: Session
) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)

    response = client.get("/shifts", headers=auth_headers(tokens))

    assert response.status_code == 400


def test_manager_cannot_list_shifts_at_unmanaged_location(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)

    response = client.get(f"/shifts?location_id={location.id}", headers=auth_headers(tokens))

    assert response.status_code == 403


def test_employee_shift_includes_own_assignment_id_and_status(
    client: TestClient, db_session: Session
) -> None:
    """Regression check: without my_assignment_id, a client has no way to
    call POST/DELETE /assignments/{id} for a shift it only knows about via
    GET /shifts — this is what makes Accept/Reject actually callable."""
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=1)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)
    offer = client.post(
        f"/shifts/{shift.id}/assignments",
        json={"employee_id": str(employee.id)},
        headers=auth_headers(mgr_tokens),
    ).json()

    emp_tokens = login(client, employee.email)
    response = client.get("/shifts", headers=auth_headers(emp_tokens))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["my_assignment_id"] == offer["id"]
    assert body[0]["my_assignment_status"] == "offered"


def test_shift_lists_accepted_employees(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=2)
    accepted_employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, accepted_employee, location)
    create_accepted_assignment(db_session, shift, accepted_employee, manager)
    # An offered (not yet accepted) employee should NOT appear here.
    offered_employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, offered_employee, location)
    mgr_tokens = login(client, manager.email)
    client.post(
        f"/shifts/{shift.id}/assignments",
        json={"employee_id": str(offered_employee.id)},
        headers=auth_headers(mgr_tokens),
    )

    response = client.get(f"/shifts?location_id={location.id}", headers=auth_headers(mgr_tokens))

    assert response.status_code == 200
    accepted_ids = {e["id"] for e in response.json()[0]["accepted_employees"]}
    assert accepted_ids == {str(accepted_employee.id)}


def test_manager_shift_has_null_assignment_fields(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    create_shift(db_session, location, manager, on=_today())
    tokens = login(client, manager.email)

    response = client.get(f"/shifts?location_id={location.id}", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert response.json()[0]["my_assignment_id"] is None
    assert response.json()[0]["my_assignment_status"] is None


def test_employee_sees_only_own_assigned_shifts(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    create_shift(db_session, location, manager, on=_today())  # not assigned to employee
    tokens = login(client, employee.email)

    response = client.get("/shifts", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert response.json() == []


def test_candidates_returns_eligible_pool_ordered_by_first_submission(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())

    emp_late = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, emp_late, location)
    emp_early = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, emp_early, location)

    now = datetime.now(timezone.utc)
    set_availability(db_session, emp_late, on=_today(), created_at=now)
    set_availability(db_session, emp_early, on=_today(), created_at=now - timedelta(minutes=5))

    tokens = login(client, manager.email)
    response = client.get(f"/shifts/{shift.id}/candidates", headers=auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert [c["employee_id"] for c in body] == [str(emp_early.id), str(emp_late.id)]


def test_candidates_excludes_unavailable_and_wrong_location(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    other_location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())

    unavailable = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, unavailable, location)
    set_availability(db_session, unavailable, on=_today(), is_available=False)

    wrong_location = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, wrong_location, other_location)
    set_availability(db_session, wrong_location, on=_today())

    tokens = login(client, manager.email)
    response = client.get(f"/shifts/{shift.id}/candidates", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert response.json() == []
