import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatusChip } from '@/components/StatusChip';
import { ErrorState, SkeletonRows } from '@/components/States';
import { useLocations } from '@/features/locations/api';
import { useAllUsers, useProvisionUser } from '@/features/users/api';
import { ApiError } from '@/lib/apiClient';
import { toastError, toastSuccess } from '@/stores/toast';

const userSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(8, 'At least 8 characters'),
  role: z.enum(['employee', 'manager', 'admin']),
  location_ids: z.array(z.string()).default([]),
});

type UserForm = z.infer<typeof userSchema>;

/** Admin-only: the user half of Super Admin management — wraps the
 * existing POST/GET /users exactly as a Manager already can via curl, just
 * with a form instead. Admin may provision any role at any location; a
 * Manager provisioning from their own portal is unchanged and still
 * restricted to employees at locations they manage (enforced server-side
 * either way — this UI doesn't duplicate that logic, it just doesn't
 * bother offering choices the backend would reject). */
export function AdminUsersPage() {
  const { data: users, isLoading, isError, refetch } = useAllUsers(true);
  const { data: locations } = useLocations();
  const provisionUser = useProvisionUser();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<UserForm>({
    resolver: zodResolver(userSchema),
    defaultValues: { role: 'employee', location_ids: [] },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await provisionUser.mutateAsync(values);
      toastSuccess('User provisioned');
      reset({ email: '', password: '', role: 'employee', location_ids: [] });
    } catch (error) {
      toastError(error instanceof ApiError ? error.message : 'Could not provision user');
    }
  });

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_22rem]">
      <div className="flex flex-col gap-3">
        <h1 className="font-display text-2xl font-bold">Users</h1>
        {isLoading ? (
          <SkeletonRows count={6} />
        ) : isError ? (
          <ErrorState message="Couldn't load users." onRetry={() => refetch()} />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line bg-white shadow-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-line-soft text-left text-xs font-semibold uppercase tracking-wide text-ink-soft">
                  <th className="px-4 py-2.5">Email</th>
                  <th className="px-4 py-2.5">Role</th>
                  <th className="px-4 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {(users ?? []).map((u) => (
                  <tr key={u.id} className="border-b border-line-soft last:border-none">
                    <td className="px-4 py-3 font-medium">{u.email}</td>
                    <td className="px-4 py-3 capitalize">{u.role}</td>
                    <td className="px-4 py-3">
                      <StatusChip tone={u.is_active ? 'ok' : 'neutral'}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </StatusChip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Card className="h-fit">
        <h2 className="mb-3 font-display text-lg font-bold">Provision a user</h2>
        <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-soft">Email</span>
            <input type="email" className="input" {...register('email')} />
            {errors.email && <span className="text-xs text-status-bad-fg">{errors.email.message}</span>}
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-soft">Temporary password</span>
            <input type="password" className="input" {...register('password')} />
            {errors.password && (
              <span className="text-xs text-status-bad-fg">{errors.password.message}</span>
            )}
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-soft">Role</span>
            <select className="input" {...register('role')}>
              <option value="employee">Employee</option>
              <option value="manager">Manager</option>
              <option value="admin">Admin</option>
            </select>
          </label>
          {locations && locations.length > 0 && (
            <fieldset className="flex flex-col gap-1 text-sm">
              <legend className="mb-1 font-semibold text-ink-soft">Locations</legend>
              <div className="flex max-h-32 flex-col gap-1 overflow-y-auto rounded-md border border-line p-2">
                {locations.map((loc) => (
                  <label key={loc.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" value={loc.id} {...register('location_ids')} />
                    {loc.name}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <Button type="submit" disabled={provisionUser.isPending} className="mt-1">
            {provisionUser.isPending ? 'Creating…' : 'Provision user'}
          </Button>
        </form>
      </Card>
    </div>
  );
}
