import AxeBuilder from '@axe-core/playwright';
import { expect, type Page } from '@playwright/test';

import type { TokenPair } from './test-data';

/** Injects a pre-fetched session (see test-data.ts / global-setup.ts)
 * directly into the app's persisted auth store — no live /auth/login call.
 * auth.spec.ts is the one place the actual login form gets exercised
 * end-to-end, deliberately using real credentials instead of this. */
export async function injectSession(page: Page, tokens: TokenPair): Promise<void> {
  await page.addInitScript((session) => {
    localStorage.setItem(
      'crew-auth',
      JSON.stringify({
        state: { accessToken: session.access_token, refreshToken: session.refresh_token, user: null },
        version: 0,
      }),
    );
  }, tokens);
}

/** Runs axe-core against the current page and asserts zero violations at
 * the "serious"/"critical" level — the accessibility pass the blueprint's
 * Section 6 calls for, wired into the E2E suite rather than a separate
 * one-off audit so it can't silently regress. Radix's own primitives
 * (Dialog, DropdownMenu, Toggle, Toast) carry most of the WCAG burden
 * already; this catches what the app layer adds on top (missing labels,
 * contrast, heading order). */
export async function expectNoSeriousA11yViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  if (serious.length > 0) {
    const detail = serious
      .map(
        (v) =>
          `${v.id} (${v.impact}): ${v.help}\n` +
          v.nodes.map((n) => `  - ${n.target.join(' ')}: ${n.html}`).join('\n'),
      )
      .join('\n');
    throw new Error(`Accessibility violations found:\n${detail}`);
  }
  expect(serious).toHaveLength(0);
}
