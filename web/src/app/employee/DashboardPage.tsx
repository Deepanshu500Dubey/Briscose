import { EmployeeShiftCard } from '@/components/ShiftCard';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/States';
import { useAcceptAssignment, useRejectAssignment } from '@/features/assignments/api';
import { useShifts } from '@/features/shifts/api';
import { toastError, toastSuccess } from '@/stores/toast';

import { ClockCard } from './ClockCard';

export function DashboardPage() {
  // This week's assignments — Employee Dashboard scope for the MVP (a
  // dedicated "My Shifts" screen spanning future weeks, EMP-03 in the
  // blueprint, wasn't in the requested flow list).
  const { data: shifts, isLoading, isError, refetch } = useShifts({});
  const accept = useAcceptAssignment();
  const reject = useRejectAssignment();

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
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-2xl font-bold">Dashboard</h1>

      <ClockCard />

      <div>
        <h2 className="mb-3 font-display text-lg font-bold">This week's shifts</h2>
        {isLoading ? (
          <SkeletonRows />
        ) : isError ? (
          <ErrorState message="Couldn't load your shifts." onRetry={() => refetch()} />
        ) : !shifts || shifts.length === 0 ? (
          <EmptyState title="No shifts this week yet" />
        ) : (
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
        )}
      </div>
    </div>
  );
}
