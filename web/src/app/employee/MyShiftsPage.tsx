import { addWeeks } from 'date-fns';
import { useMemo } from 'react';

import { EmployeeShiftCard } from '@/components/ShiftCard';
import { EmptyState, ErrorState, SkeletonRows, StaleDataBanner } from '@/components/States';
import { weekAnchorToParam } from '@/components/WeekPager';
import { useAcceptAssignment, useRejectAssignment } from '@/features/assignments/api';
import { useShifts } from '@/features/shifts/api';
import { toastError, toastSuccess } from '@/stores/toast';

const WEEKS_AHEAD = 4;

/** EMP-03 My Shifts: everything beyond "this week" on the Dashboard —
 * pending, accepted, rejected, past. GET /shifts only ever returns one
 * week, so this fans out across several weeks and merges client-side
 * rather than needing a new "all my shifts" endpoint. */
export function MyShiftsPage() {
  const weeks = useMemo(
    () => Array.from({ length: WEEKS_AHEAD }, (_, i) => weekAnchorToParam(addWeeks(new Date(), i))),
    [],
  );

  // Rules of Hooks forbid calling useShifts in a loop with a dynamic count,
  // but WEEKS_AHEAD is a fixed constant, so four literal calls is safe and
  // simpler than reaching for useQueries here.
  const w0 = useShifts({ week: weeks[0] });
  const w1 = useShifts({ week: weeks[1] });
  const w2 = useShifts({ week: weeks[2] });
  const w3 = useShifts({ week: weeks[3] });
  const queries = [w0, w1, w2, w3];

  const isLoading = queries.some((q) => q.isLoading);
  const isError = queries.some((q) => q.isError);
  const hasData = queries.some((q) => q.data !== undefined);
  const shifts = queries
    .flatMap((q) => q.data ?? [])
    .sort((a, b) => (a.date + a.start_time).localeCompare(b.date + b.start_time));

  const accept = useAcceptAssignment();
  const reject = useRejectAssignment();

  function retryAll() {
    queries.forEach((q) => q.refetch());
  }

  async function handleAccept(assignmentId: string) {
    try {
      await accept.mutateAsync(assignmentId);
      toastSuccess('Shift accepted');
    } catch (error) {
      toastError(error instanceof Error ? error.message : 'Could not accept shift');
    }
  }

  async function handleReject(assignmentId: string) {
    try {
      await reject.mutateAsync(assignmentId);
      toastSuccess('Shift rejected — the manager will need to reassign it');
    } catch (error) {
      toastError(error instanceof Error ? error.message : 'Could not reject shift');
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-2xl font-bold">My shifts</h1>
        <p className="text-sm text-ink-soft">The next {WEEKS_AHEAD} weeks.</p>
      </div>

      {isLoading ? (
        <SkeletonRows count={5} />
      ) : isError && !hasData ? (
        <ErrorState message="Couldn't load your shifts." onRetry={retryAll} />
      ) : shifts.length === 0 ? (
        <EmptyState title="No shifts in the next few weeks yet" />
      ) : (
        <>
          {isError && <StaleDataBanner onRetry={retryAll} />}
          <div className="flex flex-col gap-2">
            {shifts.map((shift) => (
              <EmployeeShiftCard
                key={shift.id}
                shift={shift}
                isResponding={accept.isPending || reject.isPending}
                onAccept={() => shift.my_assignment_id && handleAccept(shift.my_assignment_id)}
                onReject={() => shift.my_assignment_id && handleReject(shift.my_assignment_id)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
