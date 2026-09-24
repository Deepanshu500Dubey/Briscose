"""Dashboard endpoints — quick operational snapshot for managers/admins."""
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.location import Location
from app.models.manager_location import ManagerLocation
from app.models.shift import Shift, ShiftStatus
from app.models.shift_assignment import AssignmentStatus, ShiftAssignment
from app.models.time_entry import TimeEntry
from app.models.user import User, UserRole
from app.services.timesheet_service import WEEKLY_OVERTIME_HOURS

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _location_filter(db: Session, current_user: User) -> list | None:
    """Return the list of location UUIDs the caller may see, or None for admin
    (meaning: no restriction).  An empty list means the manager has no
    assigned locations — queries will return zero rows."""
    if current_user.role == UserRole.ADMIN:
        return None
    return list(
        db.scalars(
            select(ManagerLocation.location_id).where(
                ManagerLocation.manager_id == current_user.id
            )
        ).all()
    )


def _week_bounds(anchor: date) -> tuple[date, date]:
    """Monday … Sunday for the ISO week that contains *anchor*."""
    monday = anchor - timedelta(days=anchor.isoweekday() - 1)
    return monday, monday + timedelta(days=6)


# ---------------------------------------------------------------------------
# 1. GET /dashboard/today
# ---------------------------------------------------------------------------

@router.get("/today")
def today_summary(
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """Operational snapshot for today, scoped to the caller's locations."""
    now = datetime.now(timezone.utc)
    today = now.date()
    now_time = now.timetz()

    location_filter = _location_filter(db, current_user)

    def _shift_base():
        stmt = select(Shift).where(Shift.date == today)
        if location_filter is not None:
            stmt = stmt.where(Shift.location_id.in_(location_filter))
        return stmt

    shifts_today = db.scalar(
        select(func.count()).select_from(_shift_base().subquery())
    )

    open_shifts_today = db.scalar(
        select(func.count()).select_from(
            _shift_base().where(Shift.status == "open").subquery()
        )
    )

    today_shift_ids = select(Shift.id).where(Shift.date == today)
    if location_filter is not None:
        today_shift_ids = today_shift_ids.where(Shift.location_id.in_(location_filter))

    pending_offers = db.scalar(
        select(func.count(ShiftAssignment.id)).where(
            ShiftAssignment.shift_id.in_(today_shift_ids),
            ShiftAssignment.status == AssignmentStatus.OFFERED,
        )
    )

    clocked_in_stmt = select(func.count(TimeEntry.id)).where(TimeEntry.clock_out.is_(None))
    if location_filter is not None:
        clocked_in_stmt = clocked_in_stmt.where(TimeEntry.location_id.in_(location_filter))
    clocked_in_now = db.scalar(clocked_in_stmt)

    rostered_now_stmt = (
        select(func.count(ShiftAssignment.id))
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .where(
            Shift.date == today,
            Shift.start_time <= now_time,
            Shift.end_time >= now_time,
            ShiftAssignment.status == AssignmentStatus.ACCEPTED,
        )
    )
    if location_filter is not None:
        rostered_now_stmt = rostered_now_stmt.where(Shift.location_id.in_(location_filter))
    rostered_now = db.scalar(rostered_now_stmt)

    return {
        "shifts_today": shifts_today or 0,
        "open_shifts_today": open_shifts_today or 0,
        "pending_offers": pending_offers or 0,
        "clocked_in_now": clocked_in_now or 0,
        "rostered_now": rostered_now or 0,
    }


# ---------------------------------------------------------------------------
# 2. GET /dashboard/staffing-by-location?days=7
# ---------------------------------------------------------------------------

@router.get("/staffing-by-location")
def staffing_by_location(
    days: int = Query(default=7, ge=1, le=365),
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Per-location shift count broken down by status, over the next *days* days."""
    today = datetime.now(timezone.utc).date()
    until = today + timedelta(days=days - 1)

    location_filter = _location_filter(db, current_user)

    # One row per (location_id, location_name, status) with its count.
    stmt = (
        select(
            Shift.location_id,
            Location.name.label("location_name"),
            Shift.status,
            func.count(Shift.id).label("count"),
        )
        .join(Location, Location.id == Shift.location_id)
        .where(Shift.date >= today, Shift.date <= until)
        .group_by(Shift.location_id, Location.name, Shift.status)
        .order_by(Location.name, Shift.status)
    )
    if location_filter is not None:
        stmt = stmt.where(Shift.location_id.in_(location_filter))

    rows = db.execute(stmt).all()

    # Roll up into {location_id, location_name, by_status: {status: count}, total}.
    by_loc: dict = {}
    for row in rows:
        lid = str(row.location_id)
        if lid not in by_loc:
            by_loc[lid] = {
                "location_id": lid,
                "location_name": row.location_name,
                "by_status": {s.value: 0 for s in ShiftStatus},
                "total": 0,
            }
        by_loc[lid]["by_status"][row.status.value] += row.count
        by_loc[lid]["total"] += row.count

    return list(by_loc.values())


# ---------------------------------------------------------------------------
# 3. GET /dashboard/hours-by-employee?week=<date>
# ---------------------------------------------------------------------------

@router.get("/hours-by-employee")
def hours_by_employee(
    week: date | None = Query(default=None),
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Per-employee worked vs rostered hours for the ISO week containing *week*
    (defaults to the current week).  Only employees with at least one accepted
    assignment or closed time entry in that week appear in the result."""
    anchor = week or datetime.now(timezone.utc).date()
    week_start, week_end = _week_bounds(anchor)

    location_filter = _location_filter(db, current_user)

    # --- Worked hours: sum of closed TimeEntry durations, in hours ----------
    # Cast to float seconds then divide — works on PostgreSQL via EXTRACT.
    worked_stmt = (
        select(
            TimeEntry.employee_id,
            func.sum(
                func.extract("epoch", TimeEntry.clock_out - TimeEntry.clock_in)
            ).label("worked_seconds"),
        )
        .where(
            TimeEntry.clock_out.is_not(None),
            func.date(TimeEntry.clock_in) >= week_start,
            func.date(TimeEntry.clock_in) <= week_end,
        )
        .group_by(TimeEntry.employee_id)
    )
    if location_filter is not None:
        worked_stmt = worked_stmt.where(TimeEntry.location_id.in_(location_filter))

    worked_map: dict = {
        str(r.employee_id): float(r.worked_seconds or 0) / 3600
        for r in db.execute(worked_stmt).all()
    }

    # --- Rostered hours: use shift_starts_at / shift_ends_at (plain datetime
    #     columns, no tz) — avoids the Time → float cast awkwardness ----------
    rostered_stmt2 = (
        select(
            ShiftAssignment.employee_id,
            func.sum(
                func.extract(
                    "epoch",
                    ShiftAssignment.shift_ends_at - ShiftAssignment.shift_starts_at,
                )
            ).label("rostered_seconds"),
        )
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .where(
            ShiftAssignment.status == AssignmentStatus.ACCEPTED,
            Shift.date >= week_start,
            Shift.date <= week_end,
        )
        .group_by(ShiftAssignment.employee_id)
    )
    if location_filter is not None:
        rostered_stmt2 = rostered_stmt2.where(Shift.location_id.in_(location_filter))

    rostered_map = {
        str(r.employee_id): round(float(r.rostered_seconds or 0) / 3600, 2)
        for r in db.execute(rostered_stmt2).all()
    }

    # --- Resolve employee emails for display ---------------------------------
    all_employee_ids_str = set(worked_map) | set(rostered_map)
    if not all_employee_ids_str:
        return []

    all_employee_ids = [uuid.UUID(eid) for eid in all_employee_ids_str]
    email_map = {
        str(u.id): u.email
        for u in db.scalars(select(User).where(User.id.in_(all_employee_ids))).all()
    }

    result = []
    for eid in sorted(all_employee_ids_str):
        worked = round(worked_map.get(eid, 0.0), 2)
        rostered = rostered_map.get(eid, 0.0)
        result.append(
            {
                "employee_id": eid,
                "email": email_map.get(eid, ""),
                "week_start": week_start.isoformat(),
                "worked_hours": worked,
                "rostered_hours": rostered,
                "delta_hours": round(worked - rostered, 2),
            }
        )
    return result


# ---------------------------------------------------------------------------
# 4. GET /dashboard/shifts-by-weekday?days=30
# ---------------------------------------------------------------------------

@router.get("/shifts-by-weekday")
def shifts_by_weekday(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Shift count grouped by ISO day-of-week (1=Mon … 7=Sun) over the past
    *days* days up to and including today."""
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=days - 1)

    location_filter = _location_filter(db, current_user)

    # EXTRACT(ISODOW …) returns 1=Monday … 7=Sunday in PostgreSQL.
    dow_col = func.extract("isodow", Shift.date).label("day_of_week")
    stmt = (
        select(dow_col, func.count(Shift.id).label("count"))
        .where(Shift.date >= since, Shift.date <= today)
        .group_by(dow_col)
        .order_by(dow_col)
    )
    if location_filter is not None:
        stmt = stmt.where(Shift.location_id.in_(location_filter))

    _DOW_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    rows = db.execute(stmt).all()
    # Ensure all 7 days appear even when count is zero.
    count_by_dow = {int(r.day_of_week): r.count for r in rows}
    return [
        {
            "day_of_week": dow,
            "day_name": _DOW_NAMES[dow - 1],
            "count": count_by_dow.get(dow, 0),
        }
        for dow in range(1, 8)
    ]


# ---------------------------------------------------------------------------
# 5. GET /dashboard/offer-outcomes?weeks=8
# ---------------------------------------------------------------------------

@router.get("/offer-outcomes")
def offer_outcomes(
    weeks: int = Query(default=8, ge=1, le=52),
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Per ISO-week breakdown of ShiftAssignment counts by status, plus a
    separate *auto_reassignment* count for rows where offered_by is null."""
    today = datetime.now(timezone.utc).date()
    week_start, _ = _week_bounds(today)
    since = week_start - timedelta(weeks=weeks - 1)

    location_filter = _location_filter(db, current_user)

    iso_year = func.extract("isoyear", Shift.date).label("iso_year")
    iso_week = func.extract("week", Shift.date).label("iso_week")

    stmt = (
        select(
            iso_year,
            iso_week,
            ShiftAssignment.status,
            func.count(ShiftAssignment.id).label("count"),
            func.sum(
                case((ShiftAssignment.offered_by.is_(None), 1), else_=0)
            ).label("auto_reassignment_count"),
        )
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .where(Shift.date >= since, Shift.date <= today)
        .group_by(iso_year, iso_week, ShiftAssignment.status)
        .order_by(iso_year, iso_week, ShiftAssignment.status)
    )
    if location_filter is not None:
        stmt = stmt.where(Shift.location_id.in_(location_filter))

    rows = db.execute(stmt).all()

    # Roll up into one dict per (iso_year, iso_week).
    by_week: dict = {}
    for r in rows:
        key = (int(r.iso_year), int(r.iso_week))
        if key not in by_week:
            by_week[key] = {
                "iso_year": key[0],
                "iso_week": key[1],
                "by_status": {s.value: 0 for s in AssignmentStatus},
                "auto_reassignments": 0,
                "total": 0,
            }
        by_week[key]["by_status"][r.status.value] += r.count
        by_week[key]["auto_reassignments"] += r.auto_reassignment_count or 0
        by_week[key]["total"] += r.count

    return [by_week[k] for k in sorted(by_week)]


# ---------------------------------------------------------------------------
# 6. GET /dashboard/overtime?week=<date>
# ---------------------------------------------------------------------------

@router.get("/overtime")
def overtime(
    week: date | None = Query(default=None),
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Per-employee total worked hours for the ISO week and whether they
    exceed WEEKLY_OVERTIME_HOURS (imported from timesheet_service)."""
    anchor = week or datetime.now(timezone.utc).date()
    week_start, week_end = _week_bounds(anchor)

    location_filter = _location_filter(db, current_user)

    stmt = (
        select(
            TimeEntry.employee_id,
            func.sum(
                func.extract("epoch", TimeEntry.clock_out - TimeEntry.clock_in)
            ).label("worked_seconds"),
        )
        .where(
            TimeEntry.clock_out.is_not(None),
            func.date(TimeEntry.clock_in) >= week_start,
            func.date(TimeEntry.clock_in) <= week_end,
        )
        .group_by(TimeEntry.employee_id)
        .order_by(func.sum(
            func.extract("epoch", TimeEntry.clock_out - TimeEntry.clock_in)
        ).desc())
    )
    if location_filter is not None:
        stmt = stmt.where(TimeEntry.location_id.in_(location_filter))

    rows = db.execute(stmt).all()
    if not rows:
        return []

    emp_ids = [r.employee_id for r in rows]
    email_map = {
        u.id: u.email
        for u in db.scalars(select(User).where(User.id.in_(emp_ids))).all()
    }

    result = []
    for r in rows:
        total_hours = round((r.worked_seconds or 0) / 3600, 2)
        result.append(
            {
                "employee_id": str(r.employee_id),
                "email": email_map.get(r.employee_id, ""),
                "week_start": week_start.isoformat(),
                "total_hours": total_hours,
                "overtime_threshold": WEEKLY_OVERTIME_HOURS,
                "over_weekly_limit": total_hours > WEEKLY_OVERTIME_HOURS,
            }
        )
    return result


# ---------------------------------------------------------------------------
# 7. GET /dashboard/fill-rate-trend?weeks=8
# ---------------------------------------------------------------------------

@router.get("/fill-rate-trend")
def fill_rate_trend(
    weeks: int = Query(default=8, ge=1, le=52),
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Per ISO-week fill rate: % of shifts with status=confirmed out of all
    shifts in that week."""
    today = datetime.now(timezone.utc).date()
    week_start, _ = _week_bounds(today)
    since = week_start - timedelta(weeks=weeks - 1)

    location_filter = _location_filter(db, current_user)

    iso_year = func.extract("isoyear", Shift.date).label("iso_year")
    iso_week = func.extract("week", Shift.date).label("iso_week")

    stmt = (
        select(
            iso_year,
            iso_week,
            func.count(Shift.id).label("total"),
            func.sum(
                case((Shift.status == ShiftStatus.CONFIRMED, 1), else_=0)
            ).label("confirmed"),
        )
        .where(Shift.date >= since, Shift.date <= today)
        .group_by(iso_year, iso_week)
        .order_by(iso_year, iso_week)
    )
    if location_filter is not None:
        stmt = stmt.where(Shift.location_id.in_(location_filter))

    rows = db.execute(stmt).all()
    result = []
    for r in rows:
        total = r.total or 0
        confirmed = r.confirmed or 0
        result.append(
            {
                "iso_year": int(r.iso_year),
                "iso_week": int(r.iso_week),
                "total_shifts": total,
                "confirmed_shifts": confirmed,
                "fill_rate_pct": round(confirmed / total * 100, 1) if total else 0.0,
            }
        )
    return result


# ---------------------------------------------------------------------------
# 8. GET /dashboard/attention
# ---------------------------------------------------------------------------

@router.get("/attention")
def attention_items(
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Actionable items for the next 48 hours, scoped to the caller's locations.

    Three item types are returned (mixed list, ordered: understaffed first,
    then stale offers, then absent employees):

    * ``open_or_understaffed`` — shifts in the next 48 h that are ``open``,
      ``unfilled``, or have ``accepted_count < min_staff``.
    * ``offer_pending_long`` — OFFERED assignments whose ``offered_at`` is
      more than 24 h ago.
    * ``rostered_not_clocked_in`` — employees whose accepted shift is
      currently in progress but who have no open (clock_out IS NULL) time
      entry at that shift's location.

    Each item carries a ``type``, a short human-readable ``label``, and the
    IDs needed to navigate to the relevant screen.
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    now_time = now.timetz()
    cutoff_48h = (now + timedelta(hours=48)).date()
    stale_offer_cutoff = now - timedelta(hours=24)

    location_filter = _location_filter(db, current_user)

    items: list[dict] = []

    # ------------------------------------------------------------------
    # 1. Open or understaffed shifts (next 48 h)
    # ------------------------------------------------------------------
    # accepted_count per shift — scalar subquery so we avoid a full GROUP BY
    # on the outer query.
    accepted_subq = (
        select(func.count(ShiftAssignment.id))
        .where(
            ShiftAssignment.shift_id == Shift.id,
            ShiftAssignment.status == AssignmentStatus.ACCEPTED,
        )
        .correlate(Shift)
        .scalar_subquery()
    )

    understaffed_stmt = (
        select(Shift, accepted_subq.label("accepted_count"))
        .where(
            Shift.date >= today,
            Shift.date <= cutoff_48h,
            Shift.status != ShiftStatus.CANCELLED,
            # open/unfilled are always understaffed by definition; for
            # confirmed/pending_acceptance we surface them if accepted < min.
            (
                Shift.status.in_([ShiftStatus.OPEN, ShiftStatus.UNFILLED])
                | (accepted_subq < Shift.min_staff)
            ),
        )
        .order_by(Shift.date, Shift.start_time)
    )
    if location_filter is not None:
        understaffed_stmt = understaffed_stmt.where(
            Shift.location_id.in_(location_filter)
        )

    for row in db.execute(understaffed_stmt).all():
        shift = row[0]
        accepted = row[1] or 0
        needs = shift.min_staff - accepted
        items.append(
            {
                "type": "open_or_understaffed",
                "label": (
                    f"Shift on {shift.date} needs {needs} more staff "
                    f"({accepted}/{shift.min_staff} filled)"
                ),
                "shift_id": str(shift.id),
                "location_id": str(shift.location_id),
                "date": shift.date.isoformat(),
                "start_time": shift.start_time.strftime("%H:%M:%S"),
                "end_time": shift.end_time.strftime("%H:%M:%S"),
                "accepted_count": accepted,
                "min_staff": shift.min_staff,
            }
        )

    # ------------------------------------------------------------------
    # 2. Offers pending for more than 24 h
    # ------------------------------------------------------------------
    stale_stmt = (
        select(ShiftAssignment)
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .where(
            ShiftAssignment.status == AssignmentStatus.OFFERED,
            ShiftAssignment.offered_at < stale_offer_cutoff,
        )
        .order_by(ShiftAssignment.offered_at)
    )
    if location_filter is not None:
        stale_stmt = stale_stmt.where(Shift.location_id.in_(location_filter))

    for assignment in db.scalars(stale_stmt).all():
        hours_pending = (now - assignment.offered_at).total_seconds() / 3600
        items.append(
            {
                "type": "offer_pending_long",
                "label": (
                    f"Offer pending for {hours_pending:.0f} h "
                    f"— employee has not responded"
                ),
                "assignment_id": str(assignment.id),
                "shift_id": str(assignment.shift_id),
                "employee_id": str(assignment.employee_id),
                "offered_at": assignment.offered_at.isoformat(),
                "hours_pending": round(hours_pending, 1),
            }
        )

    # ------------------------------------------------------------------
    # 3. Rostered now but not clocked in
    # ------------------------------------------------------------------
    # Employees with an ACCEPTED shift that is currently in progress.
    rostered_now_stmt = (
        select(ShiftAssignment, Shift)
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .where(
            Shift.date == today,
            Shift.start_time <= now_time,
            Shift.end_time >= now_time,
            ShiftAssignment.status == AssignmentStatus.ACCEPTED,
        )
        .order_by(ShiftAssignment.employee_id)
    )
    if location_filter is not None:
        rostered_now_stmt = rostered_now_stmt.where(
            Shift.location_id.in_(location_filter)
        )

    rostered_rows = db.execute(rostered_now_stmt).all()

    if rostered_rows:
        # Build set of employee_ids that currently have an open time entry
        # at the relevant locations.
        rostered_location_ids = {row[1].location_id for row in rostered_rows}
        clocked_in_stmt = select(TimeEntry.employee_id).where(
            TimeEntry.clock_out.is_(None),
            TimeEntry.location_id.in_(rostered_location_ids),
        )
        clocked_in_ids = set(db.scalars(clocked_in_stmt).all())

        for assignment, shift in rostered_rows:
            if assignment.employee_id not in clocked_in_ids:
                items.append(
                    {
                        "type": "rostered_not_clocked_in",
                        "label": "Employee rostered now but has not clocked in",
                        "shift_id": str(shift.id),
                        "location_id": str(shift.location_id),
                        "employee_id": str(assignment.employee_id),
                        "shift_start_time": shift.start_time.strftime("%H:%M:%S"),
                        "shift_end_time": shift.end_time.strftime("%H:%M:%S"),
                    }
                )

    return items

