import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import type { UserResponse } from '@/types/api';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserResponse | null;
  setSession: (tokens: { access_token: string; refresh_token: string }) => void;
  setUser: (user: UserResponse) => void;
  clear: () => void;
}

/** Session state only — no API calls live here (see src/lib/apiClient.ts),
 * so this store has no dependency on the fetch layer and can't create a
 * circular import between the two. */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setSession: (tokens) =>
        set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token }),
      setUser: (user) => set({ user }),
      clear: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    { name: 'crew-auth' },
  ),
);
