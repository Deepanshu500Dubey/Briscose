import * as Toggle from '@radix-ui/react-toggle';

import { formatDayLabel } from '@/lib/dates';
import type { AvailabilityDayDraft } from '@/stores/availabilityDraft';

export function DayToggleRow({
  date,
  day,
  dirty,
  error,
  onChange,
}: {
  date: Date;
  day: AvailabilityDayDraft;
  dirty: boolean;
  error?: string;
  onChange: (patch: Partial<Omit<AvailabilityDayDraft, 'date'>>) => void;
}) {
  return (
    <div
      className={`flex flex-wrap items-center gap-4 rounded-lg border px-4 py-3 ${
        dirty ? 'border-brand-gold-bright bg-status-warn-bg/40' : 'border-line bg-white'
      }`}
    >
      <div className="w-28 shrink-0 font-display text-sm font-semibold text-ink">
        {formatDayLabel(date)}
      </div>

      <Toggle.Root
        pressed={day.is_available}
        onPressedChange={(pressed) =>
          onChange({
            is_available: pressed,
            start_time: pressed ? (day.start_time ?? '08:00:00') : null,
            end_time: pressed ? (day.end_time ?? '16:00:00') : null,
          })
        }
        className="relative h-6 w-11 shrink-0 rounded-full bg-line transition data-[state=on]:bg-status-ok-fg"
        aria-label={`Available on ${formatDayLabel(date)}`}
      >
        <span className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition data-[state=on]:translate-x-5" />
      </Toggle.Root>

      {day.is_available ? (
        <div className="flex items-center gap-2 text-sm">
          <input
            type="time"
            value={(day.start_time ?? '08:00:00').slice(0, 5)}
            onChange={(e) => onChange({ start_time: `${e.target.value}:00` })}
            className="rounded-md border border-line px-2 py-1"
          />
          <span className="text-ink-faint">to</span>
          <input
            type="time"
            value={(day.end_time ?? '16:00:00').slice(0, 5)}
            onChange={(e) => onChange({ end_time: `${e.target.value}:00` })}
            className="rounded-md border border-line px-2 py-1"
          />
        </div>
      ) : (
        <span className="text-sm text-ink-faint">Not available</span>
      )}

      {error && <span className="text-xs text-status-bad-fg">{error}</span>}
    </div>
  );
}
