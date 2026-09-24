import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { StaffingGauge } from './StaffingGauge';

describe('StaffingGauge', () => {
  it('shows the raw accepted/max counts', () => {
    render(<StaffingGauge accepted={1} max={3} />);
    expect(screen.getByText('1 / 3 staffed')).toBeInTheDocument();
  });

  it('fills proportionally and uses the warn color while partially staffed', () => {
    const { container } = render(<StaffingGauge accepted={1} max={4} />);
    const fill = container.querySelector('div.h-1\\.5 > div') as HTMLElement;
    expect(fill.style.width).toBe('25%');
    expect(fill.className).toContain('bg-status-warn-fg');
  });

  it('uses the ok color and 100% width once fully staffed', () => {
    const { container } = render(<StaffingGauge accepted={2} max={2} />);
    const fill = container.querySelector('div.h-1\\.5 > div') as HTMLElement;
    expect(fill.style.width).toBe('100%');
    expect(fill.className).toContain('bg-status-ok-fg');
  });

  it('uses the neutral color and 0% width with nobody accepted yet', () => {
    const { container } = render(<StaffingGauge accepted={0} max={2} />);
    const fill = container.querySelector('div.h-1\\.5 > div') as HTMLElement;
    expect(fill.style.width).toBe('0%');
    expect(fill.className).toContain('bg-line');
  });

  it('clamps to 100% width when overstaffed rather than overflowing', () => {
    const { container } = render(<StaffingGauge accepted={5} max={2} />);
    const fill = container.querySelector('div.h-1\\.5 > div') as HTMLElement;
    expect(fill.style.width).toBe('100%');
  });

  it('handles a zero max without dividing by zero', () => {
    const { container } = render(<StaffingGauge accepted={0} max={0} />);
    const fill = container.querySelector('div.h-1\\.5 > div') as HTMLElement;
    expect(fill.style.width).toBe('0%');
  });
});
