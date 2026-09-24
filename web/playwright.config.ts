import { defineConfig, devices } from '@playwright/test';

/** E2E suite for the six core flows (project blueprint, Section 13):
 * availability save, assign→accept, assign→reject→reassign, clock in/out
 * (including the multi-shift disambiguation prompt), and roster
 * confirmation/top-up. Runs against the real backend (docker compose) —
 * no mocking — via global setup that provisions its own admin/manager/
 * employees/location so it never touches real data. */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // shared backend + shared test-location state
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
