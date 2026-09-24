import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

import { postJson } from './api-client';
import { expectNoSeriousA11yViolations, injectSession } from './helpers';
import { TEST_DATA_PATH, type TestData } from './test-data';

const data: TestData = JSON.parse(readFileSync(TEST_DATA_PATH, 'utf-8'));

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** The exact worked example from the project blueprint, Section 10: a
 * shift confirms once min_staff accepts, appears on the roster, and a
 * later top-up offer toward max_staff must NOT remove it from the roster
 * even while `status` transiently flips back to pending_acceptance. */
test.describe('Roster confirmation and top-up', () => {
  test('a confirmed shift appears on the roster and survives a top-up offer', async ({ page }) => {
    // Same indices as assignment-reject-reassign.spec.ts (1, 2) — safe to
    // reuse since neither is ever ACCEPTED there. See global-setup.ts.
    const [empA, empB] = [data.employees[1], data.employees[2]];

    const shift = await postJson(
      '/shifts',
      {
        location_id: data.locationId,
        date: today(),
        start_time: '09:00:00',
        end_time: '17:00:00',
        min_staff: 1,
        max_staff: 2,
      },
      data.manager.tokens.access_token,
    );

    const offerA = await postJson(
      `/shifts/${shift.id}/assignments`,
      { employee_id: empA.id },
      data.manager.tokens.access_token,
    );
    await postJson(`/assignments/${offerA.id}/accept`, {}, empA.tokens.access_token);

    await injectSession(page, data.manager.tokens);
    await page.goto('/manage/roster');
    await expectNoSeriousA11yViolations(page);

    const rosterRow = page.locator('tr', { hasText: '9:00 AM – 5:00 PM' });
    await expect(rosterRow).toBeVisible();
    await expect(rosterRow).toContainText('Confirmed');

    // Top up toward max_staff=2 on the already-confirmed shift.
    const offerB = await postJson(
      `/shifts/${shift.id}/assignments`,
      { employee_id: empB.id },
      data.manager.tokens.access_token,
    );

    // status flips to pending_acceptance, but it must still be on the
    // roster — this is the whole point of roster_locked_at existing.
    await page.reload();
    await expect(rosterRow).toBeVisible();
    await expect(rosterRow).toContainText('Pending Acceptance');

    await postJson(`/assignments/${offerB.id}/accept`, {}, empB.tokens.access_token);

    await page.reload();
    await expect(rosterRow).toContainText('Fully Staffed');
    await expect(rosterRow).toContainText(empA.email);
    await expect(rosterRow).toContainText(empB.email);
  });
});
