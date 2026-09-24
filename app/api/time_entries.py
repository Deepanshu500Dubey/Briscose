"""Time-clock endpoints (project blueprint, Section 8 & 10)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import require_role, user_can_access_location
from app.db.session import get_db
from app.models.time_entry import TimeEntry
from app.models.user import User, UserRole
from app.schemas.time_entry import (
    ClockInRequest,
    ForceCloseRequest,
    ShiftChoiceResponse,
    TimeEntryResponse,
)
from app.services.time_clock_service import clock_in as clock_in_service
from app.services.time_clock_service import clock_out as clock_out_service
from app.services.time_clock_service import force_close

router = APIRouter(prefix="/time-entries", tags=["time-entries"])


@router.post("/clock-in")
def clock_in(
    payload: ClockInRequest = ClockInRequest(),
    current_user: User = Depends(require_role(UserRole.EMPLOYEE)),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Three distinct outcomes, hence the manual JSONResponse instead of a
    fixed response_model: 201 (new entry), 409 soft-success (already
    clocked in — client syncs its UI), or 409 with a shift choice to
    disambiguate (Section 10)."""
    status_code, result = clock_in_service(db, current_user, payload.shift_id)
    db.commit()

    if isinstance(result, dict):
        choices = [
            ShiftChoiceResponse.model_validate(shift).model_dump(mode="json")
            for shift in result["choose_shift"]
        ]
        return JSONResponse(status_code=status_code, content={"choose_shift": choices})

    db.refresh(result)
    body = TimeEntryResponse.model_validate(result).model_dump(mode="json")
    return JSONResponse(status_code=status_code, content=body)


@router.post("/clock-out", response_model=TimeEntryResponse)
def clock_out(
    current_user: User = Depends(require_role(UserRole.EMPLOYEE)),
    db: Session = Depends(get_db),
) -> TimeEntry:
    entry = clock_out_service(db, current_user)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/{entry_id}", response_model=TimeEntryResponse)
def patch_time_entry(
    entry_id: uuid.UUID,
    payload: ForceCloseRequest,
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> TimeEntry:
    entry = db.get(TimeEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time entry not found")
    if not user_can_access_location(db, current_user, entry.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this location"
        )

    updated = force_close(db, entry, payload.clock_out)
    db.commit()
    db.refresh(updated)
    return updated
