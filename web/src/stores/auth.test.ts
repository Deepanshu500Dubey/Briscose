import { beforeEach, describe, expect, it } from 'vitest';

import { useAuthStore } from './auth';

describe('useAuthStore', () => {
  beforeEach(() => {
    useAuthStore.getState().clear();
  });

  it('starts with no session', () => {
    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.user).toBeNull();
  });

  it('setSession stores both tokens', () => {
    useAuthStore.getState().setSession({ access_token: 'access-1', refresh_token: 'refresh-1' });
    const state = useAuthStore.getState();
    expect(state.accessToken).toBe('access-1');
    expect(state.refreshToken).toBe('refresh-1');
  });

  it('setUser stores the user without touching tokens', () => {
    useAuthStore.getState().setSession({ access_token: 'access-1', refresh_token: 'refresh-1' });
    useAuthStore.getState().setUser({
      id: 'u1',
      email: 'manager@example.com',
      role: 'manager',
    } as never);

    const state = useAuthStore.getState();
    expect(state.user?.email).toBe('manager@example.com');
    expect(state.accessToken).toBe('access-1');
  });

  it('clear resets tokens and user together', () => {
    useAuthStore.getState().setSession({ access_token: 'access-1', refresh_token: 'refresh-1' });
    useAuthStore.getState().setUser({ id: 'u1', email: 'a@b.com', role: 'employee' } as never);

    useAuthStore.getState().clear();

    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.user).toBeNull();
  });

  it('a later setSession call rotates both tokens (refresh behaviour)', () => {
    useAuthStore.getState().setSession({ access_token: 'access-1', refresh_token: 'refresh-1' });
    useAuthStore.getState().setSession({ access_token: 'access-2', refresh_token: 'refresh-2' });

    const state = useAuthStore.getState();
    expect(state.accessToken).toBe('access-2');
    expect(state.refreshToken).toBe('refresh-2');
  });
});
