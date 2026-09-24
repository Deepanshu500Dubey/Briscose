import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AssignmentStatusChip, ShiftStatusChip, TimeEntryFlagChip } from './StatusChip';

describe('ShiftStatusChip', () => {
  it.each([
    ['open', 'text-status-warn-fg'],
    ['pending_acceptance', 'text-status-info-fg'],
    ['confirmed', 'text-status-ok-fg'],
    ['unfilled', 'text-status-bad-fg'],
    ['cancelled', 'text-ink-soft'],
  ] as const)('renders the backend-provided label and the %s tone', (status, toneClass) => {
    render(<ShiftStatusChip status={status} label="Fully Staffed" />);
    const chip = screen.getByText('Fully Staffed');
    expect(chip).toHaveClass(toneClass);
  });
});

describe('AssignmentStatusChip', () => {
  it.each([
    ['offered', 'text-status-info-fg'],
    ['accepted', 'text-status-ok-fg'],
    ['rejected', 'text-status-bad-fg'],
    ['withdrawn', 'text-ink-soft'],
  ] as const)('renders its own status text as the label with the %s tone', (status, toneClass) => {
    render(<AssignmentStatusChip status={status} />);
    const chip = screen.getByText(status);
    expect(chip).toHaveClass(toneClass);
  });
});

describe('TimeEntryFlagChip', () => {
  it('maps "none" to the friendly "On time" label', () => {
    render(<TimeEntryFlagChip flag="none" />);
    expect(screen.getByText('On time')).toBeInTheDocument();
  });

  it('maps "after_shift_end" to its friendly label with a warn tone', () => {
    render(<TimeEntryFlagChip flag="after_shift_end" />);
    expect(screen.getByText('After shift end')).toHaveClass('text-status-warn-fg');
  });
});
