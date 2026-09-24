import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

import { postJson } from './api-client';
import { expectNoSeriousA11yViolations, injectSession } from './helpers';
import { TEST_DATA_PATH, type TestData, type TestUser } from './test-data';

const data: TestData = JSON.parse(readFileSync(TEST_DATA_PATH, 'utf-8'));

// The test location's timezone (see global-setup.ts) is Australia/Sydney,
// and the backend interprets a shift's date/start/end as local to its own
// location — so both "today" and "now ± N hours" must be computed in
// Sydney wall-clock time, not the test runner machine's own system
// timezone, or the shift created wouldn't actually bracket real "now" at
// all (found by running this suite for real: a single accepted shift was
// producing the ambiguous-choice dialog instead of a clean clock-in,
// because the time string was being interpreted ~10-11 hours off from
// intended). Like the backend's own time-based tests, this still has a
// narrow, accepted flakiness window right at Sydney's midnight, where an
// offset could cross into a different calendar day than `today()` — not
// worth fully solving for a test suite.
const SHIFT_TZ = 'Australia/Sydney';

function sydneyParts(d: Date): Record<string, string> {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: SHIFT_TZ,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).formatToParts(d);
  return Object.fromEntries(parts.filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]));
}

function todayParts() {
  return sydneyParts(new Date());
}

function today(): string {
  const { year, month, day } = todayParts();
  return `${year}-${month}-${day}`;
}

/** A time-of-day for `today()` (Sydney), offset from real "now" — clamped
 * into [00:00, 23:59] if the raw offset would land on a different calendar
 * day. Shifts in this data model can't span midnight (one `date` field for
 * both start and end), so without clamping, an offset test running near
 * Sydney's midnight would try to build a shift with start > end and 422.
 * Clamping keeps the shift constructible and still centered on real "now"
 * rather than failing outright — the residual case (now within a minute or
 * two of midnight, clamping both ends to the same instant) is an accepted,
 * vanishingly rare flakiness window, same tradeoff the backend's own
 * time-based tests make. */
function hhmm(offsetHours: number): string {
  const today = todayParts();
  const target = sydneyParts(new Date(Date.now() + offsetHours * 3_600_000));
  const sameDay = target.year === today.year && target.month === today.month && target.day === today.day;
  if (!sameDay) return offsetHours < 0 ? '00:00:00' : '23:59:00';
  return `${target.hour === '24' ? '00' : target.hour}:${target.minute}:00`;
}

async function createAcceptedShift(employee: TestUser, start: string, end: string): Promise<void> {
  const shift = await postJson(
    '/shifts',
    {
      location_id: data.locationId,
      date: today(),
      start_time: start,
      end_time: end,
      min_staff: 1,
      max_staff: 1,
    },
    data.manager.tokens.access_token,
  );
  const offer = await postJson(
    `/shifts/${shift.id}/assignments`,
    { employee_id: employee.id },
    data.manager.tokens.access_token,
  );
  await postJson(`/assignments/${offer.id}/accept`, {}, employee.tokens.access_token);
}

test.describe('Clock in / out', () => {
  test('clocking in against an accepted shift, then out, shows on the timesheet', async ({ page }) => {
    const employee = data.employees[3]; // dedicated — see global-setup.ts
    await createAcceptedShift(employee, hhmm(-2), hhmm(2));

    await injectSession(page, employee.tokens);
    await page.goto('/app');
    await expectNoSeriousA11yViolations(page);

    await page.getByRole('button', { name: 'Clock in' }).click();
    await expect(page.getByText(/clocked in since/i)).toBeVisible();

    await page.getByRole('button', { name: 'Clock out' }).click();
    await expect(page.getByText('Not clocked in')).toBeVisible();

    await page.goto('/app/timesheet');
    await expect(page.getByText('On time').or(page.getByText('After shift end'))).toBeVisible();
  });

  test('an ambiguous gap between two accepted shifts prompts a choice', async ({ page }) => {
    const employee = data.employees[4]; // dedicated — see global-setup.ts
    // Two accepted shifts today with "now" sitting in the gap between them.
    await createAcceptedShift(employee, hhmm(-6), hhmm(-2));
    await createAcceptedShift(employee, hhmm(2), hhmm(6));

    await injectSession(page, employee.tokens);
    await page.goto('/app');

    await page.getByRole('button', { name: 'Clock in' }).click();

    const dialog = page.getByRole('dialog', { name: /which shift/i });
    await expect(dialog).toBeVisible();
    await expectNoSeriousA11yViolations(page);

    // Pick one — either resolves the clock-in.
    await dialog.getByRole('button').first().click();
    await expect(page.getByText(/clocked in since/i)).toBeVisible();

    await page.getByRole('button', { name: 'Clock out' }).click();
  });
});
