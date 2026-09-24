"""Assignment core business logic (project blueprint, Section 10 & 11).

Every function here that mutates state expects `shift` to already be locked
via get_shift_for_update() by the caller — that lock is what serializes
concurrent accept/reject/assign calls against the same shift (Section 11).
Callers own the transaction boundary (commit/rollback); these functions
flush but never commit.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.availability import Availability
from app.models.employee_location import EmployeeLocation
from app.models.shift import Shift, ShiftStatus
from app.models.shift_assignment import AssignmentStatus, ShiftAssignment
from app.models.user import User
from app.services.notification_service import notify, notify_managers_of_location


def get_shift_for_update(db: Session, shift_id: uuid.UUID) -> Shift:
    shift = db.execute(
        select(Shift).where(Shift.id == shift_id).with_for_update()
    ).scalar_one_or_none()
    if shift is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    return shift


def count_assignments(db: Session, shift_id: uuid.UUID, assignment_status: AssignmentStatus) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(ShiftAssignment)
            .where(
                ShiftAssignment.shift_id == shift_id,
                ShiftAssignment.status == assignment_status,
            )
        )
        or 0
    )


def assigned_employee_ids(db: Session, shift_id: uuid.UUID) -> set[uuid.UUID]:
    """Every employee already touched by this shift, in any status — never
    re-offer to someone who already offered/accepted/rejected/withdrew."""
    return set(
        db.scalars(
            select(ShiftAssignment.employee_id).where(ShiftAssignment.shift_id == shift_id)
        ).all()
    )


def eligible_employees_for_shift(
    db: Session, shift: Shift, exclude_employee_ids: set[uuid.UUID]
) -> list[User]:
    """Employees available for the shift's full time window, eligible for
    its location, not already assigned in any status — ordered by
    `availability.created_at` ASC, `employee.id` ASC (Section 10's "first
    to submit availability" ordering rule).
    """
    employee_at_location = select(EmployeeLocation.employee_id).where(
        EmployeeLocation.employee_id == User.id,
        EmployeeLocation.location_id == shift.location_id,
    ).exists()

    stmt = (
        select(User)
        .join(Availability, Availability.employee_id == User.id)
        .where(
            Availability.date == shift.date,
            Availability.is_available.is_(True),
            Availability.start_time <= shift.start_time,
            Availability.end_time >= shift.end_time,
            (User.home_location_id == shift.location_id) | employee_at_location,
        )
        .order_by(Availability.created_at.asc(), User.id.asc())
    )
    if exclude_employee_ids:
        stmt = stmt.where(User.id.not_in(exclude_employee_ids))

    return list(db.scalars(stmt).all())


def _naive_shift_bounds(shift: Shift) -> tuple[datetime, datetime]:
    return (
        datetime.combine(shift.date, shift.start_time),
        datetime.combine(shift.date, shift.end_time),
    )


def employee_has_overlapping_accepted_shift(
    db: Session, employee_id: uuid.UUID, shift: Shift
) -> bool:
    starts_at, ends_at = _naive_shift_bounds(shift)
    stmt = select(ShiftAssignment.id).where(
        ShiftAssignment.employee_id == employee_id,
        ShiftAssignment.status == AssignmentStatus.ACCEPTED,
        ShiftAssignment.shift_starts_at < ends_at,
        ShiftAssignment.shift_ends_at > starts_at,
    )
    return db.scalar(stmt) is not None


def recompute_shift_status(db: Session, shift: Shift) -> None:
    """Must be called with `shift` already locked via get_shift_for_update().

    `status` answers "what should the staffing board show right now" and is
    allowed to move between pending_acceptance and confirmed as offers come
    and go; `roster_locked_at` answers "has this shift ever satisfied the
    roster rule" and is one-way except for the single regression path below
    (project blueprint, Section 10).
    """
    accepted = count_assignments(db, shift.id, AssignmentStatus.ACCEPTED)
    offered = count_assignments(db, shift.id, AssignmentStatus.OFFERED)

    if offered > 0:
        shift.status = ShiftStatus.PENDING_ACCEPTANCE
        # roster_locked_at untouched — a shift already on the roster stays there.
    elif accepted >= shift.min_staff:
        shift.status = ShiftStatus.CONFIRMED
        if shift.roster_locked_at is None:
            shift.roster_locked_at = datetime.now(timezone.utc)
    else:
        pool = eligible_employees_for_shift(db, shift, assigned_employee_ids(db, shift.id))
        shift.status = ShiftStatus.UNFILLED if not pool else ShiftStatus.OPEN
        if shift.roster_locked_at is not None:
            # Only reachable via a manager withdrawing an ACCEPTED
            # assignment (DELETE /assignments/{id}) and dropping the
            # accepted count below min_staff.
            shift.roster_locked_at = None
            notify_managers_of_location(
                db, shift.location_id, "shift_dropped_below_minimum", shift.id
            )
        if shift.status == ShiftStatus.UNFILLED:
            notify_managers_of_location(db, shift.location_id, "shift_unfilled", shift.id)


def create_offer(
    db: Session, shift: Shift, employee: User, offered_by: User | None
) -> ShiftAssignment:
    """Create an `offered` assignment for `employee` on the given
    (already-locked) shift. A manager may target any employee scoped to the
    shift's location — including ones outside the eligible pool, which is
    the deliberate "override availability" path (Section 0) — but never an
    employee who already has an overlapping ACCEPTED shift, so we don't
    dangle an offer that can't be honoured (Section 11).
    """
    if shift.status == ShiftStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shift is cancelled")

    if employee.id in assigned_employee_ids(db, shift.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This employee already has an assignment for this shift",
        )

    accepted = count_assignments(db, shift.id, AssignmentStatus.ACCEPTED)
    offered = count_assignments(db, shift.id, AssignmentStatus.OFFERED)
    if accepted + offered >= shift.max_staff:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shift already has max_staff accepted or outstanding offers",
        )

    if employee_has_overlapping_accepted_shift(db, employee.id, shift):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee already has an accepted shift that overlaps this time window",
        )

    starts_at, ends_at = _naive_shift_bounds(shift)
    assignment = ShiftAssignment(
        shift_id=shift.id,
        employee_id=employee.id,
        status=AssignmentStatus.OFFERED,
        offered_by=offered_by.id if offered_by else None,
        shift_starts_at=starts_at,
        shift_ends_at=ends_at,
    )
    db.add(assignment)
    db.flush()
    recompute_shift_status(db, shift)
    notify(db, employee.id, "offer", shift.id)
    return assignment


def accept_assignment(db: Session, assignment: ShiftAssignment, shift: Shift) -> None:
    """`shift` must already be locked via get_shift_for_update(). Re-checks
    max_staff under that lock — the primary concurrency guard (Section 11).
    The overlap exclusion constraint is the second, DB-level line of
    defense in case the employee accepted a conflicting shift elsewhere
    between the offer and this accept.
    """
    accepted = count_assignments(db, shift.id, AssignmentStatus.ACCEPTED)
    if accepted >= shift.max_staff:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Shift is already fully staffed"
        )

    assignment.status = AssignmentStatus.ACCEPTED
    assignment.responded_at = datetime.now(timezone.utc)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This overlaps with another accepted shift",
        ) from exc

    recompute_shift_status(db, shift)


def reject_assignment(
    db: Session, assignment: ShiftAssignment, shift: Shift
) -> ShiftAssignment | None:
    """`shift` must already be locked via get_shift_for_update(). Returns
    the newly created system-offer, if the reassignment pool wasn't empty.
    """
    assignment.status = AssignmentStatus.REJECTED
    assignment.responded_at = datetime.now(timezone.utc)
    db.flush()

    pool = eligible_employees_for_shift(db, shift, assigned_employee_ids(db, shift.id))
    new_offer = None
    if pool:
        next_employee = pool[0]
        starts_at, ends_at = _naive_shift_bounds(shift)
        new_offer = ShiftAssignment(
            shift_id=shift.id,
            employee_id=next_employee.id,
            status=AssignmentStatus.OFFERED,
            offered_by=None,  # system-driven auto-reassignment
            shift_starts_at=starts_at,
            shift_ends_at=ends_at,
        )
        db.add(new_offer)
        db.flush()
        notify(db, next_employee.id, "offer", shift.id)

    recompute_shift_status(db, shift)
    return new_offer


def withdraw_assignment(db: Session, assignment: ShiftAssignment, shift: Shift, confirm: bool) -> None:
    """`shift` must already be locked via get_shift_for_update()."""
    if assignment.status in (AssignmentStatus.REJECTED, AssignmentStatus.WITHDRAWN):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This assignment is already rejected or withdrawn",
        )

    if assignment.status == AssignmentStatus.ACCEPTED and not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Withdrawing an accepted assignment can drop the shift below "
                "min_staff and un-publish it from the roster. Resend with "
                "confirm=true to proceed."
            ),
        )

    assignment.status = AssignmentStatus.WITHDRAWN
    assignment.responded_at = datetime.now(timezone.utc)
    db.flush()

    notify(db, assignment.employee_id, "withdrawn", shift.id)
    recompute_shift_status(db, shift)
