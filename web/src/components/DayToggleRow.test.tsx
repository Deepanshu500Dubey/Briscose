import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { AvailabilityDayDraft } from '@/stores/availabilityDraft';

import { DayToggleRow } from './DayToggleRow';

const baseDay = (overrides: Partial<AvailabilityDayDraft> = {}): AvailabilityDayDraft => ({
  date: '2026-08-27',
  is_available: false,
  start_time: null,
  end_time: null,
  ...overrides,
});

describe('DayToggleRow', () => {
  it('shows "Not available" and hides time inputs when off', () => {
    render(
      <DayToggleRow date={new Date(2026, 7, 27)} day={baseDay()} dirty={false} onChange={() => {}} />,
    );
    expect(screen.getByText('Not available')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('shows start/end time inputs when available, defaulting to 08:00–16:00', () => {
    render(
      <DayToggleRow
        date={new Date(2026, 7, 27)}
        day={baseDay({ is_available: true })}
        dirty={false}
        onChange={() => {}}
      />,
    );
    const times = document.querySelectorAll('input[type="time"]');
    expect(times).toHaveLength(2);
    expect((times[0] as HTMLInputElement).value).toBe('08:00');
    expect((times[1] as HTMLInputElement).value).toBe('16:00');
  });

  it('turning the toggle on defaults start/end times via onChange', () => {
    const onChange = vi.fn();
    render(
      <DayToggleRow date={new Date(2026, 7, 27)} day={baseDay()} dirty={false} onChange={onChange} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Available on Thu 27 Aug' }));

    expect(onChange).toHaveBeenCalledWith({
      is_available: true,
      start_time: '08:00:00',
      end_time: '16:00:00',
    });
  });

  it('turning the toggle off nulls out both times', () => {
    const onChange = vi.fn();
    render(
      <DayToggleRow
        date={new Date(2026, 7, 27)}
        day={baseDay({ is_available: true, start_time: '09:00:00', end_time: '17:00:00' })}
        dirty={false}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Available on Thu 27 Aug' }));

    expect(onChange).toHaveBeenCalledWith({ is_available: false, start_time: null, end_time: null });
  });

  it('editing the start time reports HH:mm:ss back through onChange', () => {
    const onChange = vi.fn();
    render(
      <DayToggleRow
        date={new Date(2026, 7, 27)}
        day={baseDay({ is_available: true, start_time: '08:00:00', end_time: '16:00:00' })}
        dirty={false}
        onChange={onChange}
      />,
    );

    const [startInput] = document.querySelectorAll('input[type="time"]');
    fireEvent.change(startInput, { target: { value: '09:30' } });

    expect(onChange).toHaveBeenCalledWith({ start_time: '09:30:00' });
  });

  it('shows a validation error message when given one', () => {
    render(
      <DayToggleRow
        date={new Date(2026, 7, 27)}
        day={baseDay({ is_available: true })}
        dirty={false}
        error="Start time must be before end time"
        onChange={() => {}}
      />,
    );
    expect(screen.getByText('Start time must be before end time')).toBeInTheDocument();
  });
});
