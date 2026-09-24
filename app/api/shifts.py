"""Shift endpoints — creation, staffing board, candidates, roster
(project blueprint, Section 8 & 10)."""
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role, user_can_access_location
from app.db.session import get_db
from app.models.availability import Availability
from app.models.location import Location
from app.models.shift import Shift, ShiftStatus
from app.models.shift_assignment import AssignmentStatus, ShiftAssignment
from app.models.user import User, UserRole
from app.schemas.shift import AssignedEmployee, CandidateResponse, ShiftCreate, ShiftResponse
from app.services.assignment_service import (
    assigned_employee_ids,
    count_assignments,
    eligible_employees_for_shift,
)

router = APIRouter(tags=["shifts"])


def _week_range(week: date | None) -> tuple[date, date]:
    """Monday..Sunday containing `week` (or today, if omitted)."""
    anchor = week or datetime.now(timezone.utc).date()
    monday = anchor - timedelta(days=anchor.isoweekday() - 1)
    return monday, monday + timedelta(days=6)


def _board_label(shift: Shift, accepted_count: int) -> str:
    """The staffing board's richer, presentation-only vocabulary — computed
    from `status` + counts at read time, never stored (Section 7)."""
    if shift.status == ShiftStatus.CANCELLED:
        return "Cancelled"
    if shift.status == ShiftStatus.UNFILLED:
        return "Unfilled"
    if shift.status == ShiftStatus.PENDING_ACCEPTANCE:
        return "Pending Acceptance"
    if shift.status == ShiftStatus.CONFIRMED:
        return "Fully Staffed" if accepted_count >= shift.max_staff else "Confirmed"
    return "Needs Staff"


def _to_response(shift: Shift, db: Session, current_user: User) -> ShiftResponse:
    accepted = count_assignments(db, shift.id, AssignmentStatus.ACCEPTED)
    offered = count_assignments(db, shift.id, AssignmentStatus.OFFERED)

    # Populated for an Employee caller only: which of *their own*
    # assignment rows this shift is on, and its status — without this, a
    # client has no way to call POST/DELETE /assignments/{id} for a shift
    # it only knows about via this endpoint. Manager/Admin callers get
    # null here; they act on assignments via the candidates/assign flow,
    # which already returns ids directly.
    my_assignment_id = None
    my_assignment_status = None
    if current_user.role == UserRole.EMPLOYEE:
        my_assignment = db.scalar(
            select(ShiftAssignment).where(
                ShiftAssignment.shift_id == shift.id,
                ShiftAssignment.employee_id == current_user.id,
            )
        )
        if my_assignment is not None:
            my_assignment_id = my_assignment.id
            my_assignment_status = my_assignment.status

    # Who's actually on this shift — the roster's per-employee chips
    # (MGR-04) and "coworkers rostered" (EMP-04) both need this.
    accepted_rows = db.execute(
        select(User.id, User.email)
        .join(ShiftAssignment, ShiftAssignment.employee_id == User.id)
        .where(
            ShiftAssignment.shift_id == shift.id,
            ShiftAssignment.status == AssignmentStatus.ACCEPTED,
        )
    ).all()
    accepted_employees = [AssignedEmployee(id=row.id, email=row.email) for row in accepted_rows]

    return ShiftResponse(
        id=shift.id,
        location_id=shift.location_id,
        date=shift.date,
        start_time=shift.start_time,
        end_time=shift.end_time,
        min_staff=shift.min_staff,
        max_staff=shift.max_staff,
        status=shift.status,
        roster_locked_at=shift.roster_locked_at,
        created_by=shift.created_by,
        created_at=shift.created_at,
        accepted_count=accepted,
        offered_count=offered,
        board_label=_board_label(shift, accepted),
        accepted_employees=accepted_employees,
        my_assignment_id=my_assignment_id,
        my_assignment_status=my_assignment_status,
    )


@router.post("/shifts", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
def create_shift(
    payload: ShiftCreate,
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ShiftResponse:
    if db.get(Location, payload.location_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    if not user_can_access_location(db, current_user, payload.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this location"
        )

    shift = Shift(
        location_id=payload.location_id,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        min_staff=payload.min_staff,
        max_staff=payload.max_staff,
        status=ShiftStatus.OPEN,
        created_by=current_user.id,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return _to_response(shift, db, current_user)


@router.get("/shifts", response_model=list[ShiftResponse])
def list_shifts(
    location_id: uuid.UUID | None = Query(default=None),
    week: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShiftResponse]:
    week_start, week_end = _week_range(week)

    if current_user.role in (UserRole.MANAGER, UserRole.ADMIN):
        if location_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="location_id is required"
            )
        if not user_can_access_location(db, current_user, location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this location"
            )
        stmt = select(Shift).where(
            Shift.location_id == location_id, Shift.date >= week_start, Shift.date <= week_end
        )
    else:
        # Employees see only shifts they have an assignment on — never the
        # full board (Section 8: "Employee (own assignments only)").
        stmt = (
            select(Shift)
            .join(ShiftAssignment, ShiftAssignment.shift_id == Shift.id)
            .where(
                ShiftAssignment.employee_id == current_user.id,
                Shift.date >= week_start,
                Shift.date <= week_end,
            )
        )
        if location_id is not None:
            stmt = stmt.where(Shift.location_id == location_id)

    stmt = stmt.order_by(Shift.date, Shift.start_time)
    shifts = list(db.scalars(stmt).all())
    return [_to_response(shift, db, current_user) for shift in shifts]


@router.get("/shifts/{shift_id}/candidates", response_model=list[CandidateResponse])
def get_candidates(
    shift_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[CandidateResponse]:
    shift = db.get(Shift, shift_id)
    if shift is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    if not user_can_access_location(db, current_user, shift.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this location"
        )

    pool = eligible_employees_for_shift(db, shift, assigned_employee_ids(db, shift.id))

    responses = []
    for employee in pool:
        availability = db.scalar(
            select(Availability).where(
                Availability.employee_id == employee.id, Availability.date == shift.date
            )
        )
        responses.append(
            CandidateResponse(
                employee_id=employee.id,
                email=employee.email,
                available_start_time=availability.start_time,
                available_end_time=availability.end_time,
                available_since=availability.created_at,
            )
        )
    return responses


@router.get("/roster", response_model=list[ShiftResponse])
def get_roster(
    location_id: uuid.UUID = Query(...),
    week: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShiftResponse]:
    """Shifts where roster_locked_at IS NOT NULL for the week — not simply
    status == confirmed, so a shift being topped up after confirmation
    stays on the roster (Section 10)."""
    if not user_can_access_location(db, current_user, location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this location"
        )

    week_start, week_end = _week_range(week)
    stmt = (
        select(Shift)
        .where(
            Shift.location_id == location_id,
            Shift.date >= week_start,
            Shift.date <= week_end,
            Shift.roster_locked_at.is_not(None),
        )
        .order_by(Shift.date, Shift.start_time)
    )
    shifts = list(db.scalars(stmt).all())
    return [_to_response(shift, db, current_user) for shift in shifts]
