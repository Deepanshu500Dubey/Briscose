"""Timesheet endpoint (project blueprint, Section 8 & 10)."""
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, manager_shares_location_with_employee
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.timesheet import TimesheetResponse
from app.services.timesheet_service import build_timesheet

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


def _week_range(week: date | None) -> tuple[date, date]:
    anchor = week or datetime.now(timezone.utc).date()
    monday = anchor - timedelta(days=anchor.isoweekday() - 1)
    return monday, monday + timedelta(days=6)


@router.get("", response_model=TimesheetResponse)
def get_timesheet(
    employee_id: uuid.UUID | None = Query(default=None),
    week: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    target_id = employee_id or current_user.id

    if target_id != current_user.id:
        allowed = current_user.role == UserRole.ADMIN or (
            current_user.role == UserRole.MANAGER
            and manager_shares_location_with_employee(db, current_user, target_id)
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not permitted to view this employee's timesheet",
            )

    week_start, week_end = _week_range(week)
    return build_timesheet(db, target_id, week_start, week_end)
