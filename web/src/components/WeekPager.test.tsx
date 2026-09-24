import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { toIsoDate } from '@/lib/dates';

import { WeekPager, weekAnchorToParam } from './WeekPager';

describe('WeekPager', () => {
  it('shows the Monday–Sunday range containing the anchor', () => {
    render(<WeekPager anchor={new Date(2026, 7, 26)} onChange={() => {}} />); // Wed 26 Aug 2026
    expect(screen.getByText('24 Aug – 30 Aug 2026')).toBeInTheDocument();
  });

  it('steps back one week on "Previous week"', () => {
    const onChange = vi.fn();
    render(<WeekPager anchor={new Date(2026, 7, 26)} onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'Previous week' }));

    const [next] = onChange.mock.calls[0];
    expect(toIsoDate(next)).toBe('2026-08-19');
  });

  it('steps forward one week on "Next week"', () => {
    const onChange = vi.fn();
    render(<WeekPager anchor={new Date(2026, 7, 26)} onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'Next week' }));

    const [next] = onChange.mock.calls[0];
    expect(toIsoDate(next)).toBe('2026-09-02');
  });

  it('"This week" jumps back to today regardless of the current anchor', () => {
    const onChange = vi.fn();
    render(<WeekPager anchor={new Date(2020, 0, 1)} onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'This week' }));

    const [next] = onChange.mock.calls[0];
    expect(toIsoDate(next)).toBe(toIsoDate(new Date()));
  });
});

describe('weekAnchorToParam', () => {
  it('returns the ISO date of the Monday for any anchor in that week', () => {
    expect(weekAnchorToParam(new Date(2026, 7, 26))).toBe('2026-08-24');
    expect(weekAnchorToParam(new Date(2026, 7, 24))).toBe('2026-08-24');
    expect(weekAnchorToParam(new Date(2026, 7, 30))).toBe('2026-08-24');
  });
});
