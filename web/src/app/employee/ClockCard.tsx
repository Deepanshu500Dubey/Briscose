import { useState } from 'react';

import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { Modal } from '@/components/Modal';
import { useClockIn, useClockOut } from '@/features/timeClock/api';
import { useTimesheet } from '@/features/timesheets/api';
import { toastError, toastSuccess } from '@/stores/toast';
import { formatTime, formatTimeOfDay, toIsoDate, weekRange } from '@/lib/dates';
import { isChooseShiftResult, type ShiftChoiceResponse } from '@/types/api';

export function ClockCard() {
  const week = toIsoDate(weekRange().start);
  const { data: timesheet, isLoading } = useTimesheet({ week });
  const clockIn = useClockIn();
  const clockOut = useClockOut();
  const [choices, setChoices] = useState<ShiftChoiceResponse[] | null>(null);

  // Derived from this week's timesheet — see features/timeClock/api.ts for
  // why there's no dedicated "current status" endpoint to read this from
  // directly, and why that's a safe simplification for the MVP.
  const openEntry = timesheet?.days.flatMap((d) => d.entries).find((e) => e.clock_out === null);

  async function handleClockIn(shiftId?: string) {
    try {
      const { status, result } = await clockIn.mutateAsync(shiftId);
      if (isChooseShiftResult(result)) {
        setChoices(result.choose_shift);
        return;
      }
      setChoices(null);
      toastSuccess(status === 201 ? 'Clocked in' : 'You were already clocked in');
    } catch (error) {
      toastError(error instanceof Error ? error.message : 'Could not clock in');
    }
  }

  async function handleClockOut() {
    try {
      await clockOut.mutateAsync();
      toastSuccess('Clocked out');
    } catch (error) {
      toastError(error instanceof Error ? error.message : 'Could not clock out');
    }
  }

  return (
    <Card className="flex items-center justify-between">
      <div>
        <h2 className="font-display text-lg font-bold">Time clock</h2>
        {isLoading ? (
          <p className="text-sm text-ink-soft">Loading…</p>
        ) : openEntry ? (
          <p className="text-sm text-ink-soft">Clocked in since {formatTimeOfDay(openEntry.clock_in)}</p>
        ) : (
          <p className="text-sm text-ink-soft">Not clocked in</p>
        )}
      </div>

      {openEntry ? (
        <Button variant="danger" onClick={handleClockOut} disabled={clockOut.isPending}>
          Clock out
        </Button>
      ) : (
        <Button variant="gold" onClick={() => handleClockIn()} disabled={clockIn.isPending}>
          Clock in
        </Button>
      )}

      <Modal
        open={choices !== null}
        onOpenChange={(open) => !open && setChoices(null)}
        title="Which shift are you clocking in for?"
        description="You have two accepted shifts today with a gap between them."
      >
        <div className="flex flex-col gap-2">
          {choices?.map((shift) => (
            <button
              key={shift.id}
              onClick={() => handleClockIn(shift.id)}
              className="rounded-lg border border-line px-4 py-3 text-left text-sm hover:border-brand-navy hover:bg-line-soft"
            >
              {formatTime(shift.start_time)} – {formatTime(shift.end_time)}
            </button>
          ))}
        </div>
      </Modal>
    </Card>
  );
}
