# Briscoes Crew — Frontend

React 18 + TypeScript + Vite frontend for the Phase 1 backend (see the repo
root [README](../README.md)). Implements the full Phase 1 screen set against
the real, running FastAPI backend — no mock data, no invented endpoints
beyond the two documented gaps below.

## Stack

Exactly the mandated set, nothing added: React 18, TypeScript, Vite, React
Router v6, TanStack Query (server state), Zustand (local/UI/draft state
only), React Hook Form + Zod, Tailwind CSS, Radix UI primitives,
date-fns/date-fns-tz.

## Running it

The backend must already be up (`docker compose up` from the repo root,
migrated to head — see the root README).

```bash
npm install
npm run dev
```

Opens on `http://localhost:5173`. The dev server proxies `/api/*` to the
backend at `http://localhost:8000` with the `/api` prefix stripped (see
`vite.config.ts`) — the backend itself has no `/api` prefix, so this is
purely a same-origin routing convenience; no CORS configuration was needed
on the backend at all.

### Regenerating API types

Typed request/response models come straight from the backend's own OpenAPI
schema — the API's source of truth, not hand-maintained:

```bash
npm run gen:api-types
```

Requires the backend running on `localhost:8000`. Re-run this after any
backend schema change; `src/types/api.ts` re-exports the pieces the app
uses under stable names.

### Bootstrapping test accounts

There's no self-signup (see the root README). Seed an admin
(`python -m app.scripts.seed_admin`), log in, then use the **Admin** section
(Locations, Users — visible in the Manager portal's nav for an Admin
account) to create a location and provision a manager/employees. No curl
required any more — this used to be API-only.

## Structure

```text
src/
  app/
    App.tsx              Router: /login, /app/* (Employee), /manage/* (Manager,
                         with /manage/admin/* nested and Admin-gated)
    RequireAuth.tsx       Auth gate — re-validates the session via GET /auth/me
    RoleGate.tsx           Redirects between /app and /manage by role
    auth/LoginPage.tsx
    employee/              Dashboard, My Shifts, Availability, Timesheet,
                         Profile, layout, ClockCard
    manager/                Staffing Board, Unfilled Shifts, Roster,
                         Team & Availability, Team Timesheets, Create/Assign
    admin/                  Locations, Users (Admin-only, nested under /manage)
  components/              Design-system pieces: Button, StatusChip, Card, Modal,
                           Toaster, States (Skeleton/Empty/Error/StaleDataBanner),
                           ShiftCard, StaffingGauge, WeekPager, DayToggleRow,
                           TimesheetTable, EmployeeChips, NotificationsBell
  features/                One folder per resource, each a thin TanStack Query
                           wrapper over src/lib/apiClient.ts: auth, availability,
                           locations, shifts, assignments, notifications,
                           timeClock, timesheets, users
  stores/                  Zustand — auth (session, persisted), ui (selected
                           manager location + drawer/modal state, persisted),
                           toast, availabilityDraft (unsaved grid edits only —
                           server state lives in TanStack Query, not here)
  lib/
    apiClient.ts           Typed fetch wrapper: auth header injection,
                           refresh-on-401 retry (single in-flight refresh
                           shared across concurrent 401s), FastAPI error
                           parsing into ApiError
    dates.ts                Rolling-window/week-range helpers matching the
                           backend's own date logic
  types/
    openapi.d.ts            Generated — do not hand-edit
    api.ts                   Convenience aliases + the one hand-typed exception
                           (see below)
```

## Design tokens

Tailwind theme (`tailwind.config.ts`) lifted directly from the project
blueprint's Section 2: Briscoes Navy/Gold palette, Barlow Condensed (display)
+ Public Sans (body) + IBM Plex Mono (data), loaded via Google Fonts in
`index.css`.

## Documented backend changes and one API gap

Building this out surfaced real integration issues in the existing
contract — fixed rather than worked around, per the brief:

1. **`GET /shifts` gained `my_assignment_id`/`my_assignment_status`** (both
   nullable, populated for Employee callers only). Without this, an
   Employee's own dashboard had no way to discover the assignment ID needed
   to call `POST/DELETE /assignments/{id}` — Accept/Reject and
   auto-reassignment couldn't work end-to-end at all.
2. **`GET /shifts` (all callers) gained `accepted_employees`**
   (`[{id, email}]`) — the roster's per-employee chips (MGR-04) and a
   shift's "coworkers rostered" (EMP-04) both need to know who's actually
   on a shift, which nothing previously exposed.
3. **`POST /locations`** (Admin-only) — needed for the Admin UI to create
   the first location at all; previously read-only + a raw SQL insert.
4. **`PATCH /auth/password`** — self-service password change for the
   Profile screen; bumps `token_version` and revokes existing refresh
   tokens, then returns a fresh pair so the caller isn't logged out by
   their own request.

All four are additive (new endpoint or new nullable/default-valued fields
on an existing response) — no existing behavior changed, each covered by
backend regression tests (see the root README's Testing section).

**One still-hand-typed exception**: `ShiftChoiceResponse` in
`src/types/api.ts` isn't generated. `POST /time-entries/clock-in` returns
one of three shapes from a manually-built `JSONResponse` (not a declared
`response_model`), so its ambiguous-shift-choice shape never reached the
OpenAPI output. Hand-typed to match the backend's real Pydantic schema
exactly — see the comment at its definition.

## Known simplifications

- **Clock-state detection is derived from the current week's timesheet**,
  not a dedicated "am I clocked in" endpoint (none exists). Self-heals
  immediately on the rare edge case (a forgotten clock-out from a prior
  week) because clock-in's own soft-success response syncs the UI either
  way — see the comment in `features/timeClock/api.ts`.
- **The Assign drawer's manual-override list** can't perfectly exclude an
  employee the instant they're offered elsewhere in the same shift's
  history, since there's no "list assignments for a shift" endpoint —
  mitigated by tracking just-offered employees client-side per drawer
  session (see `app/manager/AssignDrawer.tsx`); the backend's own duplicate
  check is the real guard regardless (verified live: re-offering an
  employee who already has a terminal row on a shift correctly surfaces a
  409 as a toast, not a silent failure or crash).
- **Team & Availability (MGR-06) and My Shifts (EMP-03)** fan out across
  N employees / several weeks respectively with parallel requests (no bulk
  endpoint exists for either) — fine at store scale, would need a real bulk
  endpoint to scale further.
- **Profile (EMP-07) doesn't offer name/contact editing** — the `User`
  model has no such fields. Password change is real and fully wired;
  adding name/contact is a schema decision for someone to make
  deliberately, not a UI-layer workaround.
- **Admin can create locations and provision users**, but there's no
  "assign an existing user to another location" UI — that still only
  happens at provisioning time (`location_ids` on `POST /users`), matching
  the backend's actual capability.
- **No Storybook.** Every component listed in the blueprint's inventory
  exists as a real, used React component (see `src/components/`), but a
  standalone Storybook app wasn't stood up — a deliberate time trade-off
  favoring a working, integration-tested app over isolated component
  documentation.
- **No frontend automated test suite yet** (Vitest/Testing Library,
  Playwright) — everything above was verified through live, manual browser
  testing against the real backend this session, not a repeatable suite.
  Stale-while-revalidate error handling (blueprint Section 12) is
  implemented on the highest-traffic screens (Staffing Board, Unfilled
  Shifts, My Shifts) via `<StaleDataBanner>`, not yet audited across every
  screen.
