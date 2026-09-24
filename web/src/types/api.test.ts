import { describe, expect, it } from 'vitest';

import { isChooseShiftResult } from './api';
import type { ClockInResult } from './api';

describe('isChooseShiftResult', () => {
  it('is false for a normal TimeEntryResponse', () => {
    const result = {
      id: 't1',
      shift_id: 's1',
      employee_id: 'e1',
      clock_in_at: '2026-08-27T00:00:00Z',
      clock_out_at: null,
      flag: 'none',
    } as unknown as ClockInResult;

    expect(isChooseShiftResult(result)).toBe(false);
  });

  it('is true when the backend returns the ambiguous-shift choice shape', () => {
    const result: ClockInResult = {
      choose_shift: [
        { id: 's1', date: '2026-08-27', start_time: '08:00:00', end_time: '12:00:00', location_id: 'l1' },
        { id: 's2', date: '2026-08-27', start_time: '13:00:00', end_time: '17:00:00', location_id: 'l1' },
      ],
    };

    expect(isChooseShiftResult(result)).toBe(true);
    // Narrows the type — this would be a compile error if it didn't.
    if (isChooseShiftResult(result)) {
      expect(result.choose_shift).toHaveLength(2);
    }
  });

  it('is true even for an empty choose_shift array (still the ambiguous shape)', () => {
    const result: ClockInResult = { choose_shift: [] };
    expect(isChooseShiftResult(result)).toBe(true);
  });
});
