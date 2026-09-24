# Briscoes Crew — Backend (Phase 1 complete)

FastAPI + PostgreSQL + SQLAlchemy + Alembic backend implementing all of Phase 1
from the project blueprint: JWT access tokens with rotating refresh tokens,
role-based + location-scoped authorization, employee availability, the shift
staffing board with offer/accept/reject and auto-reassignment, the weekly
roster, in-app notifications, clock in/out, and timesheets — running under
Docker Compose. Phase 2 (email/SMS, offer expiry, shift swapping, recurring
templates, payroll export, break/overtime enforcement) is deliberately not
built — see the project blueprint, Section 15.

Accounts are **provisioned**, not self-registered: a Manager or Admin creates
every account via `POST /users` (see [Bootstrapping the first admin](#bootstrapping-the-first-admin)
for how the very first one gets created).

## Project setup

1. Copy the environment template and adjust if needed:

   ```bash
   cp .env.example .env
   ```

2. Build and start the stack:

   ```bash
   docker compose up --build
   ```

   This starts two services:
   - `db` — PostgreSQL 16, with a healthcheck and a persistent volume.
   - `app` — the FastAPI application, on `http://localhost:8000`, waiting for `db` to
     be healthy before starting.

## Database migrations

Run once the stack is up:

```bash
docker compose exec app alembic upgrade head
```

To roll back to an empty database:

```bash
docker compose exec app alembic downgrade base
```

## Bootstrapping the first admin

There's no self-signup — `POST /users` requires a Manager or Admin caller, which
is a chicken-and-egg problem for a fresh database. Run this once, directly
against the container, to create the first Admin account:

```bash
docker compose exec app python -m app.scripts.seed_admin admin@example.com "a-strong-password"
```

Safe to re-run: it's a no-op if the email already exists. From there, log in as
that admin, `POST /locations` to create a store, and `POST /users` for
everyone else.

## API

| Method | Path                          | Auth required             | Description                                             |
|--------|-------------------------------|:--------------------------:|----------------------------------------------------------|
| GET    | `/health`                     | No                         | Liveness check — `{"status": "ok"}`                       |
| POST   | `/auth/login`                 | No                         | Exchange email + password for a token pair                |
| POST   | `/auth/refresh`               | No (valid refresh token)   | Rotate a refresh token for a new token pair                |
| POST   | `/auth/logout`                | No (valid refresh token)   | Revoke a refresh token                                     |
| GET    | `/auth/me`                    | Yes (Bearer)               | Return the authenticated user                              |
| PATCH  | `/auth/password`              | Yes (Bearer)               | Change the caller's own password                            |
| POST   | `/users`                      | Yes (Manager, Admin)       | Provision an employee or manager account                   |
| GET    | `/users`                      | Yes (Manager, Admin)       | List staff, filterable by location                          |
| POST   | `/locations`                  | Yes (Admin)                | Create a location                                            |
| GET    | `/locations`                  | Yes (Bearer)               | Locations visible to the caller (role-scoped)               |
| GET    | `/locations/{id}`             | Yes (Bearer)               | A single location, if the caller may access it              |
| GET    | `/availability`               | Yes (Bearer)               | Read availability (self, or a manager's own staff)          |
| PATCH  | `/availability`               | Yes (Bearer)               | Bulk upsert the caller's own rolling-window grid             |
| POST   | `/shifts`                     | Yes (Manager, Admin)       | Create a shift                                              |
| GET    | `/shifts`                     | Yes (Bearer)               | Staffing board (Manager) or own assignments (Employee)       |
| GET    | `/shifts/{id}/candidates`     | Yes (Manager, Admin)       | Eligible-employee pool for a shift                          |
| POST   | `/shifts/{id}/assignments`    | Yes (Manager, Admin)       | Offer the shift to an employee                              |
| POST   | `/assignments/{id}/accept`    | Yes (self)                 | Accept an offer                                             |
| POST   | `/assignments/{id}/reject`    | Yes (self)                 | Reject an offer — triggers auto-reassignment                |
| DELETE | `/assignments/{id}`           | Yes (Manager, Admin)       | Withdraw an offer or (with `confirm`) an accepted assignment |
| GET    | `/roster`                     | Yes (Bearer)               | Published roster for a location + week                      |
| GET    | `/notifications`              | Yes (Bearer)               | The caller's in-app notification feed                        |
| PATCH  | `/notifications/{id}/read`    | Yes (self)                 | Mark a notification read                                     |
| POST   | `/time-entries/clock-in`      | Yes (Employee)             | Clock in                                                     |
| POST   | `/time-entries/clock-out`     | Yes (Employee)             | Clock out                                                    |
| PATCH  | `/time-entries/{id}`          | Yes (Manager, Admin)       | Force-close/correct a forgotten clock-out                    |
| GET    | `/timesheets`                 | Yes (Bearer)               | Per-day + weekly hour rollup (self, or a manager's staff)    |

### Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "correct-horse"}'
```

Returns `200` with `{"access_token": "<jwt>", "refresh_token": "<opaque>",
"token_type": "bearer"}` on success, or `401` on invalid credentials (the
response does not reveal whether the email exists). Access tokens are
short-lived JWTs carrying `role` and `token_version`; refresh tokens are
opaque, stored server-side as a hash only, and revocable.

### Refresh

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh-token>"}'
```

Rotates the refresh token: the presented token is revoked and a new
access/refresh pair is issued. Returns `401` if the token is missing, expired,
already revoked, or unknown — including reuse of a token that was already
rotated or logged out.

### Logout

```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh-token>"}'
```

Revokes the refresh token. Always returns `204`, even if the token was
already invalid — logging out isn't an error from the client's perspective.

### Current user

```bash
curl http://localhost:8000/auth/me -H "Authorization: Bearer <jwt>"
```

Returns `401` if the token is missing, invalid, expired, or was signed before
the user's last credential reset (stale `token_version`). Returns `403` if
the token is valid but the user has been deactivated.

### Change password

```bash
curl -X PATCH http://localhost:8000/auth/password \
  -H "Authorization: Bearer <jwt>" -H "Content-Type: application/json" \
  -d '{"current_password": "correct-horse", "new_password": "a-new-strong-password"}'
```

Bumps `token_version` (every other outstanding access token is rejected
immediately) and revokes every refresh token for the account, then returns
a fresh token pair so the caller isn't logged out by their own request.
Returns `401` if `current_password` is wrong.

### Provision a user

```bash
curl -X POST http://localhost:8000/users \
  -H "Authorization: Bearer <manager-or-admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"email": "employee@example.com", "password": "correct-horse", "role": "employee", "location_ids": ["<location-uuid>"]}'
```

`role` (`employee` | `manager` | `admin`, default `employee`), `home_location_id`,
and `location_ids` are optional. A Manager caller may only provision `employee`
accounts, and only at locations they themselves manage (`403` otherwise); an
Admin may provision any role at any location. `location_ids` immediately creates
the matching `employee_locations`/`manager_locations` rows. Returns `409` on a
duplicate email, `404` if `home_location_id` doesn't exist, `400` if a given
`location_ids` entry doesn't exist. The password hash is never returned by any
endpoint.

### List users

```bash
curl "http://localhost:8000/users?location_id=<uuid>" -H "Authorization: Bearer <manager-or-admin-jwt>"
```

Admins see everyone (optionally filtered to one location); Managers only ever
see users tied to locations they manage, and get `403` if they pass a
`location_id` they don't manage.

### Locations

```bash
curl -X POST http://localhost:8000/locations \
  -H "Authorization: Bearer <admin-jwt>" -H "Content-Type: application/json" \
  -d '{"name": "Example Store", "address": "1 Main St", "timezone": "Australia/Sydney"}'
```

Admin-only — Managers get `403`. `timezone` must be a real IANA name
(`422` otherwise). There's still no update/deactivate endpoint (schema-ready
only, per the blueprint's Phase-2-UI note on Super Admin location
management) — creation was the piece actually blocking an Admin UI.

```bash
curl http://localhost:8000/locations -H "Authorization: Bearer <jwt>"
```

Visibility follows role: Admins see every location; Managers see the
locations they're assigned to (`manager_locations`); Employees see their
home location plus any they're explicitly assigned to
(`employee_locations`). `GET /locations/{id}` additionally checks the
caller can access that specific location, returning `403` if not and `404`
if the location doesn't exist.

### Availability

Employees set their own availability over a rolling 14-day window (today
through today+13, recomputed on every request — there's no stored "window,"
it's always derived from the current date).

```bash
curl -X PATCH http://localhost:8000/availability \
  -H "Authorization: Bearer <employee-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"days": [
        {"date": "2026-08-27", "is_available": true, "start_time": "08:00:00", "end_time": "16:00:00"},
        {"date": "2026-08-28", "is_available": false}
      ]}'
```

One call upserts the whole batch. `start_time`/`end_time` are required when
`is_available` is `true` (and `start_time` must be before `end_time`);
they're ignored (stored as `null`) when `false`. Duplicate dates within one
request, or any date outside the rolling window, are rejected with `422`/`400`
respectively. **Editing a day never changes its `created_at`** — that
timestamp is set once, at first submission, and is exactly what
auto-reassignment ordering reads from (see Shifts & assignments, below).

```bash
curl "http://localhost:8000/availability?employee_id=<uuid>&from=2026-08-27&to=2026-09-09" \
  -H "Authorization: Bearer <jwt>"
```

`employee_id` defaults to the caller. Employees may only read their own
rows; Managers may read any employee's rows at a location they share with
that employee; Admins may read anyone's. `from`/`to` default to the current
rolling window if omitted.

### Shifts & assignments

The highest-risk logic in the app (project blueprint, Section 10 & 11) — a
full walkthrough is worth reading before touching this code.

**Status vocabulary.** `shifts.status` is one of `open`, `pending_acceptance`,
`confirmed`, `unfilled`, `cancelled` — deterministic states with a clear
trigger, recomputed after every offer/accept/reject/withdraw. The richer
staffing-board vocabulary ("Needs Staff", "Fully Staffed", "Pending
Acceptance", "Unfilled") is a `board_label` computed at read time from
`status` + `accepted_count`/`max_staff`, never stored. Every shift response
also carries `accepted_employees` (`[{id, email}]`) — who's actually on it,
for the roster's per-employee chips (MGR-04) and a shift's "coworkers
rostered" (EMP-04); visible to anyone who can see the shift at all.

**`roster_locked_at` vs `status`.** These answer two different questions.
`status` answers "what should the staffing board show right now" — it's
allowed to move between `pending_acceptance` and `confirmed` as offers come
and go (e.g. a manager topping up an already-confirmed shift toward
`max_staff`). `roster_locked_at` answers "has this shift ever satisfied the
roster rule" — set once, the first time `accepted_count >= min_staff`, and
left untouched by later top-up offers. `GET /roster` reads `roster_locked_at
IS NOT NULL`, not `status == confirmed`, so a shift being topped up never
flickers off the published roster. The one path that clears it: a Manager
withdrawing an *accepted* assignment and dropping the count below
`min_staff` (`DELETE /assignments/{id}` with `confirm: true`) — which
reopens the shift and un-publishes it.

**Auto-reassignment ordering.** "First to submit availability" means
`availability.created_at` for that employee/date — the moment they first
said they were free, not the moment they last edited it (see Availability,
above). Ties break on `employee.id`.

```bash
# Manager creates a shift
curl -X POST http://localhost:8000/shifts -H "Authorization: Bearer <manager-jwt>" -H "Content-Type: application/json" \
  -d '{"location_id": "<uuid>", "date": "2026-08-28", "start_time": "12:00:00", "end_time": "20:00:00", "min_staff": 3, "max_staff": 5}'

# See who's eligible (available, scoped to this location, not already assigned)
curl http://localhost:8000/shifts/<shift-id>/candidates -H "Authorization: Bearer <manager-jwt>"

# Offer it
curl -X POST http://localhost:8000/shifts/<shift-id>/assignments -H "Authorization: Bearer <manager-jwt>" -H "Content-Type: application/json" \
  -d '{"employee_id": "<uuid>"}'

# Employee accepts or rejects
curl -X POST http://localhost:8000/assignments/<assignment-id>/accept -H "Authorization: Bearer <employee-jwt>"
curl -X POST http://localhost:8000/assignments/<assignment-id>/reject -H "Authorization: Bearer <employee-jwt>"
```

A Manager may assign any employee scoped to the shift's location — including
someone outside the eligible pool, which is the deliberate "override
availability, with a warning" default (blueprint Section 0) — but never an
employee who already has an overlapping *accepted* shift, so no offer is
ever dangled that can't be honoured. Two independent lines of defense
enforce this: an app-level pre-check at offer time, and a real Postgres
exclusion constraint (`EXCLUDE USING gist`, via `btree_gist`) at accept time
that makes it impossible even under concurrent requests. `max_staff` is
re-checked under a `SELECT ... FOR UPDATE` shift-row lock on every
accept/reject/offer/withdraw, serializing concurrent actions on the same
shift — proven by a real multi-threaded test against independent DB
connections (`tests/test_shift_assignment_concurrency.py`), not just
sequential API calls.

`GET /roster?location_id=&week=` returns the published roster (see
`roster_locked_at` above); `week` is any date within the target week
(default: today), and the response spans that Monday–Sunday.

### Notifications

```bash
curl http://localhost:8000/notifications -H "Authorization: Bearer <jwt>"
curl -X PATCH http://localhost:8000/notifications/<id>/read -H "Authorization: Bearer <jwt>"
```

The in-app feed only — email/SMS is Phase 2. Fired on: an offer (manager- or
system-driven), a withdrawal, a shift going `unfilled`, and a shift dropping
below `min_staff` (the roster-regression case, to the location's managers).

### Clock in/out

Six explicit cases, each with a concrete rule (project blueprint, Section 10)
— never a fallback to "whatever the client sends."

```bash
curl -X POST http://localhost:8000/time-entries/clock-in -H "Authorization: Bearer <employee-jwt>" -H "Content-Type: application/json" -d '{}'
curl -X POST http://localhost:8000/time-entries/clock-out -H "Authorization: Bearer <employee-jwt>"
```

- **Before/after an accepted shift**: within a 15-minute grace window
  (`CLOCK_GRACE_MINUTES`) either side, links with no flag; outside it, still
  links but flags `early_start`/`after_shift_end` for manager review.
- **No accepted shift today**: still allowed — `flag: unscheduled`, attributed
  to the employee's home location (`400` if they have none).
- **Two accepted shifts with a gap between them**: the overlap-prevention
  exclusion constraint guarantees they never overlap, so if "now" matches
  neither window, the response is `409` with `{"choose_shift": [...]}` —
  retry with `{"shift_id": "<uuid>"}` to disambiguate.
- **Already clocked in**: a second clock-in is a soft-success `409` returning
  the existing open entry, not an error — safe for double-taps/multi-device.
- **Clock-out**: always allowed if an entry is open; `409` if not.
- **A forgotten clock-out**: blocks that employee's *next* clock-in forever
  by design (the open-entry check has no expiry) — a Manager at that
  employee's location closes it via `PATCH /time-entries/{id}` with a
  `clock_out` timestamp.

### Timesheets

```bash
curl "http://localhost:8000/timesheets?employee_id=<uuid>&week=2026-08-24" -H "Authorization: Bearer <jwt>"
```

Hours are always computed server-side from `clock_out - clock_in`, never
trusted from the client. Every closed entry counts toward its day's total
regardless of `flag` (an unscheduled/early/late entry is still worked time,
just marked for review); open entries are excluded until closed. Each day
carries `over_daily_limit` (>8h) and the response carries `over_weekly_limit`
(>40h) — visual flags only, no enforcement (break deduction and real
overtime rules are Phase 2, per the blueprint's Section 0 default).
Self, or a Manager for staff at a location they share with that employee;
Admins may view anyone's.

## Testing

Tests run against the same database the app uses (already migrated — see above).
Each test runs inside a transaction that is rolled back afterwards, so no
separate test database or cleanup step is needed. Test users are created
directly against the database (matching how the seed script bootstraps the
first admin), then logged in for real through `/auth/login` — there's no
self-registration endpoint to hit.

```bash
docker compose exec app pytest
```

One file is deliberately different: `tests/test_shift_assignment_concurrency.py`
talks to the real database through independent connections/threads (not the
shared rollback fixture, which lives on a single connection and can't
demonstrate cross-connection locking) to prove the shift-row lock actually
serializes concurrent accepts — it cleans up its own rows rather than relying
on the transaction rollback the rest of the suite uses.

Or locally, with dependencies installed and `DATABASE_URL` pointed at a
reachable Postgres:

```bash
pip install -r requirements.txt
alembic upgrade head
pytest
```

## Environment variables

Defined in `.env.example`:

| Variable                          | Description                                              | Local default                                              |
|------------------------------------|------------------------------------------------------------|--------------------------------------------------------------|
| `APP_ENV`                          | Environment name — `production`/`prod` triggers the JWT secret strength check below | `development`                        |
| `APP_NAME`                         | Used as the API title                                     | `briscoes`                                                    |
| `DATABASE_URL`                     | SQLAlchemy/psycopg PostgreSQL connection string            | `postgresql+psycopg://postgres:postgres@db:5432/briscoes`     |
| `JWT_SECRET_KEY`                   | Secret used to sign/verify JWTs — set a strong value outside local dev | `change-me`                                       |
| `JWT_ALGORITHM`                    | JWT signing algorithm                                      | `HS256`                                                       |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`  | Access token lifetime, in minutes                          | `30`                                                          |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS`    | Refresh token lifetime, in days                             | `7`                                                           |
| `CLOCK_GRACE_MINUTES`              | Grace window either side of a shift for clock in/out        | `15`                                                          |

`.env` is gitignored — never commit real secrets.

## Security hardening

- **Startup refuses an insecure JWT secret in production.** Set
  `APP_ENV=production` (or `prod`) with `JWT_SECRET_KEY` still at the
  `change-me` default, or under 32 characters, and the app fails to start
  (`app/core/config.py`) — a weak signing key is a total auth bypass, not a
  degraded-mode issue, so this is fail-fast rather than a warning. Generate
  a real one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- **`/auth/login` and `/auth/refresh` are rate-limited** per source IP (10
  and 30 requests/minute respectively) via slowapi — see
  `app/core/rate_limit.py`. In-memory by default, fine for a single
  process; point it at Redis (see slowapi's docs) behind a load balancer.
  Tests disable the limiter (`tests/conftest.py`) since Starlette's
  `TestClient` presents one fake address for the whole suite.

## Project structure

```text
app/
  main.py            FastAPI app, /health, router registration
  core/
    config.py        Environment-based settings (pydantic-settings)
    security.py      Password hashing (Argon2), JWT create/decode, refresh-token hashing
    dependencies.py  get_current_user, require_role, require_location_access,
                      user_can_access_location, manager_shares_location_with_employee
  db/
    session.py       SQLAlchemy engine, session factory, get_db dependency
    base.py           Declarative base
  models/
    user.py                User ORM model (role, home_location_id, token_version)
    location.py            Location ORM model
    manager_location.py    Manager → location scoping join table
    employee_location.py   Employee → location scoping join table
    refresh_token.py       Persisted, hashed, revocable refresh tokens
    availability.py        Employee availability, location-agnostic
    shift.py               Shift ORM model + status enum
    shift_assignment.py    ShiftAssignment ORM model + status enum
    notification.py        Notification ORM model + type enum
    time_entry.py           TimeEntry ORM model + flag enum
  services/
    assignment_service.py   Shift status machine, eligible pool, offer/accept/reject/withdraw
    notification_service.py In-app notification creation
    time_clock_service.py   Clock in/out rules
    timesheet_service.py    Per-day/weekly hour rollup
  schemas/           Pydantic request/response models, one file per resource
  api/
    auth.py          /auth/login, /auth/refresh, /auth/logout, /auth/me
    users.py         /users (provisioning + listing)
    locations.py     /locations, /locations/{id}
    availability.py  /availability
    shifts.py        /shifts, /shifts/{id}/candidates, /roster
    assignments.py   /shifts/{id}/assignments, /assignments/{id}/accept|reject, DELETE /assignments/{id}
    notifications.py /notifications, /notifications/{id}/read
    time_entries.py  /time-entries/clock-in|clock-out, PATCH /time-entries/{id}
    timesheets.py    /timesheets
  scripts/
    seed_admin.py    Bootstraps the first Admin account (see above)
alembic/              Migrations (schema is managed exclusively through these)
tests/                 pytest suite (see tests/helpers.py for shared fixtures —
                       create-user-then-log-in, location/shift/availability
                       factories, and the clock-in time-freezing helper)
```

## Scope

**All of Phase 1** (the project blueprint's Section 15, Steps 1–6) is
implemented:

- **Foundations**: `User` (role, home location, provisioned — no
  self-signup), `Location`, manager/employee location-scoping, revocable
  refresh tokens, and the `require_role`/`require_location_access`/
  `user_can_access_location`/`manager_shares_location_with_employee`
  authorization building blocks.
- **Availability**: rolling 14-day window, bulk upsert, and the
  ordering-critical `created_at`-preserved-on-edit rule.
- **Assignment core**: shift CRUD, the staffing board with computed status,
  candidate resolution, offer/accept/reject, auto-reassignment, and the
  `status`/`roster_locked_at` split — the highest-risk logic in the app,
  with a real multi-connection concurrency test alongside the usual
  sequential ones.
- **Roster & notifications**: `GET /roster`, the in-app notification feed,
  and manual override assignment (a Manager can always assign outside the
  eligible pool — there's no separate "unfilled shift resolution" endpoint,
  it's the same assign action MGR-05 would call in a UI).
- **Time & timesheets**: all six clock-in/out cases from Section 10,
  including the forgotten-clock-out manager correction path, plus per-day
  and weekly hour rollups with overtime *flags* (not enforcement).
- **Hardening**: consistent error handling across every endpoint (verified
  with two regression tests for FK-violation edge cases that would
  otherwise surface as raw 500s or misleading error messages — see
  `test_admin_creating_shift_at_nonexistent_location_returns_404` and
  `test_provisioning_with_nonexistent_home_location_rejected`).

**What Phase 1's Step 6 explicitly doesn't cover here, because this repo is
backend-only**: there's no frontend, so the error/loading/empty-state UI
pass, the Playwright end-to-end suite, and the accessibility pass (Section
12 & 13) don't apply — those land once a frontend exists. A k6 load test
against the assignment endpoints is also not included; the concurrency
guarantee is instead proven directly against Postgres (see Testing, above).

**Deliberately not built** (Phase 2, per the blueprint's own Section 15):
email/SMS notifications, offer-expiry timers, direct shift swapping,
recurring shift templates, a Super Admin location-management UI (schema and
API-level scoping are ready; there's no `POST /locations` yet — see
[Bootstrapping the first admin](#bootstrapping-the-first-admin)), payroll
export and staffing analytics, and break/overtime enforcement. There's also
still no email verification or password reset.
