import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatusChip } from '@/components/StatusChip';
import { ErrorState, SkeletonRows } from '@/components/States';
import { useCreateLocation, useLocations } from '@/features/locations/api';
import { ApiError } from '@/lib/apiClient';
import { toastError, toastSuccess } from '@/stores/toast';

const locationSchema = z.object({
  name: z.string().min(1, 'Required').max(200),
  address: z.string().min(1, 'Required').max(400),
  timezone: z.string().min(1, 'Required'),
});

type LocationForm = z.infer<typeof locationSchema>;

/** Admin-only: the location half of what the blueprint calls Super Admin
 * location/manager management — schema and POST /locations existed, this
 * is the first UI on top of it. Manager assignment to a location still
 * only happens at provisioning time (see AdminUsersPage) — there's no
 * "assign an existing user to another location" endpoint yet. */
export function AdminLocationsPage() {
  const { data: locations, isLoading, isError, refetch } = useLocations();
  const createLocation = useCreateLocation();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<LocationForm>({
    resolver: zodResolver(locationSchema),
    defaultValues: { timezone: 'Australia/Sydney' },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await createLocation.mutateAsync(values);
      toastSuccess('Location created');
      reset({ name: '', address: '', timezone: values.timezone });
    } catch (error) {
      toastError(error instanceof ApiError ? error.message : 'Could not create location');
    }
  });

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_20rem]">
      <div className="flex flex-col gap-3">
        <h1 className="font-display text-2xl font-bold">Locations</h1>
        {isLoading ? (
          <SkeletonRows count={4} />
        ) : isError ? (
          <ErrorState message="Couldn't load locations." onRetry={() => refetch()} />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line bg-white shadow-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-line-soft text-left text-xs font-semibold uppercase tracking-wide text-ink-soft">
                  <th className="px-4 py-2.5">Name</th>
                  <th className="px-4 py-2.5">Address</th>
                  <th className="px-4 py-2.5">Timezone</th>
                  <th className="px-4 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {(locations ?? []).map((loc) => (
                  <tr key={loc.id} className="border-b border-line-soft last:border-none">
                    <td className="px-4 py-3 font-medium">{loc.name}</td>
                    <td className="px-4 py-3 text-ink-soft">{loc.address}</td>
                    <td className="px-4 py-3 font-mono text-xs">{loc.timezone}</td>
                    <td className="px-4 py-3">
                      <StatusChip tone={loc.is_active ? 'ok' : 'neutral'}>
                        {loc.is_active ? 'Active' : 'Inactive'}
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
        <h2 className="mb-3 font-display text-lg font-bold">New location</h2>
        <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-soft">Name</span>
            <input className="input" {...register('name')} />
            {errors.name && <span className="text-xs text-status-bad-fg">{errors.name.message}</span>}
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-soft">Address</span>
            <input className="input" {...register('address')} />
            {errors.address && (
              <span className="text-xs text-status-bad-fg">{errors.address.message}</span>
            )}
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-soft">Timezone (IANA)</span>
            <input className="input" placeholder="Australia/Sydney" {...register('timezone')} />
            {errors.timezone && (
              <span className="text-xs text-status-bad-fg">{errors.timezone.message}</span>
            )}
          </label>
          <Button type="submit" disabled={createLocation.isPending} className="mt-1">
            {createLocation.isPending ? 'Creating…' : 'Create location'}
          </Button>
        </form>
      </Card>
    </div>
  );
}
