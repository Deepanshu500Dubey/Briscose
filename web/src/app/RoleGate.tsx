import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuthStore } from '@/stores/auth';
import type { UserRole } from '@/types/api';

/** RequireAuth (rendered above this in the tree) already guarantees `user`
 * is populated by the time this renders. */
export function RoleGate({ allow, children }: { allow: UserRole[]; children: ReactNode }) {
  const user = useAuthStore((s) => s.user);
  if (!user) return null;
  if (!allow.includes(user.role)) {
    return <Navigate to={user.role === 'employee' ? '/app' : '/manage/dashboard'} replace />;
  }
  return <>{children}</>;
}

export function RoleRedirect() {
  const user = useAuthStore((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === 'employee' ? '/app' : '/manage/dashboard'} replace />;
}
