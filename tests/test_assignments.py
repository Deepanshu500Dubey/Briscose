from datetime import datetime, time, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.shift_assignment import AssignmentStatus, ShiftAssignment
from app.models.user import UserRole
from tests.helpers import (
    assign_employee,
    assign_manager,
    auth_headers,
    create_location,
    create_shift,
    create_user,
    login,
    set_availability,
)


def _today():
    return datetime.now(timezone.utc).date()


def _offer(client, shift_id, employee_id, mgr_tokens):
    return client.post(
        f"/shifts/{shift_id}/assignments",
        json={"employee_id": str(employee_id)},
        headers=auth_headers(mgr_tokens),
    )


def _get_shift(client, location_id, shift_id, tokens):
    shifts = client.get(f"/shifts?location_id={location_id}", headers=auth_headers(tokens)).json()
    return next(s for s in shifts if s["id"] == str(shift_id))


# ---------------------------------------------------------------------------
# Offer creation
# ---------------------------------------------------------------------------


def test_offer_creates_pending_acceptance_status(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=1)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)

    response = _offer(client, shift.id, employee.id, mgr_tokens)

    assert response.status_code == 201
    assert response.json()["status"] == "offered"
    shift_state = _get_shift(client, location.id, shift.id, mgr_tokens)
    assert shift_state["status"] == "pending_acceptance"


def test_offer_rejects_duplicate_employee(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=2)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)

    first = _offer(client, shift.id, employee.id, mgr_tokens)
    second = _offer(client, shift.id, employee.id, mgr_tokens)

    assert first.status_code == 201
    assert second.status_code == 409


def test_offer_rejects_when_would_exceed_max_staff(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=1)
    emp1 = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, emp1, location)
    emp2 = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, emp2, location)
    mgr_tokens = login(client, manager.email)

    first = _offer(client, shift.id, emp1.id, mgr_tokens)
    second = _offer(client, shift.id, emp2.id, mgr_tokens)

    assert first.status_code == 201
    assert second.status_code == 409


def test_offer_rejects_employee_not_scoped_to_location(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)  # no location assignment
    mgr_tokens = login(client, manager.email)

    response = _offer(client, shift.id, employee.id, mgr_tokens)

    assert response.status_code == 400


def test_manager_cannot_offer_at_unmanaged_location(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    other_manager = create_user(db_session, role=UserRole.MANAGER)
    shift = create_shift(db_session, location, other_manager, on=_today())
    manager = create_user(db_session, role=UserRole.MANAGER)  # not assigned to `location`
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    tokens = login(client, manager.email)

    response = _offer(client, shift.id, employee.id, tokens)

    assert response.status_code == 403


def test_manager_can_manually_assign_outside_availability(
    client: TestClient, db_session: Session
) -> None:
    """The Section 0 override default: a manager may assign any staff
    member scoped to the location, even with no matching availability."""
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    # Deliberately no availability row for this employee/date.
    tokens = login(client, manager.email)

    response = _offer(client, shift.id, employee.id, tokens)

    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Accept / confirm / roster_locked_at
# ---------------------------------------------------------------------------


def test_accept_confirms_shift_and_sets_roster_locked_at(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=1)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)
    offer = _offer(client, shift.id, employee.id, mgr_tokens).json()

    emp_tokens = login(client, employee.email)
    response = client.post(f"/assignments/{offer['id']}/accept", headers=auth_headers(emp_tokens))

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    shift_state = _get_shift(client, location.id, shift.id, mgr_tokens)
    assert shift_state["status"] == "confirmed"
    assert shift_state["board_label"] == "Fully Staffed"
    assert shift_state["roster_locked_at"] is not None


def test_accept_wrong_employee_forbidden(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    other_employee = create_user(db_session, role=UserRole.EMPLOYEE)
    mgr_tokens = login(client, manager.email)
    offer = _offer(client, shift.id, employee.id, mgr_tokens).json()

    other_tokens = login(client, other_employee.email)
    response = client.post(f"/assignments/{offer['id']}/accept", headers=auth_headers(other_tokens))

    assert response.status_code == 403


def test_accept_non_offered_assignment_rejected(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)
    offer = _offer(client, shift.id, employee.id, mgr_tokens).json()
    emp_tokens = login(client, employee.email)
    client.post(f"/assignments/{offer['id']}/accept", headers=auth_headers(emp_tokens))

    # Already accepted — accepting again should be rejected.
    response = client.post(f"/assignments/{offer['id']}/accept", headers=auth_headers(emp_tokens))

    assert response.status_code == 400


def test_accept_rejects_when_would_exceed_max_staff(
    client: TestClient, db_session: Session
) -> None:
    """Exercises the accept-time guard directly (independent of the
    offer-time guard) by pre-seeding two outstanding offers on a
    max_staff=1 shift and accepting both."""
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=1)
    emp1 = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, emp1, location)
    emp2 = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, emp2, location)

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
    db_session.add_all([a1, a2])
    db_session.commit()
    db_session.refresh(a1)
    db_session.refresh(a2)

    emp1_tokens = login(client, emp1.email)
    emp2_tokens = login(client, emp2.email)

    r1 = client.post(f"/assignments/{a1.id}/accept", headers=auth_headers(emp1_tokens))
    r2 = client.post(f"/assignments/{a2.id}/accept", headers=auth_headers(emp2_tokens))

    assert r1.status_code == 200
    assert r2.status_code == 409


def test_exclusion_constraint_blocks_overlapping_accepted_shifts(
    client: TestClient, db_session: Session
) -> None:
    """The DB-level line of defense (Section 11): even bypassing the
    app-level overlap check by pre-seeding both offers directly, accepting
    the second overlapping shift is rejected by the real Postgres
    exclusion constraint."""
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)

    shift1 = create_shift(
        db_session, location, manager, on=_today(),
        start_time=time(8, 0), end_time=time(16, 0), min_staff=1, max_staff=1,
    )
    shift2 = create_shift(
        db_session, location, manager, on=_today(),
        start_time=time(12, 0), end_time=time(20, 0), min_staff=1, max_staff=1,
    )

    a1 = ShiftAssignment(
        shift_id=shift1.id, employee_id=employee.id, status=AssignmentStatus.OFFERED,
        offered_by=manager.id,
        shift_starts_at=datetime.combine(shift1.date, shift1.start_time),
        shift_ends_at=datetime.combine(shift1.date, shift1.end_time),
    )
    a2 = ShiftAssignment(
        shift_id=shift2.id, employee_id=employee.id, status=AssignmentStatus.OFFERED,
        offered_by=manager.id,
        shift_starts_at=datetime.combine(shift2.date, shift2.start_time),
        shift_ends_at=datetime.combine(shift2.date, shift2.end_time),
    )
    db_session.add_all([a1, a2])
    db_session.commit()
    db_session.refresh(a1)
    db_session.refresh(a2)

    tokens = login(client, employee.email)
    r1 = client.post(f"/assignments/{a1.id}/accept", headers=auth_headers(tokens))
    r2 = client.post(f"/assignments/{a2.id}/accept", headers=auth_headers(tokens))

    assert r1.status_code == 200
    assert r2.status_code == 409


def test_offer_blocked_when_employee_has_overlapping_accepted_shift(
    client: TestClient, db_session: Session
) -> None:
    """The app-level pre-check (Section 11): don't even dangle an offer
    that can't be honoured."""
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)

    shift1 = create_shift(
        db_session, location, manager, on=_today(),
        start_time=time(8, 0), end_time=time(16, 0), min_staff=1, max_staff=1,
    )
    shift2 = create_shift(
        db_session, location, manager, on=_today(),
        start_time=time(12, 0), end_time=time(20, 0), min_staff=1, max_staff=1,
    )
    mgr_tokens = login(client, manager.email)
    offer1 = _offer(client, shift1.id, employee.id, mgr_tokens).json()
    emp_tokens = login(client, employee.email)
    client.post(f"/assignments/{offer1['id']}/accept", headers=auth_headers(emp_tokens))

    response = _offer(client, shift2.id, employee.id, mgr_tokens)

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Reject / auto-reassignment / unfilled
# ---------------------------------------------------------------------------


def test_reject_triggers_auto_reassignment_to_next_in_pool(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=1)

    emp1 = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, emp1, location)
    set_availability(db_session, emp1, on=_today())
    emp2 = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, emp2, location)
    set_availability(
        db_session, emp2, on=_today(), created_at=datetime.now(timezone.utc) + timedelta(seconds=1)
    )

    mgr_tokens = login(client, manager.email)
    offer1 = _offer(client, shift.id, emp1.id, mgr_tokens).json()
    emp1_tokens = login(client, emp1.email)

    response = client.post(f"/assignments/{offer1['id']}/reject", headers=auth_headers(emp1_tokens))

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    new_assignment = (
        db_session.query(ShiftAssignment)
        .filter(ShiftAssignment.shift_id == shift.id, ShiftAssignment.employee_id == emp2.id)
        .one()
    )
    assert new_assignment.status == AssignmentStatus.OFFERED
    assert new_assignment.offered_by is None  # system-driven


def test_reject_with_empty_pool_marks_shift_unfilled(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=1)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)
    offer = _offer(client, shift.id, employee.id, mgr_tokens).json()
    emp_tokens = login(client, employee.email)

    client.post(f"/assignments/{offer['id']}/reject", headers=auth_headers(emp_tokens))

    shift_state = _get_shift(client, location.id, shift.id, mgr_tokens)
    assert shift_state["status"] == "unfilled"
    assert shift_state["board_label"] == "Unfilled"

    notifications = client.get("/notifications", headers=auth_headers(mgr_tokens)).json()
    assert any(n["type"] == "shift_unfilled" for n in notifications)


def test_reject_wrong_employee_forbidden(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    other = create_user(db_session, role=UserRole.EMPLOYEE)
    mgr_tokens = login(client, manager.email)
    offer = _offer(client, shift.id, employee.id, mgr_tokens).json()

    other_tokens = login(client, other.email)
    response = client.post(f"/assignments/{offer['id']}/reject", headers=auth_headers(other_tokens))

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Top-up on a confirmed shift — the worked example from Section 10
# ---------------------------------------------------------------------------


def test_topup_offer_on_confirmed_shift_preserves_roster_locked_at(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=2)
    mgr_tokens = login(client, manager.email)

    emp1 = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, emp1, location)
    offer1 = _offer(client, shift.id, emp1.id, mgr_tokens).json()
    emp1_tokens = login(client, emp1.email)
    accept1 = client.post(f"/assignments/{offer1['id']}/accept", headers=auth_headers(emp1_tokens))
    assert accept1.status_code == 200

    confirmed = _get_shift(client, location.id, shift.id, mgr_tokens)
    assert confirmed["status"] == "confirmed"
    assert confirmed["board_label"] == "Confirmed"  # 1 of 2 max_staff — not "Fully Staffed" yet
    roster_locked_at_1 = confirmed["roster_locked_at"]
    assert roster_locked_at_1 is not None

    # Top up toward max_staff=2 on the already-confirmed shift.
    emp2 = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, emp2, location)
    offer2 = _offer(client, shift.id, emp2.id, mgr_tokens)
    assert offer2.status_code == 201

    topped_up = _get_shift(client, location.id, shift.id, mgr_tokens)
    assert topped_up["status"] == "pending_acceptance"
    assert topped_up["roster_locked_at"] == roster_locked_at_1  # untouched by the top-up offer

    # And still on the published roster throughout — never hidden by the
    # transient pending_acceptance status (this is exactly what
    # roster_locked_at exists to guarantee).
    roster = client.get(f"/roster?location_id={location.id}", headers=auth_headers(mgr_tokens)).json()
    assert str(shift.id) in {s["id"] for s in roster}

    emp2_tokens = login(client, emp2.email)
    accept2 = client.post(f"/assignments/{offer2.json()['id']}/accept", headers=auth_headers(emp2_tokens))
    assert accept2.status_code == 200

    final = _get_shift(client, location.id, shift.id, mgr_tokens)
    assert final["status"] == "confirmed"
    assert final["accepted_count"] == 2
    assert final["board_label"] == "Fully Staffed"
    assert final["roster_locked_at"] == roster_locked_at_1


# ---------------------------------------------------------------------------
# Withdraw
# ---------------------------------------------------------------------------


def test_withdraw_offered_assignment(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)
    offer = _offer(client, shift.id, employee.id, mgr_tokens).json()

    response = client.request(
        "DELETE", f"/assignments/{offer['id']}", headers=auth_headers(mgr_tokens)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"


def test_withdraw_accepted_requires_confirm(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=1)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)
    offer = _offer(client, shift.id, employee.id, mgr_tokens).json()
    emp_tokens = login(client, employee.email)
    client.post(f"/assignments/{offer['id']}/accept", headers=auth_headers(emp_tokens))

    without_confirm = client.request(
        "DELETE", f"/assignments/{offer['id']}", headers=auth_headers(mgr_tokens)
    )
    assert without_confirm.status_code == 400

    with_confirm = client.request(
        "DELETE",
        f"/assignments/{offer['id']}",
        json={"confirm": True},
        headers=auth_headers(mgr_tokens),
    )
    assert with_confirm.status_code == 200
    assert with_confirm.json()["status"] == "withdrawn"


def test_withdraw_accepted_below_min_reopens_and_drops_off_roster(
    client: TestClient, db_session: Session
) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today(), min_staff=1, max_staff=1)
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)
    offer = _offer(client, shift.id, employee.id, mgr_tokens).json()
    emp_tokens = login(client, employee.email)
    client.post(f"/assignments/{offer['id']}/accept", headers=auth_headers(emp_tokens))

    roster_before = client.get(
        f"/roster?location_id={location.id}", headers=auth_headers(mgr_tokens)
    ).json()
    assert str(shift.id) in {s["id"] for s in roster_before}

    client.request(
        "DELETE",
        f"/assignments/{offer['id']}",
        json={"confirm": True},
        headers=auth_headers(mgr_tokens),
    )

    reopened = _get_shift(client, location.id, shift.id, mgr_tokens)
    assert reopened["roster_locked_at"] is None
    assert reopened["status"] == "unfilled"  # no one else eligible

    roster_after = client.get(
        f"/roster?location_id={location.id}", headers=auth_headers(mgr_tokens)
    ).json()
    assert str(shift.id) not in {s["id"] for s in roster_after}

    notifications = client.get("/notifications", headers=auth_headers(mgr_tokens)).json()
    assert any(n["type"] == "shift_dropped_below_minimum" for n in notifications)


def test_withdraw_already_withdrawn_rejected(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)
    offer = _offer(client, shift.id, employee.id, mgr_tokens).json()
    client.request("DELETE", f"/assignments/{offer['id']}", headers=auth_headers(mgr_tokens))

    response = client.request(
        "DELETE", f"/assignments/{offer['id']}", headers=auth_headers(mgr_tokens)
    )

    assert response.status_code == 400


def test_employee_cannot_withdraw_assignment(client: TestClient, db_session: Session) -> None:
    location = create_location(db_session)
    manager = create_user(db_session, role=UserRole.MANAGER)
    assign_manager(db_session, manager, location)
    shift = create_shift(db_session, location, manager, on=_today())
    employee = create_user(db_session, role=UserRole.EMPLOYEE)
    assign_employee(db_session, employee, location)
    mgr_tokens = login(client, manager.email)
    offer = _offer(client, shift.id, employee.id, mgr_tokens).json()

    emp_tokens = login(client, employee.email)
    response = client.request(
        "DELETE", f"/assignments/{offer['id']}", headers=auth_headers(emp_tokens)
    )

    assert response.status_code == 403
