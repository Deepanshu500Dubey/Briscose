"""Unit tests for the require_role / require_location_access dependencies."""
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import require_role, user_can_access_location
from app.models.employee_location import EmployeeLocation
from app.models.location import Location
from app.models.manager_location import ManagerLocation
from app.models.user import User, UserRole
from tests.helpers import unique_email


def _make_user(role: UserRole) -> User:
    # A unique email per call, not a fixed one — this module shares a
    # database with manually-seeded or other test data, and a fixed email
    # would collide (see tests/helpers.py, which follows this convention
    # everywhere else in the suite).
    return User(email=unique_email(role.value), hashed_password="x", role=role)


def test_require_role_allows_matching_role() -> None:
    check = require_role(UserRole.MANAGER, UserRole.ADMIN)
    manager = _make_user(UserRole.MANAGER)

    assert check(current_user=manager) is manager


def test_require_role_rejects_other_role() -> None:
    check = require_role(UserRole.MANAGER, UserRole.ADMIN)
    employee = _make_user(UserRole.EMPLOYEE)

    with pytest.raises(HTTPException) as exc_info:
        check(current_user=employee)
    assert exc_info.value.status_code == 403


def _create_location(db_session: Session, name: str = "Westfield Kiosk") -> Location:
    location = Location(name=name, address="1 Test St", timezone="Australia/Sydney")
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)
    return location


def _create_user(db_session: Session, role: UserRole) -> User:
    user = _make_user(role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_can_access_any_location(db_session: Session) -> None:
    location = _create_location(db_session)
    admin = _create_user(db_session, UserRole.ADMIN)

    assert user_can_access_location(db_session, admin, location.id) is True


def test_manager_requires_explicit_assignment(db_session: Session) -> None:
    location = _create_location(db_session)
    manager = _create_user(db_session, UserRole.MANAGER)

    assert user_can_access_location(db_session, manager, location.id) is False

    db_session.add(ManagerLocation(manager_id=manager.id, location_id=location.id))
    db_session.commit()

    assert user_can_access_location(db_session, manager, location.id) is True


def test_employee_requires_explicit_assignment(db_session: Session) -> None:
    location = _create_location(db_session)
    employee = _create_user(db_session, UserRole.EMPLOYEE)

    assert user_can_access_location(db_session, employee, location.id) is False

    db_session.add(EmployeeLocation(employee_id=employee.id, location_id=location.id))
    db_session.commit()

    assert user_can_access_location(db_session, employee, location.id) is True


def test_manager_assignment_does_not_grant_employee_access(db_session: Session) -> None:
    """A manager assigned to a location isn't automatically an eligible
    employee there — the two join tables are checked independently."""
    location = _create_location(db_session)
    manager = _create_user(db_session, UserRole.MANAGER)
    db_session.add(ManagerLocation(manager_id=manager.id, location_id=location.id))
    db_session.commit()

    employee = _create_user(db_session, UserRole.EMPLOYEE)
    assert user_can_access_location(db_session, employee, location.id) is False
