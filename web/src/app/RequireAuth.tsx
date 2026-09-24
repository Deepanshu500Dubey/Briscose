import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useMe } from '@/features/auth/api';
import { Skeleton } from '@/components/States';
import { useAuthStore } from '@/stores/auth';

/** Gates every authenticated route. Re-validates the persisted session
 * against GET /auth/me on mount (a token restored from localStorage may
 * have been revoked/expired since the last visit) — see
 * features/auth/api.ts. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const location = useLocation();
  const { isLoading, isError } = useMe(Boolean(accessToken));

  if (!accessToken) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Skeleton className="h-10 w-40" />
      </div>
    );
  }

  if (isError) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
