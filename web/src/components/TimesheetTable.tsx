import { formatDayLabel, formatTimeOfDay, fromIsoDate } from '@/lib/dates';
import type { TimesheetResponse } from '@/types/api';

import { TimeEntryFlagChip } from './StatusChip';

export function TimesheetTable({ timesheet }: { timesheet: TimesheetResponse }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-white shadow-card">
      <table className="w-full min-w-[560px] text-sm">
        <thead>
          <tr className="border-b border-line bg-line-soft text-left text-xs font-semibold uppercase tracking-wide text-ink-soft">
            <th className="px-4 py-2.5">Day</th>
            <th className="px-4 py-2.5">Entries</th>
            <th className="px-4 py-2.5">Hours</th>
          </tr>
        </thead>
        <tbody>
          {timesheet.days.map((day) => (
            <tr key={day.date} className="border-b border-line-soft last:border-none align-top">
              <td className="px-4 py-3 font-display font-semibold">
                {formatDayLabel(fromIsoDate(day.date))}
              </td>
              <td className="px-4 py-3">
                {day.entries.length === 0 ? (
                  <span className="text-ink-faint">—</span>
                ) : (
                  <div className="flex flex-col gap-1">
                    {day.entries.map((entry) => (
                      <div key={entry.id} className="flex items-center gap-2">
                        <span className="font-mono text-xs">
                          {formatTimeOfDay(entry.clock_in)} –{' '}
                          {entry.clock_out ? formatTimeOfDay(entry.clock_out) : 'in progress'}
                        </span>
                        <TimeEntryFlagChip flag={entry.flag} />
                      </div>
                    ))}
                  </div>
                )}
              </td>
              <td className="px-4 py-3 font-mono">
                {day.total_hours.toFixed(2)}
                {day.over_daily_limit && (
                  <span className="ml-1 text-xs font-semibold text-status-warn-fg">over 8h</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-line bg-line-soft font-semibold">
            <td className="px-4 py-2.5" colSpan={2}>
              Week total
            </td>
            <td className="px-4 py-2.5 font-mono">
              {timesheet.weekly_total_hours.toFixed(2)}
              {timesheet.over_weekly_limit && (
                <span className="ml-1 text-xs font-semibold text-status-warn-fg">over 40h</span>
              )}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
