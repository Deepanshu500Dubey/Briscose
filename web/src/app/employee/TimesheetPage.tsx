import { useState } from 'react';

import { ErrorState, SkeletonRows } from '@/components/States';
import { TimesheetTable } from '@/components/TimesheetTable';
import { WeekPager, weekAnchorToParam } from '@/components/WeekPager';
import { useTimesheet } from '@/features/timesheets/api';

export function TimesheetPage() {
  const [anchor, setAnchor] = useState(new Date());
  const week = weekAnchorToParam(anchor);
  const { data: timesheet, isLoading, isError, refetch } = useTimesheet({ week });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold">Timesheet</h1>
        <WeekPager anchor={anchor} onChange={setAnchor} />
      </div>

      {isLoading ? (
        <SkeletonRows count={7} />
      ) : isError || !timesheet ? (
        <ErrorState message="Couldn't load your timesheet." onRetry={() => refetch()} />
      ) : (
        <TimesheetTable timesheet={timesheet} />
      )}
    </div>
  );
}
