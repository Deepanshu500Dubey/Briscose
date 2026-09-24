import { addWeeks, format } from 'date-fns';

import { toIsoDate, weekRange } from '@/lib/dates';

import { Button } from './Button';

export function WeekPager({
  anchor,
  onChange,
}: {
  anchor: Date;
  onChange: (next: Date) => void;
}) {
  const { start, end } = weekRange(anchor);
  return (
    <div className="flex items-center gap-3">
      <Button variant="outline" onClick={() => onChange(addWeeks(anchor, -1))} aria-label="Previous week">
        ←
      </Button>
      <span className="font-display text-sm font-semibold text-ink">
        {format(start, 'd MMM')} – {format(end, 'd MMM yyyy')}
      </span>
      <Button variant="outline" onClick={() => onChange(addWeeks(anchor, 1))} aria-label="Next week">
        →
      </Button>
      <Button variant="outline" onClick={() => onChange(new Date())}>
        This week
      </Button>
    </div>
  );
}

export function weekAnchorToParam(anchor: Date): string {
  return toIsoDate(weekRange(anchor).start);
}
