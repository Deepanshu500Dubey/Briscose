import { useMutation, useQueryClient } from '@tanstack/react-query';

import { ApiError, api } from '@/lib/apiClient';
import type { ClockInResult, TimeEntryResponse } from '@/types/api';

export interface ClockInOutcome {
  /** 201 = freshly clocked in; 409 = already open (soft-success) or an
   * ambiguous-shift choice — both carry a usable body, not an error (see
   * the backend's app/api/time_entries.py), but the UI still needs to tell
   * them apart since a fresh entry and an already-open one both have
   * clock_out: null. */
  status: 201 | 409;
  result: ClockInResult;
}

export function useClockIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (shiftId?: string): Promise<ClockInOutcome> => {
      try {
        const result = await api.post<TimeEntryResponse>(
          '/time-entries/clock-in',
          shiftId ? { shift_id: shiftId } : {},
        );
        return { status: 201, result };
      } catch (error) {
        if (error instanceof ApiError && error.status === 409 && error.body) {
          return { status: 409, result: error.body as ClockInResult };
        }
        throw error;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
      queryClient.invalidateQueries({ queryKey: ['timesheets'] });
    },
  });
}

export function useClockOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<TimeEntryResponse>('/time-entries/clock-out'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
      queryClient.invalidateQueries({ queryKey: ['timesheets'] });
    },
  });
}

export function useForceCloseTimeEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entryId, clockOut }: { entryId: string; clockOut: string }) =>
      api.patch<TimeEntryResponse>(`/time-entries/${entryId}`, { clock_out: clockOut }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['timesheets'] }),
  });
}
