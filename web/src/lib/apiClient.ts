import { useAuthStore } from '@/stores/auth';
import type { TokenResponse } from '@/types/api';

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE';
type Params = Record<string, string | number | boolean | undefined | null>;

// Locally, the dev proxy (vite.config.ts) forwards /api/* to the backend
// with the prefix stripped, so the default same-origin '/api' is all that's
// needed. A split-service deployment (frontend and backend as two separate
// Cloud Run services, say) has no such proxy — VITE_API_URL there is the
// backend's own absolute origin, baked in at build time.
const BASE_URL = import.meta.env.VITE_API_URL?.replace(/\/$/, '') || '/api';

function buildUrl(path: string, params?: Params): string {
  const url = new URL(BASE_URL + path, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
  }
  // Same-origin (BASE_URL is a bare path like '/api') deliberately returns
  // only path+search — window.location.origin was just a resolution base
  // for the URL constructor, not where the request should actually go.
  // Cross-origin (BASE_URL is an absolute URL) must keep the real origin,
  // or fetch would silently send the request back to this page's own host.
  return BASE_URL.startsWith('/') ? url.pathname + url.search : url.toString();
}

// A refresh in flight is shared by every caller that races into a 401 at
// the same time, so a burst of concurrent requests only rotates the
// refresh token once.
let refreshPromise: Promise<void> | null = null;

async function refreshSession(): Promise<void> {
  const refreshToken = useAuthStore.getState().refreshToken;
  if (!refreshToken) throw new ApiError(401, 'No refresh token', null);

  const response = await fetch(buildUrl('/auth/refresh'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    useAuthStore.getState().clear();
    throw new ApiError(response.status, 'Session expired', null);
  }
  const tokens = (await response.json()) as TokenResponse;
  useAuthStore.getState().setSession(tokens);
}

interface RequestOptions {
  params?: Params;
  body?: unknown;
}

async function rawFetch(method: Method, path: string, options: RequestOptions): Promise<Response> {
  const { accessToken } = useAuthStore.getState();
  const headers: Record<string, string> = {};
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';

  return fetch(buildUrl(path, options.params), {
    method,
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
}

async function request<T>(method: Method, path: string, options: RequestOptions = {}): Promise<T> {
  let response = await rawFetch(method, path, options);

  // Never retry the refresh call itself, and never retry a 401 from login
  // (no token was sent, so a retry can't help).
  if (response.status === 401 && useAuthStore.getState().accessToken && path !== '/auth/refresh') {
    try {
      refreshPromise ??= refreshSession().finally(() => {
        refreshPromise = null;
      });
      await refreshPromise;
    } catch {
      throw new ApiError(401, 'Your session has expired — please log in again.', null);
    }
    response = await rawFetch(method, path, options);
  }

  if (response.status === 204) return undefined as T;

  const contentType = response.headers.get('content-type') ?? '';
  const isJson = contentType.includes('application/json');
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail =
      isJson && data && typeof data === 'object' && 'detail' in data
        ? (data as { detail: unknown }).detail
        : null;
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((e) => (e as { msg?: string }).msg).join('; ')
          : `Request failed (${response.status})`;
    throw new ApiError(response.status, message, data);
  }

  return data as T;
}

export const api = {
  get: <T>(path: string, params?: Params) => request<T>('GET', path, { params }),
  post: <T>(path: string, body?: unknown, params?: Params) => request<T>('POST', path, { body, params }),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, { body }),
  delete: <T>(path: string, body?: unknown) => request<T>('DELETE', path, { body }),
};
