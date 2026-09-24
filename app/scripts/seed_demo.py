"""Seed a clean, presentable set of demo data for showcasing the MVP.

Unlike the E2E suite (which deliberately uses disposable, timestamped
`e2e-<ts>@example.com` accounts so runs never collide), this is meant to be
run once against a fresh database and looked at by a human — multiple
stores, each with its own manager and set of employees, all with readable
emails. This also makes location scoping trivial to demo: sign in as
Chatswood's manager and Parramatta's shifts/staff simply aren't there.

Every employee gets a wide same-day availability window seeded up front, so
live in the demo, assigning a shift shows several eligible candidates
immediately rather than needing availability set up on stage.

Writes directly to the DB (like seed_admin.py) rather than going through the
API, so it isn't subject to the login rate limiter and doesn't need a
running server. Safe to re-run, including after adding a new store to
STORES below: it's a no-op for anything that already exists.

Usage:
    python -m app.scripts.seed_demo
"""
import random
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.employee_location import EmployeeLocation
from app.models.location import Location
from app.models.manager_location import ManagerLocation
from app.models.availability import Availability
from app.models.shift import Shift, ShiftStatus
from app.models.shift_assignment import AssignmentStatus, ShiftAssignment
from app.models.time_entry import TimeEntry, TimeEntryFlag
from app.models.user import User, UserRole

DEMO_PASSWORD = "DemoPass123!"
ADMIN_EMAIL = "admin.demo@briscoes.demo"

# How much shift/assignment/time-entry history to backfill per store, for the
# manager dashboard's charts (fill rate, hours, overtime, offer outcomes,
# weekday distribution) to have something real to aggregate.
HISTORY_WEEKS_BACK = 8
FUTURE_DAYS = 2

SHIFT_TEMPLATES = [
    {"start": time(8, 0), "end": time(14, 0), "min_staff": 2, "max_staff": 3},
    {"start": time(14, 0), "end": time(20, 0), "min_staff": 2, "max_staff": 4},
]

# One admin oversees every store (admin.demo, above) — everything below is
# per-store, which is exactly the boundary a manager account can't cross.
STORES = [
    {
        "name": "Briscoes Botany Downs",
        "address": "588 Chapel Rd, Botany Downs, Auckland 2013",
        "timezone": "Pacific/Auckland",
        "manager": "manager.jordan@briscoes.demo",
        "employees": [
            "employee.alex@briscoes.demo",
            "employee.priya@briscoes.demo",
            "employee.sam@briscoes.demo",
            "employee.maria@briscoes.demo",
            "employee.ben@briscoes.demo",
        ],
    },
    {
        "name": "Briscoes Wellington",
        "address": "119 Vivian St, Te Aro, Wellington 6011",
        "timezone": "Pacific/Auckland",
        "manager": "manager.taylor@briscoes.demo",
        "employees": [
            "employee.noah@briscoes.demo",
            "employee.grace@briscoes.demo",
            "employee.liam@briscoes.demo",
            "employee.zoe@briscoes.demo",
        ],
    },
    {
        "name": "Briscoes Christchurch",
        "address": "128 Colombo St, Sydenham, Christchurch 8023",
        "timezone": "Pacific/Auckland",
        "manager": "manager.morgan@briscoes.demo",
        "employees": [
            "employee.ruby@briscoes.demo",
            "employee.finn@briscoes.demo",
            "employee.ivy@briscoes.demo",
        ],
    },
]


def _get_or_create_user(db, email: str, role: UserRole, home_location_id=None) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        return user
    user = User(
        email=email,
        hashed_password=hash_password(DEMO_PASSWORD),
        role=role,
        home_location_id=home_location_id,
    )
    db.add(user)
    db.flush()  # get user.id without a full commit
    return user


def _get_or_create_location(db, store: dict) -> Location:
    location = db.query(Location).filter(Location.name == store["name"]).first()
    if location is not None:
        print(f"Location already exists: {store['name']}")
        return location
    location = Location(name=store["name"], address=store["address"], timezone=store["timezone"])
    db.add(location)
    db.flush()
    print(f"Created location: {store['name']} ({store['timezone']})")
    return location


def _seed_shift_history(
    db, rng: random.Random, location: Location, manager: User, employees: list[User]
) -> tuple[int, int, int]:
    """Backfill shifts/assignments/time entries for one location, from
    HISTORY_WEEKS_BACK weeks ago through FUTURE_DAYS ahead. Idempotent at
    the location level: if this location already has any Shift, it's
    assumed to have been fully seeded already and is skipped entirely.
    """
    if db.query(Shift).filter(Shift.location_id == location.id).first() is not None:
        print(f"Shift history already exists for {location.name}, skipping")
        return 0, 0, 0

    tz = ZoneInfo(location.timezone)
    today = date.today()
    shift_total = assignment_total = time_entry_total = 0
    live_entry_created = False

    day = today - timedelta(weeks=HISTORY_WEEKS_BACK)
    while day <= today + timedelta(days=FUTURE_DAYS):
        is_past = day < today
        # Sundays run a single shorter shift — gives the weekday-distribution
        # chart real variation instead of a flat line.
        templates = SHIFT_TEMPLATES if day.weekday() != 6 else SHIFT_TEMPLATES[:1]

        for template in templates:
            naive_start = datetime.combine(day, template["start"])
            naive_end = datetime.combine(day, template["end"])
            aware_start = naive_start.replace(tzinfo=tz)
            aware_end = naive_end.replace(tzinfo=tz)

            pool = employees[:]
            rng.shuffle(pool)

            status: ShiftStatus
            roster_locked_at = None
            accepted_employees: list[User] = []
            rejected_employee: User | None = None
            withdrawn_employee: User | None = None

            if not is_past:
                # Still being staffed — no outcome to seed yet.
                status = ShiftStatus.OPEN if rng.random() < 0.45 else ShiftStatus.PENDING_ACCEPTANCE
            else:
                outcome = rng.random()
                if outcome < 0.10:
                    status = ShiftStatus.CANCELLED
                    if pool:
                        withdrawn_employee = pool[0]
                elif outcome < 0.25:
                    status = ShiftStatus.UNFILLED
                    accepted_count = min(rng.randint(0, max(template["min_staff"] - 1, 0)), len(pool))
                    accepted_employees = pool[:accepted_count]
                else:
                    status = ShiftStatus.CONFIRMED
                    roster_locked_at = (aware_start - timedelta(days=2)).astimezone(timezone.utc)
                    accepted_count = min(rng.randint(template["min_staff"], template["max_staff"]), len(pool))
                    accepted_employees = pool[:accepted_count]
                    remaining = pool[accepted_count:]
                    if remaining and rng.random() < 0.35:
                        rejected_employee = remaining[0]

            shift = Shift(
                location_id=location.id,
                date=day,
                start_time=template["start"],
                end_time=template["end"],
                min_staff=template["min_staff"],
                max_staff=template["max_staff"],
                status=status,
                roster_locked_at=roster_locked_at,
                created_by=manager.id,
            )
            db.add(shift)
            db.flush()  # need shift.id for the assignments/time entries below
            shift_total += 1

            if status == ShiftStatus.PENDING_ACCEPTANCE:
                offered_employee = pool[0]
                db.add(ShiftAssignment(
                    shift_id=shift.id,
                    employee_id=offered_employee.id,
                    status=AssignmentStatus.OFFERED,
                    offered_by=manager.id,
                    shift_starts_at=naive_start,
                    shift_ends_at=naive_end,
                ))
                assignment_total += 1

            if withdrawn_employee is not None:
                offered_at = (aware_start - timedelta(days=1)).astimezone(timezone.utc)
                db.add(ShiftAssignment(
                    shift_id=shift.id,
                    employee_id=withdrawn_employee.id,
                    status=AssignmentStatus.WITHDRAWN,
                    offered_by=manager.id,
                    offered_at=offered_at,
                    responded_at=offered_at + timedelta(hours=2),
                    shift_starts_at=naive_start,
                    shift_ends_at=naive_end,
                ))
                assignment_total += 1

            if rejected_employee is not None:
                offered_at = (aware_start - timedelta(days=2)).astimezone(timezone.utc)
                db.add(ShiftAssignment(
                    shift_id=shift.id,
                    employee_id=rejected_employee.id,
                    status=AssignmentStatus.REJECTED,
                    offered_by=manager.id if rng.random() < 0.7 else None,
                    offered_at=offered_at,
                    responded_at=offered_at + timedelta(hours=3),
                    shift_starts_at=naive_start,
                    shift_ends_at=naive_end,
                ))
                assignment_total += 1

            for employee in accepted_employees:
                offered_at = (aware_start - timedelta(days=rng.randint(2, 5))).astimezone(timezone.utc)
                responded_at = offered_at + timedelta(hours=rng.randint(1, 12))
                db.add(ShiftAssignment(
                    shift_id=shift.id,
                    employee_id=employee.id,
                    status=AssignmentStatus.ACCEPTED,
                    offered_by=manager.id if rng.random() < 0.8 else None,
                    offered_at=offered_at,
                    responded_at=responded_at,
                    shift_starts_at=naive_start,
                    shift_ends_at=naive_end,
                ))
                assignment_total += 1

                clock_in = aware_start + timedelta(minutes=rng.randint(-10, 25))
                clock_out = aware_end + timedelta(minutes=rng.randint(-10, 30))
                if clock_out <= clock_in:
                    clock_out = clock_in + timedelta(hours=4)

                if clock_in < aware_start - timedelta(minutes=15):
                    flag = TimeEntryFlag.EARLY_START
                elif clock_out > aware_end + timedelta(minutes=15):
                    flag = TimeEntryFlag.AFTER_SHIFT_END
                else:
                    flag = TimeEntryFlag.NONE

                db.add(TimeEntry(
                    employee_id=employee.id,
                    shift_id=shift.id,
                    clock_in=clock_in.astimezone(timezone.utc),
                    clock_out=clock_out.astimezone(timezone.utc),
                    location_id=location.id,
                    flag=flag,
                ))
                time_entry_total += 1

        # A weekly unscheduled bonus shift for one employee, so the overtime
        # tile has someone to actually flag.
        if is_past and day.weekday() == 2 and employees:  # Wednesdays
            overtime_employee = employees[0]
            bonus_start = datetime.combine(day, time(21, 0), tzinfo=tz)
            bonus_end = bonus_start + timedelta(hours=5)
            db.add(TimeEntry(
                employee_id=overtime_employee.id,
                shift_id=None,
                clock_in=bonus_start.astimezone(timezone.utc),
                clock_out=bonus_end.astimezone(timezone.utc),
                location_id=location.id,
                flag=TimeEntryFlag.UNSCHEDULED,
            ))
            time_entry_total += 1

        if day == today and not live_entry_created and employees:
            # Someone currently clocked in, for the "clocked in right now"
            # dashboard tile.
            live_employee = employees[-1]
            db.add(TimeEntry(
                employee_id=live_employee.id,
                shift_id=None,
                clock_in=datetime.now(timezone.utc) - timedelta(minutes=45),
                clock_out=None,
                location_id=location.id,
                flag=TimeEntryFlag.NONE,
            ))
            time_entry_total += 1
            live_entry_created = True

        day += timedelta(days=1)

    return shift_total, assignment_total, time_entry_total


def seed_demo() -> None:
    db = SessionLocal()
    try:
        admin = _get_or_create_user(db, ADMIN_EMAIL, UserRole.ADMIN)

        # Wide same-day + next-day availability window, same reasoning as
        # the module docstring: no live data entry needed before a shift can
        # be assigned on stage.
        today = date.today()
        window_days = [today, today + timedelta(days=1)]
        history_totals: dict[str, tuple[int, int, int]] = {}

        for store in STORES:
            location = _get_or_create_location(db, store)

            manager = _get_or_create_user(db, store["manager"], UserRole.MANAGER, home_location_id=location.id)
            if db.get(ManagerLocation, {"manager_id": manager.id, "location_id": location.id}) is None:
                db.add(ManagerLocation(manager_id=manager.id, location_id=location.id))

            employee_users: list[User] = []
            for email in store["employees"]:
                employee = _get_or_create_user(db, email, UserRole.EMPLOYEE, home_location_id=location.id)
                employee_users.append(employee)
                if db.get(EmployeeLocation, {"employee_id": employee.id, "location_id": location.id}) is None:
                    db.add(EmployeeLocation(employee_id=employee.id, location_id=location.id, is_primary=True))

                for day in window_days:
                    existing = (
                        db.query(Availability)
                        .filter(Availability.employee_id == employee.id, Availability.date == day)
                        .first()
                    )
                    if existing is None:
                        db.add(
                            Availability(
                                employee_id=employee.id,
                                date=day,
                                is_available=True,
                                start_time=time(6, 0),
                                end_time=time(22, 0),
                            )
                        )

            # Seeded once per store name, so re-runs produce the same history
            # rather than piling up more of it (the location-level existence
            # check in _seed_shift_history is the actual idempotency guard;
            # this just keeps that history reproducible).
            rng = random.Random(f"shift-history:{store['name']}")
            history_totals[store["name"]] = _seed_shift_history(db, rng, location, manager, employee_users)

        db.commit()

        print("\nDemo data ready.")
        print(f"  Admin: {ADMIN_EMAIL}  (sees every store)")
        for store in STORES:
            print(f"\n  {store['name']} ({store['timezone']})")
            print(f"    Manager:   {store['manager']}")
            print("    Employees:")
            for email in store["employees"]:
                print(f"      {email}")
            shifts, assignments, time_entries = history_totals[store["name"]]
            print(f"    History:   {shifts} shifts, {assignments} assignments, {time_entries} time entries")
        print(f"\n  Password (all accounts): {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
