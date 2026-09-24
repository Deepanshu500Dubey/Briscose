/** Shared shape of the fixture data global-setup.ts writes and every spec
 * reads back — kept in one file so the two stay in sync.
 *
 * Every user's access/refresh token pair is pre-fetched once, here, during
 * setup — not re-fetched at spec-run time. `/auth/login` is rate-limited
 * per source IP (see the root README's Security hardening section), and
 * every login this suite makes shares that one bucket regardless of which
 * user it's for; fetching once up front keeps the whole suite's real
 * login-endpoint traffic at a handful of calls instead of dozens. */
export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

export interface TestUser {
  id: string;
  email: string;
  password: string;
  tokens: TokenPair;
}

export interface TestData {
  locationId: string;
  locationName: string;
  manager: TestUser;
  /** Five employees, each dedicated to exactly one spec's ACCEPTED
   * assignments (or, for [1] and [2], never accepted at all) — see the
   * per-index comments in global-setup.ts. Never share an index across
   * specs that both drive that employee to ACCEPTED, or the real
   * overlap-prevention exclusion constraint (Section 11) could
   * legitimately reject one of them depending on what time the suite
   * happens to run. */
  employees: TestUser[];
}

export const TEST_DATA_PATH = 'e2e/.test-data.json';
export const API_BASE = 'http://localhost:8000';
