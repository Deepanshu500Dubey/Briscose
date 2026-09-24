import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Button } from '@/components/Button';
import { EmployeeChips } from '@/components/EmployeeChips';
import { ShiftStatusChip } from '@/components/StatusChip';
import { EmptyState, ErrorState, SkeletonRows, StaleDataBanner } from '@/components/States';
import { StaffingGauge } from '@/components/StaffingGauge';
import { WeekPager, weekAnchorToParam } from '@/components/WeekPager';
import { useShifts } from '@/features/shifts/api';
import { formatDayLabel, formatTime, fromIsoDate } from '@/lib/dates';
import { useUiStore } from '@/stores/ui';

import { AssignDrawer } from './AssignDrawer';
import { CreateShiftModal } from './CreateShiftModal';

export function StaffingBoardPage() {
  const locationId = useUiStore((s) => s.selectedLocationId);
  const [anchor, setAnchor] = useState(new Date());
  const [createOpen, setCreateOpen] = useState(false);
  // An id, not a snapshot — so the drawer's header (staffed count, status)
  // stays live as assignment mutations invalidate and refetch `shifts`,
  // instead of freezing at whatever it looked like when the drawer opened.
  const [assigningShiftId, setAssigningShiftId] = useState<string | null>(null);
  const week = weekAnchorToParam(anchor);

  const { data: shifts, isLoading, isError, refetch } = useShifts({
    locationId: locationId ?? undefined,
    week,
    enabled: Boolean(locationId),
  });
  const assigningShift = shifts?.find((s) => s.id === assigningShiftId) ?? null;
  const unfilledCount = shifts?.filter((s) => s.status === 'unfilled').length ?? 0;

  if (!locationId) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl font-bold">Staffing board</h1>
          {unfilledCount > 0 && (
            <Link
              to="/manage/unfilled"
              className="rounded-full border border-status-bad-line bg-status-bad-bg px-2.5 py-0.5 font-display text-xs font-semibold uppercase tracking-wide text-status-bad-fg hover:brightness-95"
            >
              {unfilledCount} unfilled
            </Link>
          )}
        </div>
        <div className="flex items-center gap-3">
          <WeekPager anchor={anchor} onChange={setAnchor} />
          <Button variant="gold" onClick={() => setCreateOpen(true)}>
            + Create shift
          </Button>
        </div>
      </div>

      {isLoading ? (
        <SkeletonRows count={5} />
      ) : isError && !shifts ? (
        <ErrorState message="Couldn't load the staffing board." onRetry={() => refetch()} />
      ) : !shifts || shifts.length === 0 ? (
        <EmptyState
          title="No shifts created for this week yet"
          action={{ label: 'Create shift', onClick: () => setCreateOpen(true) }}
        />
      ) : (
        <>
          {isError && <StaleDataBanner onRetry={() => refetch()} />}
          <div className="overflow-x-auto rounded-lg border border-line bg-white shadow-card">
            <table className="w-full min-w-[720px] text-sm">
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
                {shifts.map((shift) => (
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
                      {shift.status !== 'cancelled' && (
                        <Button variant="outline" onClick={() => setAssigningShiftId(shift.id)}>
                          Assign
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <CreateShiftModal open={createOpen} onOpenChange={setCreateOpen} locationId={locationId} />
      {assigningShift && (
        <AssignDrawer shift={assigningShift} onClose={() => setAssigningShiftId(null)} />
      )}
    </div>
  );
}
