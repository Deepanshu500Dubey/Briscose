"""Assignment endpoints — offer, accept, reject, withdraw (project
blueprint, Section 8 & 10)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role, user_can_access_location
from app.db.session import get_db
from app.models.shift_assignment import AssignmentStatus, ShiftAssignment
from app.models.user import User, UserRole
from app.schemas.assignment import (
    AssignmentResponse,
    CreateAssignmentRequest,
    WithdrawAssignmentRequest,
)
from app.services.assignment_service import (
    accept_assignment,
    create_offer,
    get_shift_for_update,
    reject_assignment,
    withdraw_assignment,
)

router = APIRouter(tags=["assignments"])


@router.post(
    "/shifts/{shift_id}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def offer_shift(
    shift_id: uuid.UUID,
    payload: CreateAssignmentRequest,
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ShiftAssignment:
    shift = get_shift_for_update(db, shift_id)
    if not user_can_access_location(db, current_user, shift.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this location"
        )

    employee = db.get(User, payload.employee_id)
    if employee is None or employee.role != UserRole.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    if not user_can_access_location(db, employee, shift.location_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee is not assigned to this shift's location",
        )

    assignment = create_offer(db, shift, employee, offered_by=current_user)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/assignments/{assignment_id}/accept", response_model=AssignmentResponse)
def accept(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShiftAssignment:
    assignment = db.get(ShiftAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if assignment.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your assignment")
    if assignment.status != AssignmentStatus.OFFERED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This assignment is not currently offered"
        )

    shift = get_shift_for_update(db, assignment.shift_id)
    accept_assignment(db, assignment, shift)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/assignments/{assignment_id}/reject", response_model=AssignmentResponse)
def reject(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShiftAssignment:
    assignment = db.get(ShiftAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if assignment.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your assignment")
    if assignment.status != AssignmentStatus.OFFERED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This assignment is not currently offered"
        )

    shift = get_shift_for_update(db, assignment.shift_id)
    reject_assignment(db, assignment, shift)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.delete("/assignments/{assignment_id}", response_model=AssignmentResponse)
def withdraw(
    assignment_id: uuid.UUID,
    payload: WithdrawAssignmentRequest = WithdrawAssignmentRequest(),
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ShiftAssignment:
    assignment = db.get(ShiftAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    shift = get_shift_for_update(db, assignment.shift_id)
    if not user_can_access_location(db, current_user, shift.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this location"
        )

    withdraw_assignment(db, assignment, shift, confirm=payload.confirm)
    db.commit()
    db.refresh(assignment)
    return assignment
