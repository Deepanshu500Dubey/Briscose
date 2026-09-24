import { useState } from 'react';

import { Button } from '@/components/Button';
import { Modal } from '@/components/Modal';
import { EmptyState, SkeletonRows } from '@/components/States';
import { useOfferAssignment } from '@/features/assignments/api';
import { useCandidates } from '@/features/shifts/api';
import { useUsers } from '@/features/users/api';
import { formatDayLabel, formatTime, fromIsoDate } from '@/lib/dates';
import { toastError, toastSuccess } from '@/stores/toast';
import type { ShiftResponse } from '@/types/api';

export function AssignDrawer({ shift, onClose }: { shift: ShiftResponse; onClose: () => void }) {
  const { data: candidates, isLoading } = useCandidates(shift.id);
  const { data: allStaff } = useUsers(shift.location_id);
  const offer = useOfferAssignment(shift.id);
  // There's no "list assignments for this shift" endpoint to read back —
  // track who this drawer has just offered so they drop out of the
  // override list immediately, rather than waiting on a query that
  // wouldn't tell us anyway. The candidates list itself is always live
  // (it already excludes anyone assigned, refetched after every offer).
  const [justOffered, setJustOffered] = useState<Set<string>>(new Set());

  const candidateIds = new Set(candidates?.map((c) => c.employee_id));
  const overrideOptions = (allStaff ?? []).filter(
    (u) => u.role === 'employee' && !candidateIds.has(u.id) && !justOffered.has(u.id),
  );

  async function handleAssign(employeeId: string) {
    try {
      await offer.mutateAsync(employeeId);
      setJustOffered((prev) => new Set(prev).add(employeeId));
      toastSuccess('Offer sent');
    } catch (error) {
      toastError(error instanceof Error ? error.message : 'Could not assign employee');
    }
  }

  return (
    <Modal
      open
      onOpenChange={(open) => !open && onClose()}
      title="Assign employees"
      description={`${formatDayLabel(fromIsoDate(shift.date))} · ${formatTime(shift.start_time)}–${formatTime(shift.end_time)} · ${shift.accepted_count}/${shift.max_staff} staffed`}
    >
      <div className="flex flex-col gap-4">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
            Available for this slot
          </h3>
          {isLoading ? (
            <SkeletonRows count={2} />
          ) : !candidates || candidates.length === 0 ? (
            <EmptyState title="No one is available for this slot" />
          ) : (
            <div className="flex flex-col gap-2">
              {candidates.map((c) => (
                <div
                  key={c.employee_id}
                  className="flex items-center justify-between rounded-lg border border-line px-3 py-2"
                >
                  <div className="text-sm">
                    <div className="font-semibold">{c.email}</div>
                    <div className="text-xs text-ink-faint">
                      Available {formatTime(c.available_start_time)}–{formatTime(c.available_end_time)}
                    </div>
                  </div>
                  <Button
                    variant="primary"
                    onClick={() => handleAssign(c.employee_id)}
                    disabled={offer.isPending}
                  >
                    Assign
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        {overrideOptions.length > 0 && (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
              Assign someone else at this location (overrides availability)
            </h3>
            <div className="flex flex-col gap-2">
              {overrideOptions.map((u) => (
                <div
                  key={u.id}
                  className="flex items-center justify-between rounded-lg border border-dashed border-line px-3 py-2"
                >
                  <span className="text-sm">{u.email}</span>
                  <Button variant="outline" onClick={() => handleAssign(u.id)} disabled={offer.isPending}>
                    Assign anyway
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
