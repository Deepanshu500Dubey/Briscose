"""Location endpoints.

Visibility follows the caller's role (see the project blueprint, Section 8):
Admins see every location; Managers see the locations they're assigned to;
Employees see their home location plus any they're explicitly assigned to.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_location_access, require_role
from app.db.session import get_db
from app.models.employee_location import EmployeeLocation
from app.models.location import Location
from app.models.manager_location import ManagerLocation
from app.models.user import User, UserRole
from app.schemas.location import LocationCreate, LocationResponse

router = APIRouter(prefix="/locations", tags=["locations"])


@router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
def create_location(
    payload: LocationCreate,
    _: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> Location:
    """Admin-only (project blueprint, Section 1's role table). There's no
    Manager path here by design — location creation is an org-structure
    decision, not a store-level one."""
    location = Location(name=payload.name, address=payload.address, timezone=payload.timezone)
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("", response_model=list[LocationResponse])
def list_locations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Location]:
    if current_user.role == UserRole.ADMIN:
        stmt = select(Location)
    elif current_user.role == UserRole.MANAGER:
        stmt = (
            select(Location)
            .join(ManagerLocation, ManagerLocation.location_id == Location.id)
            .where(ManagerLocation.manager_id == current_user.id)
        )
    else:
        ids = {current_user.home_location_id} if current_user.home_location_id else set()
        assigned_ids = db.scalars(
            select(EmployeeLocation.location_id).where(
                EmployeeLocation.employee_id == current_user.id
            )
        ).all()
        ids.update(assigned_ids)
        ids.discard(None)
        if not ids:
            return []
        stmt = select(Location).where(Location.id.in_(ids))

    return list(db.scalars(stmt).all())


@router.get("/{location_id}", response_model=LocationResponse)
def get_location(
    location_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_location_access),
) -> Location:
    location = db.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location
