import { execSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';

import { API_BASE, TEST_DATA_PATH, type TestData, type TestUser } from './test-data';

/** Provisions everything the E2E suite needs against the real backend:
 * a dedicated admin (via the same seed script the README documents),
 * one location, one manager, and five employees — all under a run-unique
 * "e2e-<timestamp>" prefix so repeated runs never collide and never touch
 * real data. Torn down in global-teardown.ts.
 *
 * Every user is also logged in here, once, with the resulting tokens
 * stored on the TestUser record — see test-data.ts for why. */
export default async function globalSetup(): Promise<void> {
  const runId = Date.now();
  const adminEmail = `e2e-admin-${runId}@example.com`;
  const adminPassword = 'e2e-strong-password-1';

  execSync(
    `docker compose exec -T app python -m app.scripts.seed_admin ${adminEmail} "${adminPassword}"`,
    { cwd: '..', stdio: 'inherit' },
  );

  const adminTokens = await login(adminEmail, adminPassword);

  const locationName = `E2E Store ${runId}`;
  const location = await postJson(
    '/locations',
    { name: locationName, address: '1 Test St', timezone: 'Australia/Sydney' },
    adminTokens.access_token,
  );

  const managerEmail = `e2e-manager-${runId}@example.com`;
  const managerPassword = 'e2e-strong-password-1';
  await postJson(
    '/users',
    { email: managerEmail, password: managerPassword, role: 'manager', location_ids: [location.id] },
    adminTokens.access_token,
  );
  const manager: TestUser = {
    id: '', // not needed anywhere; managers act via their own token, not their id
    email: managerEmail,
    password: managerPassword,
    tokens: await login(managerEmail, managerPassword),
  };

  // Index allocation — each dedicated to exactly one spec's ACCEPTED
  // assignments, to guarantee no two specs' shifts can ever overlap for
  // the same employee regardless of what time the suite runs:
  //   [0] assignment-accept.spec.ts        (accepted)
  //   [1] assignment-reject-reassign +      (never accepted in either spec —
  //       roster-topup.spec.ts (empA)        safe to share)
  //   [2] assignment-reject-reassign +      (never accepted in reject-reassign;
  //       roster-topup.spec.ts (empB)        accepted only in roster-topup)
  //   [3] clock-in-out.spec.ts test 1       (accepted)
  //   [4] clock-in-out.spec.ts test 2       (accepted x2)
  const employees: TestUser[] = [];
  for (let i = 0; i < 5; i++) {
    const email = `e2e-employee${i}-${runId}@example.com`;
    const password = 'e2e-strong-password-1';
    const user = await postJson(
      '/users',
      { email, password, role: 'employee', location_ids: [location.id] },
      adminTokens.access_token,
    );
    employees.push({ id: user.id, email, password, tokens: await login(email, password) });
  }

  const data: TestData = {
    locationId: location.id,
    locationName,
    manager,
    employees,
  };
  writeFileSync(TEST_DATA_PATH, JSON.stringify(data, null, 2));
}

async function login(email: string, password: string) {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error(`login failed for ${email}: ${response.status}`);
  return response.json();
}

async function postJson(path: string, body: unknown, token: string): Promise<any> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`POST ${path} failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}
