import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { useChangePassword } from '@/features/auth/api';
import { useLocations } from '@/features/locations/api';
import { ApiError } from '@/lib/apiClient';
import { useAuthStore } from '@/stores/auth';
import { toastSuccess } from '@/stores/toast';

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Required'),
    new_password: z.string().min(8, 'At least 8 characters'),
    confirm_password: z.string().min(1, 'Required'),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    message: "Passwords don't match",
    path: ['confirm_password'],
  });

type PasswordForm = z.infer<typeof passwordSchema>;

/** EMP-07 Profile. The User model only has email/role/home_location_id —
 * no name or contact fields exist yet, so this doesn't pretend to offer
 * editing them (that's a schema decision for someone to make deliberately,
 * not a UI-layer workaround). Password change is real and fully wired. */
export function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const { data: locations } = useLocations();
  const changePassword = useChangePassword();
  const homeLocation = locations?.find((l) => l.id === user?.home_location_id);

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<PasswordForm>({ resolver: zodResolver(passwordSchema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await changePassword.mutateAsync({
        current_password: values.current_password,
        new_password: values.new_password,
      });
      toastSuccess('Password changed');
      reset();
    } catch (error) {
      setError('current_password', {
        message: error instanceof ApiError ? error.message : 'Could not change password',
      });
    }
  });

  return (
    <div className="flex max-w-lg flex-col gap-6">
      <h1 className="font-display text-2xl font-bold">Profile</h1>

      <Card>
        <h2 className="mb-3 font-display text-lg font-bold">Account</h2>
        <dl className="flex flex-col gap-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-ink-soft">Email</dt>
            <dd className="font-medium">{user?.email}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-ink-soft">Role</dt>
            <dd className="font-medium capitalize">{user?.role}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-ink-soft">Home location</dt>
            <dd className="font-medium">{homeLocation?.name ?? '—'}</dd>
          </div>
        </dl>
      </Card>

      <Card>
        <h2 className="mb-3 font-display text-lg font-bold">Change password</h2>
        <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-soft">Current password</span>
            <input type="password" className="input" {...register('current_password')} />
            {errors.current_password && (
              <span className="text-xs text-status-bad-fg">{errors.current_password.message}</span>
            )}
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-soft">New password</span>
            <input type="password" className="input" {...register('new_password')} />
            {errors.new_password && (
              <span className="text-xs text-status-bad-fg">{errors.new_password.message}</span>
            )}
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-soft">Confirm new password</span>
            <input type="password" className="input" {...register('confirm_password')} />
            {errors.confirm_password && (
              <span className="text-xs text-status-bad-fg">{errors.confirm_password.message}</span>
            )}
          </label>
          <Button type="submit" disabled={changePassword.isPending} className="mt-1">
            {changePassword.isPending ? 'Changing…' : 'Change password'}
          </Button>
        </form>
      </Card>
    </div>
  );
}
