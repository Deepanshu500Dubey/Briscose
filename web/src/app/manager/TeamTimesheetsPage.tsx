import { useEffect, useState } from 'react';

import { EmptyState, ErrorState, SkeletonRows } from '@/components/States';
import { TimesheetTable } from '@/components/TimesheetTable';
import { WeekPager, weekAnchorToParam } from '@/components/WeekPager';
import { useUsers } from '@/features/users/api';
import { useTimesheet } from '@/features/timesheets/api';
import { useUiStore } from '@/stores/ui';

export function TeamTimesheetsPage() {
  const locationId = useUiStore((s) => s.selectedLocationId);
  const [anchor, setAnchor] = useState(new Date());
  const [employeeId, setEmployeeId] = useState<string>('');
  const week = weekAnchorToParam(anchor);

  const { data: staff, isLoading: staffLoading } = useUsers(locationId ?? undefined);
  const employees = (staff ?? []).filter((u) => u.role === 'employee');

  useEffect(() => {
    if (!employeeId && employees.length > 0) setEmployeeId(employees[0].id);
  }, [employees, employeeId]);

  const {
    data: timesheet,
    isLoading: timesheetLoading,
    isError,
    refetch,
  } = useTimesheet({ employeeId: employeeId || undefined, week });

  if (!locationId) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold">Team timesheets</h1>
        <div className="flex items-center gap-3">
          {employees.length > 0 && (
            <select
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
              className="input"
            >
              {employees.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.email}
                </option>
              ))}
            </select>
          )}
          <WeekPager anchor={anchor} onChange={setAnchor} />
        </div>
      </div>

      {staffLoading || timesheetLoading ? (
        <SkeletonRows count={7} />
      ) : employees.length === 0 ? (
        <EmptyState title="No employees assigned to this location yet" />
      ) : isError || !timesheet ? (
        <ErrorState message="Couldn't load this timesheet." onRetry={() => refetch()} />
      ) : (
        <TimesheetTable timesheet={timesheet} />
      )}
    </div>
  );
}
