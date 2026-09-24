import { useEffect, useMemo } from 'react';

import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { DayToggleRow } from '@/components/DayToggleRow';
import { ErrorState, SkeletonRows } from '@/components/States';
import { useAvailability, useSaveAvailability } from '@/features/availability/api';
import { rollingAvailabilityWindow, toIsoDate } from '@/lib/dates';
import { useAvailabilityDraftStore } from '@/stores/availabilityDraft';
import { toastError, toastSuccess } from '@/stores/toast';
import type { AvailabilityDayInput } from '@/types/api';

export function AvailabilityPage() {
  const window = useMemo(() => rollingAvailabilityWindow(), []);
  const { data: existing, isLoading, isError, refetch } = useAvailability();
  const save = useSaveAvailability();

  const days = useAvailabilityDraftStore((s) => s.days);
  const dirtyDates = useAvailabilityDraftStore((s) => s.dirtyDates);
  const setInitial = useAvailabilityDraftStore((s) => s.setInitial);
  const updateDay = useAvailabilityDraftStore((s) => s.updateDay);
  const markSaved = useAvailabilityDraftStore((s) => s.markSaved);

  // Seed the draft once server data has loaded: existing rows as-is, any
  // day in the window with no row yet defaulting to "not available".
  useEffect(() => {
    if (!existing) return;
    const byDate = new Map(existing.map((row) => [row.date, row]));
    setInitial(
      window.map((date) => {
        const iso = toIsoDate(date);
        const row = byDate.get(iso);
        return row
          ? {
              date: iso,
              is_available: row.is_available,
              start_time: row.start_time,
              end_time: row.end_time,
            }
          : { date: iso, is_available: false, start_time: null, end_time: null };
      }),
    );
    // Only re-seed when the server data identity changes, not on every
    // render — otherwise in-progress edits would be clobbered.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existing]);

  const rowError = (day: (typeof days)[string] | undefined): string | undefined => {
    if (!day?.is_available) return undefined;
    if (!day.start_time || !day.end_time) return 'Set a time range';
    if (day.start_time >= day.end_time) return 'Start must be before end';
    return undefined;
  };

  const hasErrors = window.some((date) => rowError(days[toIsoDate(date)]));
  const hasUnsaved = dirtyDates.size > 0;

  async function handleSave() {
    const payload: AvailabilityDayInput[] = window.map((date) => {
      const iso = toIsoDate(date);
      const day = days[iso];
      return {
        date: iso,
        is_available: day?.is_available ?? false,
        start_time: day?.is_available ? day.start_time : null,
        end_time: day?.is_available ? day.end_time : null,
      };
    });
    try {
      await save.mutateAsync(payload);
      markSaved();
      toastSuccess('Availability saved');
    } catch (error) {
      toastError(error instanceof Error ? error.message : 'Could not save availability');
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">Set availability</h1>
          <p className="text-sm text-ink-soft">The next 14 days — toggle each day and set a time range.</p>
        </div>
        <Button onClick={handleSave} disabled={!hasUnsaved || hasErrors || save.isPending}>
          {save.isPending ? 'Saving…' : hasUnsaved ? 'Save changes' : 'Saved'}
        </Button>
      </div>

      <Card>
        {isLoading ? (
          <SkeletonRows count={6} />
        ) : isError ? (
          <ErrorState message="Couldn't load your availability." onRetry={() => refetch()} />
        ) : (
          <div className="flex flex-col gap-2">
            {window.map((date) => {
              const iso = toIsoDate(date);
              const day = days[iso];
              if (!day) return null;
              return (
                <DayToggleRow
                  key={iso}
                  date={date}
                  day={day}
                  dirty={dirtyDates.has(iso)}
                  error={rowError(day)}
                  onChange={(patch) => updateDay(iso, patch)}
                />
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
