import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { Button } from '@/components/Button';
import { useLogin } from '@/features/auth/api';
import { ApiError } from '@/lib/apiClient';
import { useAuthStore } from '@/stores/auth';

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginForm = z.infer<typeof loginSchema>;

export function LoginPage() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const navigate = useNavigate();
  const login = useLogin();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  if (accessToken) return <Navigate to="/" replace />;

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      const me = await login.mutateAsync(values);
      navigate(me.role === 'employee' ? '/app' : '/manage/dashboard', { replace: true });
    } catch (error) {
      setServerError(error instanceof ApiError ? error.message : 'Something went wrong.');
    }
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-navy-deep px-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-8 shadow-card">
        <div className="mb-6 flex flex-col gap-0.5">
          <span className="font-display text-2xl font-extrabold tracking-wide text-ink">BRISCOES</span>
          {/* brand-gold (#DD9200) is ~2.6:1 on white — fine as a large
              decorative fill (see the header logos on navy), but fails
              WCAG AA (4.5:1) for small text on a light background (caught
              by the E2E suite's axe-core pass). status-warn-fg is the same
              warm tone tuned for on-light text and clears ~6.5:1. */}
          <span className="font-display text-sm font-semibold uppercase tracking-[0.28em] text-status-warn-fg">
            Crew
          </span>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <div>
            <label htmlFor="email" className="mb-1 block text-sm font-semibold text-ink-soft">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
              {...register('email')}
            />
            {errors.email && <p className="mt-1 text-xs text-status-bad-fg">{errors.email.message}</p>}
          </div>

          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-semibold text-ink-soft">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
              {...register('password')}
            />
            {errors.password && <p className="mt-1 text-xs text-status-bad-fg">{errors.password.message}</p>}
          </div>

          {serverError && (
            <div className="rounded-lg border border-status-bad-line bg-status-bad-bg px-3 py-2 text-sm text-status-bad-fg">
              {serverError}
            </div>
          )}

          <Button type="submit" disabled={login.isPending} className="mt-2 w-full">
            {login.isPending ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </div>
    </div>
  );
}
