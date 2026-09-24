import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuthStore } from '@/stores/auth';

import { api, ApiError } from './apiClient';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('apiClient', () => {
  beforeEach(() => {
    useAuthStore.getState().clear();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends no Authorization header when logged out', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    await api.get('/locations');

    const [, init] = fetchMock.mock.calls[0];
    expect((init?.headers as Record<string, string>)['Authorization']).toBeUndefined();
  });

  it('attaches a Bearer token from the auth store when logged in', async () => {
    useAuthStore.getState().setSession({ access_token: 'token-abc', refresh_token: 'refresh-abc' });
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    await api.get('/locations');

    const [, init] = fetchMock.mock.calls[0];
    expect((init?.headers as Record<string, string>)['Authorization']).toBe('Bearer token-abc');
  });

  it('routes through the /api prefix and serializes query params', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, []));

    await api.get('/shifts', { location_id: 'loc-1', include_cancelled: false });

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/shifts');
    expect(url).toContain('location_id=loc-1');
    // false is a real value that must be sent, only null/undefined are dropped
    expect(url).toContain('include_cancelled=false');
  });

  it('omits undefined/null query params entirely', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, []));

    await api.get('/shifts', { location_id: undefined, week: null });

    const [url] = fetchMock.mock.calls[0];
    expect(url).not.toContain('location_id');
    expect(url).not.toContain('week');
  });

  it('returns undefined for a 204 with no body', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    const result = await api.delete('/assignments/a1');
    expect(result).toBeUndefined();
  });

  it('throws an ApiError with the backend detail string on failure', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(404, { detail: 'Shift not found' }));

    await expect(api.get('/shifts/missing')).rejects.toMatchObject({
      status: 404,
      message: 'Shift not found',
    });
  });

  it('joins a FastAPI validation-error list into one message', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(
      jsonResponse(422, {
        detail: [{ msg: 'field required' }, { msg: 'must be positive' }],
      }),
    );

    await expect(api.post('/shifts', {})).rejects.toMatchObject({
      status: 422,
      message: 'field required; must be positive',
    });
  });

  it('falls back to a generic message when there is no structured detail', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(new Response('Internal error', { status: 500 }));

    await expect(api.get('/shifts')).rejects.toMatchObject({
      status: 500,
      message: 'Request failed (500)',
    });
  });

  describe('401 handling and token refresh', () => {
    it('refreshes the session once on a single 401 and retries the original request', async () => {
      useAuthStore.getState().setSession({ access_token: 'expired', refresh_token: 'refresh-1' });
      const fetchMock = vi.mocked(fetch);

      fetchMock
        .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' })) // original request
        .mockResolvedValueOnce(jsonResponse(200, { access_token: 'fresh', refresh_token: 'refresh-2' })) // refresh
        .mockResolvedValueOnce(jsonResponse(200, { id: 's1' })); // retried request

      const result = await api.get('/shifts/s1');

      expect(result).toEqual({ id: 's1' });
      expect(fetchMock).toHaveBeenCalledTimes(3);
      expect(useAuthStore.getState().accessToken).toBe('fresh');

      // The retried call must use the newly rotated token, not the expired one.
      const [, retryInit] = fetchMock.mock.calls[2];
      expect((retryInit?.headers as Record<string, string>)['Authorization']).toBe('Bearer fresh');
    });

    it('shares one in-flight refresh across concurrent 401s', async () => {
      useAuthStore.getState().setSession({ access_token: 'expired', refresh_token: 'refresh-1' });
      const fetchMock = vi.mocked(fetch);

      let refreshCalls = 0;
      const callsPerPath = new Map<string, number>();
      fetchMock.mockImplementation(async (input) => {
        const url = String(input);
        if (url.includes('/auth/refresh')) {
          refreshCalls++;
          return jsonResponse(200, { access_token: 'fresh', refresh_token: 'refresh-2' });
        }
        // Each distinct path's own first call is a 401; its retry (after the
        // shared refresh resolves) succeeds — tracked per-path so the two
        // concurrent requests below don't interfere with each other's count.
        const path = url.split('?')[0];
        const count = (callsPerPath.get(path) ?? 0) + 1;
        callsPerPath.set(path, count);
        return count === 1 ? jsonResponse(401, { detail: 'expired' }) : jsonResponse(200, { ok: true });
      });

      await Promise.all([api.get('/shifts'), api.get('/notifications')]);

      expect(refreshCalls).toBe(1);
    });

    it('clears the session and throws a friendly error when the refresh token itself is rejected', async () => {
      useAuthStore.getState().setSession({ access_token: 'expired', refresh_token: 'bad-refresh' });
      const fetchMock = vi.mocked(fetch);

      fetchMock
        .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' })) // original request
        .mockResolvedValueOnce(jsonResponse(401, { detail: 'invalid refresh token' })); // refresh fails

      await expect(api.get('/shifts')).rejects.toMatchObject({
        status: 401,
        message: 'Your session has expired — please log in again.',
      });
      expect(useAuthStore.getState().accessToken).toBeNull();
      expect(useAuthStore.getState().refreshToken).toBeNull();
    });

    it('does not attempt a refresh for a 401 with no access token (e.g. a bad login)', async () => {
      const fetchMock = vi.mocked(fetch);
      fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: 'Incorrect email or password' }));

      await expect(api.post('/auth/login', { email: 'a@b.com', password: 'wrong' })).rejects.toMatchObject({
        status: 401,
        message: 'Incorrect email or password',
      });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('never retries a 401 coming from the refresh endpoint itself', async () => {
      useAuthStore.getState().setSession({ access_token: 'expired', refresh_token: 'refresh-1' });
      const fetchMock = vi.mocked(fetch);
      fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: 'bad' }));

      // Calling the refresh path directly as if it were any other request —
      // request() must not loop back into refreshing itself.
      await expect(
        (api as unknown as { patch: (p: string, b?: unknown) => Promise<unknown> }).patch('/auth/refresh', {}),
      ).rejects.toMatchObject({ status: 401 });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });

  it('ApiError carries the raw response body for callers that need it', () => {
    const err = new ApiError(409, 'Email already registered', { detail: 'Email already registered' });
    expect(err).toBeInstanceOf(Error);
    expect(err.status).toBe(409);
    expect(err.body).toEqual({ detail: 'Email already registered' });
  });

  describe('VITE_API_URL — split-service deployment', () => {
    // BASE_URL is computed once at module load from import.meta.env, so
    // each of these needs its own fresh module instance under the env
    // value it's testing — a plain re-import would reuse the first one.
    afterEach(() => {
      vi.unstubAllEnvs();
    });

    it('targets the backend origin directly when VITE_API_URL is a cross-origin URL', async () => {
      vi.stubEnv('VITE_API_URL', 'https://backend-abc123.run.app');
      vi.resetModules();
      const { api: crossOriginApi } = await import('./apiClient');

      const fetchMock = vi.mocked(fetch);
      fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

      await crossOriginApi.get('/locations');

      const [url] = fetchMock.mock.calls[0];
      // Regression check: buildUrl used to return only pathname+search,
      // which silently sent cross-origin requests back to the frontend's
      // own host instead of the real backend once BASE_URL stopped being
      // a bare same-origin path.
      expect(url).toBe('https://backend-abc123.run.app/locations');
    });

    it('strips a trailing slash from VITE_API_URL before joining paths', async () => {
      vi.stubEnv('VITE_API_URL', 'https://backend-abc123.run.app/');
      vi.resetModules();
      const { api: crossOriginApi } = await import('./apiClient');

      const fetchMock = vi.mocked(fetch);
      fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

      await crossOriginApi.get('/locations');

      const [url] = fetchMock.mock.calls[0];
      expect(url).toBe('https://backend-abc123.run.app/locations');
    });

    it('falls back to the same-origin dev-proxy path when VITE_API_URL is unset', async () => {
      vi.stubEnv('VITE_API_URL', undefined);
      vi.resetModules();
      const { api: sameOriginApi } = await import('./apiClient');

      const fetchMock = vi.mocked(fetch);
      fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

      await sameOriginApi.get('/locations');

      const [url] = fetchMock.mock.calls[0];
      expect(url).toBe('/api/locations');
    });
  });
});
