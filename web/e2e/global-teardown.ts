import { execSync } from 'node:child_process';
import { existsSync, readFileSync, unlinkSync } from 'node:fs';

import { TEST_DATA_PATH, type TestData } from './test-data';

/** Deletes everything global-setup.ts created, by email pattern — same
 * "never leave test data behind" practice used throughout manual testing
 * this project. Every email global-setup.ts creates ends in
 * "-<runId>@example.com" (admin, manager, and each employeeN alike), so
 * that's what ties them together here without needing to have stored the
 * admin's own email on TestData. */
export default async function globalTeardown(): Promise<void> {
  if (!existsSync(TEST_DATA_PATH)) return;
  const data: TestData = JSON.parse(readFileSync(TEST_DATA_PATH, 'utf-8'));
  const runId = data.manager.email.match(/e2e-manager-(\d+)@/)?.[1];
  if (!runId) throw new Error(`Could not parse run id from manager email: ${data.manager.email}`);
  const emailPattern = `%-${runId}@example.com`;

  const sql = `
    DELETE FROM time_entries WHERE employee_id IN (SELECT id FROM users WHERE email LIKE '${emailPattern}');
    DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE email LIKE '${emailPattern}');
    DELETE FROM shift_assignments WHERE employee_id IN (SELECT id FROM users WHERE email LIKE '${emailPattern}');
    DELETE FROM shifts WHERE created_by IN (SELECT id FROM users WHERE email LIKE '${emailPattern}');
    DELETE FROM availability WHERE employee_id IN (SELECT id FROM users WHERE email LIKE '${emailPattern}');
    DELETE FROM manager_locations WHERE manager_id IN (SELECT id FROM users WHERE email LIKE '${emailPattern}');
    DELETE FROM employee_locations WHERE employee_id IN (SELECT id FROM users WHERE email LIKE '${emailPattern}');
    DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE email LIKE '${emailPattern}');
    DELETE FROM users WHERE email LIKE '${emailPattern}';
    DELETE FROM locations WHERE name = '${data.locationName}';
  `;

  execSync(`docker compose exec -T db psql -U postgres -d briscoes -c "${sql.replace(/"/g, '\\"')}"`, {
    cwd: '..',
    stdio: 'inherit',
  });

  unlinkSync(TEST_DATA_PATH);
}
