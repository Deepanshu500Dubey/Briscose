import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

import { patchJson } from './api-client';
import { expectNoSeriousA11yViolations, injectSession } from './helpers';
import { TEST_DATA_PATH, type TestData } from './test-data';

const data: TestData = JSON.parse(readFileSync(TEST_DATA_PATH, 'utf-8'));

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

test.describe('Manager creates a shift, assigns it, employee accepts', () => {
  test('offer → accept confirms the shift on the staffing board', async ({ browser }) => {
    const employee = data.employees[0]; // dedicated — see global-setup.ts

    // Give the employee availability for today via the API — this test is
    // about assign→accept, not re-proving the availability flow.
    await patchJson(
      '/availability',
      { days: [{ date: today(), is_available: true, start_time: '07:00:00', end_time: '18:00:00' }] },
      employee.tokens.access_token,
    );

    const managerContext = await browser.newContext();
    const managerPage = await managerContext.newPage();
    await injectSession(managerPage, data.manager.tokens);
    await managerPage.goto('/manage');
    await expectNoSeriousA11yViolations(managerPage);

    await managerPage.getByRole('button', { name: '+ Create shift' }).click();
    await managerPage.getByLabel('Date').fill(today());
    await managerPage.getByLabel('Start time').fill('08:00');
    await managerPage.getByLabel('End time').fill('16:00');
    await managerPage.getByLabel('Min staff').fill('1');
    await managerPage.getByLabel('Max staff').fill('1');
    await managerPage.getByRole('button', { name: 'Create shift' }).click();

    const row = managerPage.locator('tr', { hasText: '8:00 AM – 4:00 PM' }).first();
    await expect(row).toBeVisible();
    await row.getByRole('button', { name: 'Assign' }).click();

    const dialog = managerPage.getByRole('dialog', { name: 'Assign employees' });
    await expectNoSeriousA11yViolations(managerPage);
    await dialog.getByRole('button', { name: 'Assign' }).first().click();
    await expect(managerPage.getByText('Offer sent', { exact: true })).toBeVisible();
    await managerPage.keyboard.press('Escape');

    await expect(row).toContainText('Pending Acceptance');

    const employeeContext = await browser.newContext();
    const employeePage = await employeeContext.newPage();
    await injectSession(employeePage, employee.tokens);
    await employeePage.goto('/app');
    await expect(employeePage.getByText('Pending your response')).toBeVisible();

    await employeePage.getByRole('button', { name: 'Accept' }).click();
    // Non-exact getByText does substring/case-insensitive matching, which
    // would also match the "Shift accepted" toast — pin to the status
    // chip's exact text.
    await expect(employeePage.getByText('Accepted', { exact: true })).toBeVisible();

    await managerPage.reload();
    // This shift is min_staff=1/max_staff=1, so per the backend's own
    // board-label vocabulary (app/api/shifts.py `_board_label`) a confirmed
    // shift at capacity reads "Fully Staffed", not "Confirmed" — that label
    // is reserved for a confirmed shift still under max_staff.
    await expect(row).toContainText('Fully Staffed');

    await managerContext.close();
    await employeeContext.close();
  });
});
