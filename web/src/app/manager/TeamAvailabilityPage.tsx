import { format } from 'date-fns';
import { useMemo } from 'react';

import { EmptyState, ErrorState, SkeletonRows } from '@/components/States';
import { useTeamAvailability } from '@/features/availability/api';
import { useUsers } from '@/features/users/api';
import { formatTime, rollingAvailabilityWindow, toIsoDate } from '@/lib/dates';
import { useUiStore } from '@/stores/ui';

/** MGR-06 Team & Availability: every staff member at this location and
 * their submitted availability over the same rolling 14-day window
 * employees edit (Section 8). Read-only — a manager sees this to plan
 * assignments, never edits an employee's availability for them. */
export function TeamAvailabilityPage() {
  const locationId = useUiStore((s) => s.selectedLocationId);
  const { data: staff, isLoading: staffLoading, isError: staffErrored, refetch: refetchStaff } =
    useUsers(locationId ?? undefined);
  const employees = useMemo(() => (staff ?? []).filter((u) => u.role === 'employee'), [staff]);
  const window = useMemo(() => rollingAvailabilityWindow(), []);

  const availabilityQueries = useTeamAvailability(employees.map((e) => e.id));
  const isLoadingAvailability = availabilityQueries.some((q) => q.isLoading);

  if (!locationId) return null;

  if (staffLoading) return <SkeletonRows count={5} />;
  if (staffErrored) {
    return <ErrorState message="Couldn't load your team." onRetry={() => refetchStaff()} />;
  }
  if (employees.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="font-display text-2xl font-bold">Team &amp; availability</h1>
        <EmptyState title="No employees assigned to this location yet" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-display text-2xl font-bold">Team &amp; availability</h1>

      {isLoadingAvailability ? (
        <SkeletonRows count={employees.length} />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-white shadow-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-line-soft text-left text-xs font-semibold uppercase tracking-wide text-ink-soft">
                <th className="sticky left-0 bg-line-soft px-4 py-2.5">Employee</th>
                {window.map((date) => (
                  <th key={toIsoDate(date)} className="whitespace-nowrap px-3 py-2.5">
                    {format(date, 'EEE d')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {employees.map((employee, i) => {
                const rows = availabilityQueries[i]?.data ?? [];
                const byDate = new Map(rows.map((r) => [r.date, r]));
                return (
                  <tr key={employee.id} className="border-b border-line-soft last:border-none">
                    <td className="sticky left-0 whitespace-nowrap bg-white px-4 py-2.5 font-medium">
                      {employee.email}
                    </td>
                    {window.map((date) => {
                      const iso = toIsoDate(date);
                      const row = byDate.get(iso);
                      return (
                        <td key={iso} className="px-3 py-2.5 text-xs">
                          {!row || !row.is_available ? (
                            <span className="text-ink-faint">—</span>
                          ) : (
                            <span className="whitespace-nowrap text-status-ok-fg">
                              {row.start_time && formatTime(row.start_time)}–
                              {row.end_time && formatTime(row.end_time)}
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
