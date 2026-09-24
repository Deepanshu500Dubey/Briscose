import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

import { expectNoSeriousA11yViolations, injectSession } from './helpers';
import { TEST_DATA_PATH, type TestData } from './test-data';

const data: TestData = JSON.parse(readFileSync(TEST_DATA_PATH, 'utf-8'));

test.describe('Login + auth persistence', () => {
  // These two exercise the real login form end-to-end (the only place in
  // the suite that makes a live /auth/login call — see test-data.ts for
  // why every other spec injects a pre-fetched session instead).
  test('logs in through the real form and lands on the manager portal', async ({ page }) => {
    await page.goto('/login');
    await expectNoSeriousA11yViolations(page);

    await page.getByLabel('Email').fill(data.manager.email);
    await page.getByLabel('Password').fill(data.manager.password);
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page).toHaveURL(/\/manage$/);
    await expect(page.getByRole('heading', { name: 'Staffing board' })).toBeVisible();
  });

  test('rejects the wrong password with a visible error, no navigation', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(data.manager.email);
    await page.getByLabel('Password').fill('definitely-wrong');
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page.getByText(/incorrect email or password/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('session persists across a reload', async ({ page }) => {
    await injectSession(page, data.manager.tokens);
    await page.goto('/manage');
    await expect(page.getByRole('heading', { name: 'Staffing board' })).toBeVisible();

    await page.reload();

    await expect(page).toHaveURL(/\/manage$/);
    await expect(page.getByRole('heading', { name: 'Staffing board' })).toBeVisible();
  });

  test('logging out clears the session and redirects to login', async ({ page }) => {
    await injectSession(page, data.manager.tokens);
    await page.goto('/manage');
    await expect(page.getByRole('heading', { name: 'Staffing board' })).toBeVisible();

    await page.getByRole('button', { name: 'Log out' }).click();
    await expect(page).toHaveURL(/\/login$/);

    // Confirm the effect is real server-side, not just a client-side route
    // change: the refresh token logout revoked must now be rejected. (Not
    // re-testing via a page navigation on this same `page` — injectSession's
    // addInitScript re-fires on every navigation for its whole lifetime, so
    // a goto('/manage') here would silently re-inject the original tokens
    // and mask a real logout regression instead of catching one.)
    const refreshResponse = await page.request.post('http://localhost:8000/auth/refresh', {
      data: { refresh_token: data.manager.tokens.refresh_token },
    });
    expect(refreshResponse.status()).toBe(401);
  });
});
