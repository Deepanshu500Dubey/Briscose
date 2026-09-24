import { formatDayLabel, formatTime, fromIsoDate } from '@/lib/dates';
import type { ShiftResponse } from '@/types/api';

import { Button } from './Button';
import { StatusChip } from './StatusChip';

export function EmployeeShiftCard({
  shift,
  onAccept,
  onReject,
  isResponding,
}: {
  shift: ShiftResponse;
  onAccept: () => void;
  onReject: () => void;
  isResponding: boolean;
}) {
  const isPending = shift.my_assignment_status === 'offered';

  return (
    <div className="flex items-center justify-between rounded-lg border border-line bg-white p-4 shadow-card">
      <div>
        <div className="font-display text-base font-semibold text-ink">
          {formatDayLabel(fromIsoDate(shift.date))} · {formatTime(shift.start_time)} –{' '}
          {formatTime(shift.end_time)}
        </div>
        <div className="mt-1">
          {shift.my_assignment_status && <AssignmentChip status={shift.my_assignment_status} />}
        </div>
      </div>
      {isPending && (
        <div className="flex gap-2">
          <Button variant="outline" disabled={isResponding} onClick={onReject}>
            Reject
          </Button>
          <Button variant="primary" disabled={isResponding} onClick={onAccept}>
            Accept
          </Button>
        </div>
      )}
    </div>
  );
}

function AssignmentChip({ status }: { status: NonNullable<ShiftResponse['my_assignment_status']> }) {
  const map = {
    offered: { tone: 'info' as const, label: 'Pending your response' },
    accepted: { tone: 'ok' as const, label: 'Accepted' },
    rejected: { tone: 'bad' as const, label: 'Rejected' },
    withdrawn: { tone: 'neutral' as const, label: 'Withdrawn' },
  };
  const { tone, label } = map[status];
  return <StatusChip tone={tone}>{label}</StatusChip>;
}
