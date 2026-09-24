import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.employee_location import EmployeeLocation
from app.models.location import Location
from app.models.manager_location import ManagerLocation
from app.models.user import UserRole
from tests.helpers import auth_headers, create_user, login


def _create_location(db_session: Session, name: str) -> Location:
    location = Location(name=name, address="1 Test St", timezone="Australia/Sydney")
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)
    return location


# ---------------------------------------------------------------------------
# POST /locations
# ---------------------------------------------------------------------------


def test_admin_can_create_location(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)

    response = client.post(
        "/locations",
        json={"name": "New Store", "address": "1 Test St", "timezone": "Australia/Sydney"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "New Store"
    assert body["is_active"] is True


def test_create_location_rejects_invalid_timezone(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)

    response = client.post(
        "/locations",
        json={"name": "New Store", "address": "1 Test St", "timezone": "Not/ARealZone"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422


def test_manager_cannot_create_location(client: TestClient, db_session: Session) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)

    response = client.post(
        "/locations",
        json={"name": "New Store", "address": "1 Test St", "timezone": "Australia/Sydney"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 403


def test_unauthenticated_cannot_create_location(client: TestClient) -> None:
    response = client.post(
        "/locations",
        json={"name": "New Store", "address": "1 Test St", "timezone": "Australia/Sydney"},
    )

    assert response.status_code == 401


def test_admin_sees_all_locations(client: TestClient, db_session: Session) -> None:
    _create_location(db_session, f"Location A {uuid.uuid4().hex}")
    _create_location(db_session, f"Location B {uuid.uuid4().hex}")
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)

    response = client.get("/locations", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert len(response.json()) >= 2


def test_manager_sees_only_assigned_locations(client: TestClient, db_session: Session) -> None:
    assigned = _create_location(db_session, f"Assigned Store {uuid.uuid4().hex}")
    _create_location(db_session, f"Other Store {uuid.uuid4().hex}")
    manager = create_user(db_session, role=UserRole.MANAGER)
    db_session.add(ManagerLocation(manager_id=manager.id, location_id=assigned.id))
    db_session.commit()
    tokens = login(client, manager.email)

    response = client.get("/locations", headers=auth_headers(tokens))

    assert response.status_code == 200
    names = {loc["name"] for loc in response.json()}
    assert names == {assigned.name}


def test_manager_with_no_assignments_sees_nothing(
    client: TestClient, db_session: Session
) -> None:
    _create_location(db_session, f"Some Store {uuid.uuid4().hex}")
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)

    response = client.get("/locations", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert response.json() == []


def test_employee_sees_home_and_assigned_locations(
    client: TestClient, db_session: Session
) -> None:
    home = _create_location(db_session, f"Home Store {uuid.uuid4().hex}")
    other = _create_location(db_session, f"Other Store {uuid.uuid4().hex}")
    employee = create_user(db_session, role=UserRole.EMPLOYEE, home_location_id=home.id)
    db_session.add(EmployeeLocation(employee_id=employee.id, location_id=other.id))
    db_session.commit()
    tokens = login(client, employee.email)

    response = client.get("/locations", headers=auth_headers(tokens))

    assert response.status_code == 200
    names = {loc["name"] for loc in response.json()}
    assert names == {home.name, other.name}


def test_employee_with_no_home_or_assignment_sees_nothing(
    client: TestClient, db_session: Session
) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.get("/locations", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert response.json() == []


def test_get_location_forbidden_for_unassigned_employee(
    client: TestClient, db_session: Session
) -> None:
    location = _create_location(db_session, f"Unassigned Store {uuid.uuid4().hex}")
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.get(f"/locations/{location.id}", headers=auth_headers(tokens))

    assert response.status_code == 403


def test_get_location_allowed_for_admin(client: TestClient, db_session: Session) -> None:
    location = _create_location(db_session, f"Any Store {uuid.uuid4().hex}")
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)

    response = client.get(f"/locations/{location.id}", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert response.json()["name"] == location.name


def test_get_location_not_found(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)

    response = client.get(f"/locations/{uuid.uuid4()}", headers=auth_headers(tokens))

    assert response.status_code == 404
