import { API_BASE } from './test-data';

/** Pure HTTP helpers for spec-time API setup calls. Deliberately take a
 * pre-fetched token rather than an (email, password) pair — every user's
 * tokens are fetched once in global-setup.ts, not re-fetched here, to
 * avoid tripping /auth/login's rate limit (see test-data.ts). */
export async function postJson(path: string, body: unknown, token: string): Promise<any> {
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

export async function patchJson(path: string, body: unknown, token: string): Promise<any> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`PATCH ${path} failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}
