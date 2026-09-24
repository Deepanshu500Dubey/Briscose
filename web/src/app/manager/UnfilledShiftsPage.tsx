import { addWeeks } from 'date-fns';
import { useState } from 'react';

import { Button } from '@/components/Button';
import { EmployeeChips } from '@/components/EmployeeChips';
import { ShiftStatusChip } from '@/components/StatusChip';
import { EmptyState, ErrorState, SkeletonRows, StaleDataBanner } from '@/components/States';
import { StaffingGauge } from '@/components/StaffingGauge';
import { weekAnchorToParam } from '@/components/WeekPager';
import { useShifts } from '@/features/shifts/api';
import { formatDayLabel, formatTime, fromIsoDate } from '@/lib/dates';
import { useUiStore } from '@/stores/ui';

import { AssignDrawer } from './AssignDrawer';

/** MGR-05 Unfilled Shift Resolution. There's no dedicated backend view for
 * this — it's the same GET /shifts data as the staffing board, filtered to
 * status === 'unfilled' and widened to the next two weeks (an unfilled
 * shift is exactly the kind of thing a manager needs to see coming, not
 * just for the week they happen to have open). Assigning uses the same
 * override-capable drawer as the staffing board. */
export function UnfilledShiftsPage() {
  const locationId = useUiStore((s) => s.selectedLocationId);
  const [assigningShiftId, setAssigningShiftId] = useState<string | null>(null);
  const today = new Date();
  const thisWeek = weekAnchorToParam(today);
  const nextWeek = weekAnchorToParam(addWeeks(today, 1));

  const week1 = useShifts({ locationId: locationId ?? undefined, week: thisWeek, enabled: Boolean(locationId) });
  const week2 = useShifts({ locationId: locationId ?? undefined, week: nextWeek, enabled: Boolean(locationId) });

  const isLoading = week1.isLoading || week2.isLoading;
  const isError = week1.isError || week2.isError;
  const hasData = week1.data !== undefined || week2.data !== undefined;
  const unfilled = [...(week1.data ?? []), ...(week2.data ?? [])].filter(
    (s) => s.status === 'unfilled',
  );
  const assigningShift = unfilled.find((s) => s.id === assigningShiftId) ?? null;

  function retryAll() {
    week1.refetch();
    week2.refetch();
  }

  if (!locationId) return null;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-2xl font-bold">Unfilled shifts</h1>
        <p className="text-sm text-ink-soft">
          Below minimum staff, with no one left in the eligible pool — this week and next.
          Manually assign anyone at this location to resolve it.
        </p>
      </div>

      {isLoading ? (
        <SkeletonRows count={4} />
      ) : isError && !hasData ? (
        <ErrorState message="Couldn't load unfilled shifts." onRetry={retryAll} />
      ) : unfilled.length === 0 ? (
        <EmptyState title="Nothing unfilled — nice work" />
      ) : (
        <>
          {isError && <StaleDataBanner onRetry={retryAll} />}
          <div className="overflow-x-auto rounded-lg border border-line bg-white shadow-card">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-line bg-line-soft text-left text-xs font-semibold uppercase tracking-wide text-ink-soft">
                  <th className="px-4 py-2.5">Day</th>
                  <th className="px-4 py-2.5">Time</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Staffing</th>
                  <th className="px-4 py-2.5">Team</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {unfilled.map((shift) => (
                  <tr key={shift.id} className="border-b border-line-soft last:border-none">
                    <td className="px-4 py-3 font-display font-semibold">
                      {formatDayLabel(fromIsoDate(shift.date))}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {formatTime(shift.start_time)} – {formatTime(shift.end_time)}
                    </td>
                    <td className="px-4 py-3">
                      <ShiftStatusChip status={shift.status} label={shift.board_label} />
                    </td>
                    <td className="px-4 py-3">
                      <StaffingGauge accepted={shift.accepted_count} max={shift.max_staff} />
                    </td>
                    <td className="px-4 py-3">
                      <EmployeeChips employees={shift.accepted_employees} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button variant="primary" onClick={() => setAssigningShiftId(shift.id)}>
                        Assign
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {assigningShift && (
        <AssignDrawer shift={assigningShift} onClose={() => setAssigningShiftId(null)} />
      )}
    </div>
  );
}
