import { addDays, format, parseISO, startOfWeek } from 'date-fns';

export const ISO_DATE = 'yyyy-MM-dd';

export function toIsoDate(date: Date): string {
  return format(date, ISO_DATE);
}

export function fromIsoDate(iso: string): Date {
  return parseISO(iso);
}

/** Today through today+13 — the rolling availability window (project
 * blueprint, Section 8 & the backend's app/api/availability.py). Recomputed
 * on every call, never stored. */
export function rollingAvailabilityWindow(): Date[] {
  const today = new Date();
  return Array.from({ length: 14 }, (_, i) => addDays(today, i));
}

/** Monday..Sunday containing `anchor` (or today) — matches the backend's
 * own week-range helper in app/api/shifts.py / timesheets.py. */
export function weekRange(anchor: Date = new Date()): { start: Date; end: Date } {
  const start = startOfWeek(anchor, { weekStartsOn: 1 });
  return { start, end: addDays(start, 6) };
}

export function formatDayLabel(date: Date): string {
  return format(date, 'EEE d MMM');
}

export function formatTime(time: string): string {
  // "08:00:00" -> "8:00 AM"
  const [h, m] = time.split(':').map(Number);
  const d = new Date();
  d.setHours(h, m, 0, 0);
  return format(d, 'h:mm a');
}

export function formatDateTime(iso: string): string {
  return format(parseISO(iso), "d MMM yyyy 'at' h:mm a");
}

/** Local (browser) time-of-day from an ISO datetime — for "clocked in
 * since…" style display. Business logic in the backend runs on UTC/the
 * shift's own location timezone; this is a display-only convenience. */
export function formatTimeOfDay(iso: string): string {
  return format(parseISO(iso), 'h:mm a');
}
