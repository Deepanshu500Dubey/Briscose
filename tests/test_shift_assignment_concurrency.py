"""Real concurrency test for the accept-time max_staff guard
(project blueprint, Section 11 & 13).

This deliberately does NOT use the shared db_session/client fixtures —
their SAVEPOINT-based isolation lives on a single connection, which can't
demonstrate cross-connection row locking. This talks to the real dev
database directly through independent connections/threads, and cleans up
its own rows since it isn't wrapped in the usual auto-rollback fixture.
"""
import threading
import uuid
from datetime import datetime, time, timezone

from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.db.session import engine
from app.models.location import Location
from app.models.shift import Shift, ShiftStatus
from app.models.shift_assignment import AssignmentStatus, ShiftAssignment
from app.models.user import User, UserRole
from app.services.assignment_service import accept_assignment, get_shift_for_update


def test_concurrent_accepts_never_exceed_max_staff() -> None:
    SessionFactory = sessionmaker(bind=engine)
    setup_session = SessionFactory()

    location = manager = emp1 = emp2 = shift = None
    try:
        location = Location(
            name=f"Concurrency Store {uuid.uuid4().hex}",
            address="1 Test St",
            timezone="Australia/Sydney",
        )
        setup_session.add(location)
        setup_session.flush()

        manager = User(
            email=f"conc-mgr-{uuid.uuid4().hex}@example.com",
            hashed_password=hash_password("correct-horse"),
            role=UserRole.MANAGER,
        )
        emp1 = User(
            email=f"conc-emp1-{uuid.uuid4().hex}@example.com",
            hashed_password=hash_password("correct-horse"),
            role=UserRole.EMPLOYEE,
        )
        emp2 = User(
            email=f"conc-emp2-{uuid.uuid4().hex}@example.com",
            hashed_password=hash_password("correct-horse"),
            role=UserRole.EMPLOYEE,
        )
        setup_session.add_all([manager, emp1, emp2])
        setup_session.flush()

        today = datetime.now(timezone.utc).date()
        shift = Shift(
            location_id=location.id,
            date=today,
            start_time=time(8, 0),
            end_time=time(16, 0),
            min_staff=1,
            max_staff=1,
            status=ShiftStatus.OPEN,
            created_by=manager.id,
        )
        setup_session.add(shift)
        setup_session.flush()

        starts_at = datetime.combine(shift.date, shift.start_time)
        ends_at = datetime.combine(shift.date, shift.end_time)
        a1 = ShiftAssignment(
            shift_id=shift.id, employee_id=emp1.id, status=AssignmentStatus.OFFERED,
            offered_by=manager.id, shift_starts_at=starts_at, shift_ends_at=ends_at,
        )
        a2 = ShiftAssignment(
            shift_id=shift.id, employee_id=emp2.id, status=AssignmentStatus.OFFERED,
            offered_by=manager.id, shift_starts_at=starts_at, shift_ends_at=ends_at,
        )
        setup_session.add_all([a1, a2])
        setup_session.commit()

        shift_id, a1_id, a2_id = shift.id, a1.id, a2.id
        results: dict[str, str] = {}

        def try_accept(assignment_id: uuid.UUID, key: str) -> None:
            session = SessionFactory()
            try:
                locked_shift = get_shift_for_update(session, shift_id)
                assignment = session.get(ShiftAssignment, assignment_id)
                try:
                    accept_assignment(session, assignment, locked_shift)
                    session.commit()
                    results[key] = "accepted"
                except Exception as exc:  # noqa: BLE001 - want to record any failure
                    session.rollback()
                    results[key] = f"rejected: {exc}"
            finally:
                session.close()

        t1 = threading.Thread(target=try_accept, args=(a1_id, "t1"))
        t2 = threading.Thread(target=try_accept, args=(a2_id, "t2"))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert set(results.keys()) == {"t1", "t2"}, f"a thread never finished: {results}"
        accepted_count = sum(1 for outcome in results.values() if outcome == "accepted")
        assert accepted_count == 1, f"expected exactly one accept to win, got: {results}"

        verify_session = SessionFactory()
        try:
            final_accepted = (
                verify_session.query(ShiftAssignment)
                .filter(
                    ShiftAssignment.shift_id == shift_id,
                    ShiftAssignment.status == AssignmentStatus.ACCEPTED,
                )
                .count()
            )
            assert final_accepted == 1
        finally:
            verify_session.close()
    finally:
        setup_session.rollback()
        cleanup = SessionFactory()
        try:
            if shift is not None:
                cleanup.query(ShiftAssignment).filter(
                    ShiftAssignment.shift_id == shift.id
                ).delete()
                cleanup.query(Shift).filter(Shift.id == shift.id).delete()
            user_ids = [u.id for u in (manager, emp1, emp2) if u is not None]
            if user_ids:
                cleanup.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
            if location is not None:
                cleanup.query(Location).filter(Location.id == location.id).delete()
            cleanup.commit()
        finally:
            cleanup.close()
            setup_session.close()
