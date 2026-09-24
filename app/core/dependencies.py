"""Reusable FastAPI dependencies for authentication and authorization.

Chain: get_current_user -> require_role(...) -> require_location_access(...).
The last one is what makes multi-location scoping safe: it checks the
caller's manager_locations/employee_locations row, not just their role.
"""
import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.employee_location import EmployeeLocation
from app.models.manager_location import ManagerLocation
from app.models.user import User, UserRole

_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a Bearer JWT.

    Rejects: missing credentials, invalid/expired tokens, tokens for a
    nonexistent user, tokens signed before the user's last credential reset
    (stale `token_version`), and inactive users.
    """
    if credentials is None:
        raise _CREDENTIALS_ERROR

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise _CREDENTIALS_ERROR from exc

    subject = payload.get("sub")
    if subject is None:
        raise _CREDENTIALS_ERROR

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise _CREDENTIALS_ERROR from exc

    user = db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_ERROR

    if payload.get("token_version") != user.token_version:
        raise _CREDENTIALS_ERROR

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


def require_role(*allowed_roles: UserRole) -> Callable[[User], User]:
    """Dependency factory: only let through users whose role is in `allowed_roles`."""

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not permitted for this role",
            )
        return current_user

    return _check


def user_can_access_location(db: Session, user: User, location_id: uuid.UUID) -> bool:
    """True if `user` may act on `location_id`, given their role.

    Admins can access every location. Managers are scoped to the locations
    they're explicitly assigned to via manager_locations. Employees are
    scoped to their home_location_id plus any explicit employee_locations
    rows — the same two sources /locations and
    manager_shares_location_with_employee treat as "this employee's
    locations", kept consistent here.
    """
    if user.role == UserRole.ADMIN:
        return True

    if user.role == UserRole.MANAGER:
        stmt = select(ManagerLocation).where(
            ManagerLocation.manager_id == user.id,
            ManagerLocation.location_id == location_id,
        )
        return db.scalar(stmt) is not None

    if user.home_location_id == location_id:
        return True
    stmt = select(EmployeeLocation).where(
        EmployeeLocation.employee_id == user.id,
        EmployeeLocation.location_id == location_id,
    )
    return db.scalar(stmt) is not None


def manager_shares_location_with_employee(
    db: Session, manager: User, employee_id: uuid.UUID
) -> bool:
    """True if `manager` and the given employee are linked through at least
    one common location — i.e. the manager is allowed to see that
    employee's data (e.g. availability) for rostering purposes.

    An employee's location set is their home_location_id plus any explicit
    employee_locations rows, matching how visibility is resolved elsewhere
    (see app/api/locations.py).
    """
    manager_location_ids = set(
        db.scalars(
            select(ManagerLocation.location_id).where(ManagerLocation.manager_id == manager.id)
        ).all()
    )
    if not manager_location_ids:
        return False

    employee = db.get(User, employee_id)
    employee_location_ids = {employee.home_location_id} if employee and employee.home_location_id else set()
    employee_location_ids.update(
        db.scalars(
            select(EmployeeLocation.location_id).where(
                EmployeeLocation.employee_id == employee_id
            )
        ).all()
    )
    employee_location_ids.discard(None)

    return bool(manager_location_ids & employee_location_ids)


def require_location_access(
    location_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Dependency for routes with a `location_id` path parameter.

    Raises 403 unless `current_user` is an admin or is explicitly assigned
    to `location_id`.
    """
    if not user_can_access_location(db, current_user, location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not permitted for this location",
        )
    return current_user
