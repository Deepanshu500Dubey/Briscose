import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/apiClient';
import { useAuthStore } from '@/stores/auth';
import type { PasswordChangeRequest, TokenResponse, UserResponse } from '@/types/api';

export function useLogin() {
  const setSession = useAuthStore((s) => s.setSession);
  const setUser = useAuthStore((s) => s.setUser);

  return useMutation({
    mutationFn: async (payload: { email: string; password: string }) => {
      const tokens = await api.post<TokenResponse>('/auth/login', payload);
      setSession(tokens);
      const me = await api.get<UserResponse>('/auth/me');
      setUser(me);
      return me;
    },
  });
}

/** Re-validates the persisted session on app boot — a token restored from
 * localStorage might have been revoked/expired since the last visit. */
export function useMe(enabled: boolean) {
  const setUser = useAuthStore((s) => s.setUser);
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const me = await api.get<UserResponse>('/auth/me');
      setUser(me);
      return me;
    },
    enabled,
    retry: false,
    staleTime: 60_000,
  });
}

export function useChangePassword() {
  const setSession = useAuthStore((s) => s.setSession);
  return useMutation({
    mutationFn: async (payload: PasswordChangeRequest) => {
      const tokens = await api.patch<TokenResponse>('/auth/password', payload);
      // The change bumps token_version server-side, invalidating the
      // access token this very request was authenticated with — swap in
      // the fresh pair immediately so the caller isn't logged out.
      setSession(tokens);
      return tokens;
    },
  });
}

export function useLogout() {
  const clear = useAuthStore((s) => s.clear);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const refreshToken = useAuthStore.getState().refreshToken;
      if (refreshToken) {
        await api.post('/auth/logout', { refresh_token: refreshToken }).catch(() => undefined);
      }
    },
    onSettled: () => {
      clear();
      queryClient.clear();
    },
  });
}
