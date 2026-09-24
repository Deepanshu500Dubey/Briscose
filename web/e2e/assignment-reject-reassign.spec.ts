import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

import { patchJson, postJson } from './api-client';
import { injectSession } from './helpers';
import { TEST_DATA_PATH, type TestData } from './test-data';

const data: TestData = JSON.parse(readFileSync(TEST_DATA_PATH, 'utf-8'));

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

test.describe('Reject triggers auto-reassignment, visible in the UI', () => {
  test('rejecting an offer immediately surfaces a new offer to the next eligible employee', async ({
    browser,
  }) => {
    // Dedicated indices (1, 2) — neither ever becomes ACCEPTED in this
    // spec, so roster-topup.spec.ts safely reuses them for its own
    // (unrelated, non-overlapping) accepted shift. See global-setup.ts.
    const [firstOffered, nextInLine] = [data.employees[1], data.employees[2]];

    // An evening window, deliberately outside employees[0]'s 07:00-18:00
    // availability from assignment-accept.spec.ts (same location, same
    // day, and that spec runs first alphabetically) — otherwise employee
    // [0] would also be eligible for this shift, and being available since
    // *before* this test even starts, would legitimately win the "first to
    // submit" reassignment ordering ahead of nextInLine, exactly as
    // designed (Section 10) — just not what this test means to exercise.
    for (const employee of [firstOffered, nextInLine]) {
      await patchJson(
        '/availability',
        { days: [{ date: today(), is_available: true, start_time: '19:00:00', end_time: '23:59:00' }] },
        employee.tokens.access_token,
      );
    }

    const shift = await postJson(
      '/shifts',
      {
        location_id: data.locationId,
        date: today(),
        start_time: '20:00:00',
        end_time: '23:00:00',
        min_staff: 1,
        max_staff: 1,
      },
      data.manager.tokens.access_token,
    );
    await postJson(
      `/shifts/${shift.id}/assignments`,
      { employee_id: firstOffered.id },
      data.manager.tokens.access_token,
    );

    const rejectingContext = await browser.newContext();
    const rejectingPage = await rejectingContext.newPage();
    await injectSession(rejectingPage, firstOffered.tokens);
    await rejectingPage.goto('/app');
    await expect(rejectingPage.getByText('Pending your response')).toBeVisible();

    await rejectingPage.getByRole('button', { name: 'Reject' }).click();
    await expect(rejectingPage.getByText('Rejected', { exact: true })).toBeVisible();

    const nextContext = await browser.newContext();
    const nextPage = await nextContext.newPage();
    await injectSession(nextPage, nextInLine.tokens);
    await nextPage.goto('/app');

    await expect(nextPage.getByText('Pending your response')).toBeVisible();

    await rejectingContext.close();
    await nextContext.close();
  });
});
