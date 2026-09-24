import { describe, expect, it } from 'vitest';

import {
  formatDayLabel,
  formatDateTime,
  formatTime,
  formatTimeOfDay,
  fromIsoDate,
  ISO_DATE,
  rollingAvailabilityWindow,
  toIsoDate,
  weekRange,
} from './dates';

describe('toIsoDate / fromIsoDate', () => {
  it('round-trips a date through ISO format', () => {
    const date = new Date(2026, 7, 27); // 27 Aug 2026 (local)
    const iso = toIsoDate(date);
    expect(iso).toBe('2026-08-27');
    expect(toIsoDate(fromIsoDate(iso))).toBe(iso);
  });

  it('uses the yyyy-MM-dd format constant', () => {
    expect(ISO_DATE).toBe('yyyy-MM-dd');
  });
});

describe('rollingAvailabilityWindow', () => {
  it('returns exactly 14 consecutive days starting today', () => {
    const days = rollingAvailabilityWindow();
    expect(days).toHaveLength(14);

    const todayIso = toIsoDate(new Date());
    expect(toIsoDate(days[0])).toBe(todayIso);

    for (let i = 1; i < days.length; i++) {
      const diffMs = days[i].getTime() - days[i - 1].getTime();
      expect(Math.round(diffMs / 86_400_000)).toBe(1);
    }
  });
});

describe('weekRange', () => {
  it('anchors on Monday and ends on Sunday, matching the backend week helper', () => {
    // Wednesday 26 Aug 2026
    const wednesday = new Date(2026, 7, 26);
    const { start, end } = weekRange(wednesday);

    expect(toIsoDate(start)).toBe('2026-08-24'); // Monday
    expect(toIsoDate(end)).toBe('2026-08-30'); // Sunday
  });

  it('treats a Monday anchor as the start of its own week', () => {
    const monday = new Date(2026, 7, 24);
    const { start } = weekRange(monday);
    expect(toIsoDate(start)).toBe(toIsoDate(monday));
  });

  it('treats a Sunday anchor as the end of the week that started the previous Monday', () => {
    const sunday = new Date(2026, 7, 30);
    const { start, end } = weekRange(sunday);
    expect(toIsoDate(start)).toBe('2026-08-24');
    expect(toIsoDate(end)).toBe(toIsoDate(sunday));
  });
});

describe('formatDayLabel', () => {
  it('formats as "Thu 27 Aug"', () => {
    expect(formatDayLabel(new Date(2026, 7, 27))).toBe('Thu 27 Aug');
  });
});

describe('formatTime', () => {
  it('formats a 24h HH:mm:ss string as 12h with AM/PM', () => {
    expect(formatTime('08:00:00')).toBe('8:00 AM');
    expect(formatTime('16:00:00')).toBe('4:00 PM');
    expect(formatTime('00:00:00')).toBe('12:00 AM');
    expect(formatTime('12:30:00')).toBe('12:30 PM');
  });
});

describe('formatDateTime / formatTimeOfDay', () => {
  it('formats an ISO datetime with date and time', () => {
    expect(formatDateTime('2026-08-27T08:05:00Z')).toMatch(/27 Aug 2026 at/);
  });

  it('formats only the local time-of-day portion', () => {
    expect(formatTimeOfDay('2026-08-27T00:05:00Z')).toMatch(/^\d{1,2}:\d{2} (AM|PM)$/);
  });
});
