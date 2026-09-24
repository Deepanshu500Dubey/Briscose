import type { ReactNode } from 'react';

import type { AssignmentStatus, ShiftStatus, TimeEntryFlag } from '@/types/api';

type Tone = 'ok' | 'warn' | 'bad' | 'info' | 'neutral';

const toneClasses: Record<Tone, string> = {
  ok: 'bg-status-ok-bg text-status-ok-fg border-status-ok-line',
  warn: 'bg-status-warn-bg text-status-warn-fg border-status-warn-line',
  bad: 'bg-status-bad-bg text-status-bad-fg border-status-bad-line',
  info: 'bg-status-info-bg text-status-info-fg border-status-info-line',
  neutral: 'bg-line-soft text-ink-soft border-line',
};

export function StatusChip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 font-display text-xs font-semibold uppercase tracking-wide ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}

// Presentational labels only — the stored enum stays small and
// deterministic (see the backend's app/api/shifts.py `_board_label`); this
// mirrors the same computed vocabulary for the pieces the board doesn't
// already send as `board_label`.
const SHIFT_STATUS_TONE: Record<ShiftStatus, Tone> = {
  open: 'warn',
  pending_acceptance: 'info',
  confirmed: 'ok',
  unfilled: 'bad',
  cancelled: 'neutral',
};

export function ShiftStatusChip({ status, label }: { status: ShiftStatus; label: string }) {
  return <StatusChip tone={SHIFT_STATUS_TONE[status]}>{label}</StatusChip>;
}

const ASSIGNMENT_STATUS_TONE: Record<AssignmentStatus, Tone> = {
  offered: 'info',
  accepted: 'ok',
  rejected: 'bad',
  withdrawn: 'neutral',
};

export function AssignmentStatusChip({ status }: { status: AssignmentStatus }) {
  return <StatusChip tone={ASSIGNMENT_STATUS_TONE[status]}>{status}</StatusChip>;
}

const FLAG_LABEL: Record<TimeEntryFlag, string> = {
  none: 'On time',
  unscheduled: 'Unscheduled',
  early_start: 'Early start',
  after_shift_end: 'After shift end',
};

const FLAG_TONE: Record<TimeEntryFlag, Tone> = {
  none: 'ok',
  unscheduled: 'info',
  early_start: 'warn',
  after_shift_end: 'warn',
};

export function TimeEntryFlagChip({ flag }: { flag: TimeEntryFlag }) {
  return <StatusChip tone={FLAG_TONE[flag]}>{FLAG_LABEL[flag]}</StatusChip>;
}
