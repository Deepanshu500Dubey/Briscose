import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

import { expectNoSeriousA11yViolations, injectSession } from './helpers';
import { TEST_DATA_PATH, type TestData } from './test-data';

const data: TestData = JSON.parse(readFileSync(TEST_DATA_PATH, 'utf-8'));

test.describe('Employee availability — rolling 14 days + bulk save', () => {
  test('toggling a day and saving persists across reload', async ({ page }) => {
    const employee = data.employees[0];
    await injectSession(page, employee.tokens);
    await page.goto('/app/availability');
    await expectNoSeriousA11yViolations(page);

    const saveButton = page.getByRole('button', { name: /save changes|saved/i });
    await expect(saveButton).toHaveText(/saved/i);

    // The first day's toggle — flip it on, which should reveal a time
    // range and flip the header button to "Save changes".
    const firstToggle = page.getByRole('button', { name: /^available on/i }).first();
    await firstToggle.click();
    await expect(saveButton).toHaveText(/save changes/i);

    await saveButton.click();
    await expect(saveButton).toHaveText(/saved/i);

    // Reload — the save must have actually persisted server-side, not just
    // updated local state.
    await page.reload();
    await expect(page.getByText('to')).toBeVisible();
  });
});
