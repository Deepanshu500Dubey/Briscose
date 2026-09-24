import { useState } from 'react';

import { EmployeeChips } from '@/components/EmployeeChips';
import { ShiftStatusChip } from '@/components/StatusChip';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/States';
import { StaffingGauge } from '@/components/StaffingGauge';
import { WeekPager, weekAnchorToParam } from '@/components/WeekPager';
import { useRoster } from '@/features/shifts/api';
import { formatDayLabel, formatTime, fromIsoDate } from '@/lib/dates';
import { useUiStore } from '@/stores/ui';

export function RosterPage() {
  const locationId = useUiStore((s) => s.selectedLocationId);
  const [anchor, setAnchor] = useState(new Date());
  const week = weekAnchorToParam(anchor);
  const { data: roster, isLoading, isError, refetch } = useRoster(locationId ?? undefined, week);

  if (!locationId) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">Weekly roster</h1>
          <p className="text-sm text-ink-soft">
            Published shifts only — a top-up offer on an already-confirmed shift never removes
            it from here.
          </p>
        </div>
        <WeekPager anchor={anchor} onChange={setAnchor} />
      </div>

      {isLoading ? (
        <SkeletonRows count={5} />
      ) : isError ? (
        <ErrorState message="Couldn't load the roster." onRetry={() => refetch()} />
      ) : !roster || roster.length === 0 ? (
        <EmptyState title="Nothing confirmed yet this week" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-white shadow-card">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-line bg-line-soft text-left text-xs font-semibold uppercase tracking-wide text-ink-soft">
                <th className="px-4 py-2.5">Day</th>
                <th className="px-4 py-2.5">Time</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Staffing</th>
                <th className="px-4 py-2.5">Team</th>
              </tr>
            </thead>
            <tbody>
              {roster.map((shift) => (
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
