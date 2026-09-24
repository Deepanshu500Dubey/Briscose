"""Availability endpoints (project blueprint, Sections 7, 8 & 10).

Employees set their own availability over a rolling 14-day window (today
through today+13, recomputed on every request — there's no stored "window"
row, it's always derived from the current date). Managers and Admins can
read — never write — an employee's availability, scoped by shared location.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, manager_shares_location_with_employee
from app.db.session import get_db
from app.models.availability import Availability
from app.models.user import User, UserRole
from app.schemas.availability import AvailabilityResponse, AvailabilityUpsertRequest

router = APIRouter(prefix="/availability", tags=["availability"])

ROLLING_WINDOW_DAYS = 14


def _rolling_window() -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    return today, today + timedelta(days=ROLLING_WINDOW_DAYS - 1)


def _assert_can_view(current_user: User, employee_id: uuid.UUID, db: Session) -> None:
    if current_user.id == employee_id or current_user.role == UserRole.ADMIN:
        return
    if current_user.role == UserRole.MANAGER and manager_shares_location_with_employee(
        db, current_user, employee_id
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not permitted to view this employee's availability",
    )


@router.get("", response_model=list[AvailabilityResponse])
def get_availability(
    employee_id: uuid.UUID | None = Query(default=None),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Availability]:
    target_id = employee_id or current_user.id
    _assert_can_view(current_user, target_id, db)

    window_start, window_end = _rolling_window()
    range_start = from_ or window_start
    range_end = to or window_end
    if range_start > range_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="'from' must not be after 'to'"
        )

    stmt = (
        select(Availability)
        .where(
            Availability.employee_id == target_id,
            Availability.date >= range_start,
            Availability.date <= range_end,
        )
        .order_by(Availability.date)
    )
    return list(db.scalars(stmt).all())


@router.patch("", response_model=list[AvailabilityResponse])
def upsert_availability(
    payload: AvailabilityUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Availability]:
    """Bulk upsert — one call saves the whole rolling-window grid.

    Employees only ever write their own availability; there's no
    `employee_id` in the request body by design (see the project
    blueprint, Section 9's self-scoping rule).
    """
    if not payload.days:
        return []

    window_start, window_end = _rolling_window()
    out_of_window = [day.date for day in payload.days if not (window_start <= day.date <= window_end)]
    if out_of_window:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"date(s) outside the editable rolling window "
                f"({window_start.isoformat()}..{window_end.isoformat()}): "
                + ", ".join(d.isoformat() for d in out_of_window)
            ),
        )

    values = [
        {
            "employee_id": current_user.id,
            "date": day.date,
            "is_available": day.is_available,
            "start_time": day.start_time,
            "end_time": day.end_time,
        }
        for day in payload.days
    ]

    # INSERT ... ON CONFLICT (employee_id, date) DO UPDATE, with `created_at`
    # deliberately absent from the SET clause: editing a day's time range
    # must never re-queue that employee ahead of or behind their original
    # submission for auto-reassignment ordering (Section 10).
    insert_stmt = pg_insert(Availability).values(values)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[Availability.employee_id, Availability.date],
        set_={
            "is_available": insert_stmt.excluded.is_available,
            "start_time": insert_stmt.excluded.start_time,
            "end_time": insert_stmt.excluded.end_time,
            "updated_at": func.now(),
        },
    )
    db.execute(upsert_stmt)
    db.commit()

    dates = [day.date for day in payload.days]
    result_stmt = (
        select(Availability)
        .where(Availability.employee_id == current_user.id, Availability.date.in_(dates))
        .order_by(Availability.date)
    )
    return list(db.scalars(result_stmt).all())
