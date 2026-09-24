import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.employee_location import EmployeeLocation
from app.models.location import Location
from app.models.manager_location import ManagerLocation
from app.models.user import UserRole
from tests.helpers import DEFAULT_PASSWORD, auth_headers, create_user, login, unique_email


def _create_location(db_session: Session, name: str) -> Location:
    location = Location(name=name, address="1 Test St", timezone="Australia/Sydney")
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)
    return location


# ---------------------------------------------------------------------------
# POST /users — provisioning
# ---------------------------------------------------------------------------


def test_admin_can_provision_employee(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)
    email = unique_email("new-employee")

    response = client.post(
        "/users",
        json={"email": email, "password": DEFAULT_PASSWORD, "role": "employee"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert body["role"] == "employee"


def test_admin_can_provision_manager(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)

    response = client.post(
        "/users",
        json={"email": unique_email("new-manager"), "password": DEFAULT_PASSWORD, "role": "manager"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 201
    assert response.json()["role"] == "manager"


def test_manager_can_provision_employee(client: TestClient, db_session: Session) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)

    response = client.post(
        "/users",
        json={"email": unique_email("emp"), "password": DEFAULT_PASSWORD, "role": "employee"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 201


def test_manager_cannot_provision_manager(client: TestClient, db_session: Session) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)

    response = client.post(
        "/users",
        json={"email": unique_email("emp"), "password": DEFAULT_PASSWORD, "role": "manager"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 403


def test_manager_cannot_provision_admin(client: TestClient, db_session: Session) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)

    response = client.post(
        "/users",
        json={"email": unique_email("emp"), "password": DEFAULT_PASSWORD, "role": "admin"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 403


def test_employee_cannot_provision_anyone(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.post(
        "/users",
        json={"email": unique_email("emp"), "password": DEFAULT_PASSWORD},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 403


def test_unauthenticated_cannot_provision(client: TestClient) -> None:
    response = client.post(
        "/users", json={"email": unique_email("emp"), "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 401


def test_duplicate_email_rejected(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)
    email = unique_email("dup")

    first = client.post(
        "/users",
        json={"email": email, "password": DEFAULT_PASSWORD, "role": "employee"},
        headers=auth_headers(tokens),
    )
    second = client.post(
        "/users",
        json={"email": email, "password": DEFAULT_PASSWORD, "role": "employee"},
        headers=auth_headers(tokens),
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_provisioning_with_location_assigns_employee_location(
    client: TestClient, db_session: Session
) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)
    location = _create_location(db_session, f"Kiosk {uuid.uuid4().hex}")

    response = client.post(
        "/users",
        json={
            "email": unique_email("emp"),
            "password": DEFAULT_PASSWORD,
            "role": "employee",
            "location_ids": [str(location.id)],
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["id"])
    row = (
        db_session.query(EmployeeLocation)
        .filter(
            EmployeeLocation.employee_id == user_id, EmployeeLocation.location_id == location.id
        )
        .first()
    )
    assert row is not None


def test_manager_cannot_assign_location_they_do_not_manage(
    client: TestClient, db_session: Session
) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)
    unmanaged = _create_location(db_session, f"Unmanaged Store {uuid.uuid4().hex}")

    response = client.post(
        "/users",
        json={
            "email": unique_email("emp"),
            "password": DEFAULT_PASSWORD,
            "role": "employee",
            "location_ids": [str(unmanaged.id)],
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 403


def test_manager_can_assign_managed_location(client: TestClient, db_session: Session) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    tokens = login(client, manager.email)
    location = _create_location(db_session, f"Managed Store {uuid.uuid4().hex}")
    db_session.add(ManagerLocation(manager_id=manager.id, location_id=location.id))
    db_session.commit()

    response = client.post(
        "/users",
        json={
            "email": unique_email("emp"),
            "password": DEFAULT_PASSWORD,
            "role": "employee",
            "location_ids": [str(location.id)],
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 201


def test_provisioning_with_nonexistent_location_rejected(
    client: TestClient, db_session: Session
) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)

    response = client.post(
        "/users",
        json={
            "email": unique_email("emp"),
            "password": DEFAULT_PASSWORD,
            "role": "employee",
            "location_ids": [str(uuid.uuid4())],
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 400


def test_provisioning_with_nonexistent_home_location_rejected(
    client: TestClient, db_session: Session
) -> None:
    """Regression check: a bad home_location_id must not be misreported as
    a duplicate-email conflict (both used to raise the same IntegrityError)."""
    admin = create_user(db_session, role=UserRole.ADMIN)
    tokens = login(client, admin.email)

    response = client.post(
        "/users",
        json={
            "email": unique_email("emp"),
            "password": DEFAULT_PASSWORD,
            "role": "employee",
            "home_location_id": str(uuid.uuid4()),
        },
        headers=auth_headers(tokens),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /users — listing
# ---------------------------------------------------------------------------


def test_admin_lists_all_users(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, role=UserRole.ADMIN)
    create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, admin.email)

    response = client.get("/users", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert len(response.json()) >= 2


def test_manager_lists_only_users_at_managed_locations(
    client: TestClient, db_session: Session
) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    location = _create_location(db_session, f"Store A {uuid.uuid4().hex}")
    other_location = _create_location(db_session, f"Store B {uuid.uuid4().hex}")
    db_session.add(ManagerLocation(manager_id=manager.id, location_id=location.id))
    db_session.commit()

    visible_employee = create_user(db_session, role=UserRole.EMPLOYEE)
    db_session.add(EmployeeLocation(employee_id=visible_employee.id, location_id=location.id))
    hidden_employee = create_user(db_session, role=UserRole.EMPLOYEE)
    db_session.add(
        EmployeeLocation(employee_id=hidden_employee.id, location_id=other_location.id)
    )
    db_session.commit()

    tokens = login(client, manager.email)
    response = client.get("/users", headers=auth_headers(tokens))

    assert response.status_code == 200
    emails = {u["email"] for u in response.json()}
    assert visible_employee.email in emails
    assert hidden_employee.email not in emails


def test_manager_with_no_locations_lists_nothing(client: TestClient, db_session: Session) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, manager.email)

    response = client.get("/users", headers=auth_headers(tokens))

    assert response.status_code == 200
    assert response.json() == []


def test_manager_filtering_by_unmanaged_location_forbidden(
    client: TestClient, db_session: Session
) -> None:
    manager = create_user(db_session, role=UserRole.MANAGER)
    other_location = _create_location(db_session, f"Not Mine {uuid.uuid4().hex}")
    tokens = login(client, manager.email)

    response = client.get(
        f"/users?location_id={other_location.id}", headers=auth_headers(tokens)
    )

    assert response.status_code == 403


def test_employee_cannot_list_users(client: TestClient, db_session: Session) -> None:
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    tokens = login(client, employee.email)

    response = client.get("/users", headers=auth_headers(tokens))

    assert response.status_code == 403


def test_unauthenticated_cannot_list_users(client: TestClient) -> None:
    response = client.get("/users")

    assert response.status_code == 401
