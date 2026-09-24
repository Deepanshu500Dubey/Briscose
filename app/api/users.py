"""User provisioning & listing.

Accounts are created by a Manager or Admin, never by self-signup (project
blueprint, Section 9) — HR/rostering owns account creation, matching a real
retail deployment. A Manager may only provision Employee accounts, and only
at locations they themselves manage; an Admin may provision any role at any
location.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import require_role, user_can_access_location
from app.core.security import hash_password
from app.db.session import get_db
from app.models.employee_location import EmployeeLocation
from app.models.location import Location
from app.models.manager_location import ManagerLocation
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def provision_user(
    payload: UserCreate,
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    if current_user.role == UserRole.MANAGER and payload.role != UserRole.EMPLOYEE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers may only provision employee accounts",
        )

    if current_user.role == UserRole.MANAGER:
        for location_id in payload.location_ids:
            if not user_can_access_location(db, current_user, location_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not permitted to assign location {location_id}",
                )

    if payload.home_location_id is not None and db.get(Location, payload.home_location_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="home_location_id does not exist"
        )

    user = User(
        email=_normalize_email(payload.email),
        hashed_password=hash_password(payload.password),
        role=payload.role,
        home_location_id=payload.home_location_id,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from exc

    for location_id in payload.location_ids:
        if payload.role == UserRole.MANAGER:
            db.add(ManagerLocation(manager_id=user.id, location_id=location_id))
        else:
            db.add(EmployeeLocation(employee_id=user.id, location_id=location_id))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more location_ids do not exist",
        ) from exc

    db.refresh(user)
    return user


@router.get("", response_model=list[UserResponse])
def list_users(
    location_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[User]:
    if current_user.role == UserRole.ADMIN and location_id is None:
        return list(db.scalars(select(User).order_by(User.created_at)).all())

    if current_user.role == UserRole.ADMIN:
        target_location_ids = {location_id}
    else:
        managed_ids = set(
            db.scalars(
                select(ManagerLocation.location_id).where(
                    ManagerLocation.manager_id == current_user.id
                )
            ).all()
        )
        if location_id is not None:
            if location_id not in managed_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not permitted for this location",
                )
            target_location_ids = {location_id}
        else:
            target_location_ids = managed_ids

    if not target_location_ids:
        return []

    stmt = (
        select(User)
        .distinct()
        .outerjoin(EmployeeLocation, EmployeeLocation.employee_id == User.id)
        .outerjoin(ManagerLocation, ManagerLocation.manager_id == User.id)
        .where(
            User.home_location_id.in_(target_location_ids)
            | EmployeeLocation.location_id.in_(target_location_ids)
            | ManagerLocation.location_id.in_(target_location_ids)
        )
        .order_by(User.created_at)
    )
    return list(db.scalars(stmt).all())
