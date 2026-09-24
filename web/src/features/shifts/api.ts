import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/apiClient';
import type { CandidateResponse, ShiftResponse } from '@/types/api';

export interface ShiftCreatePayload {
  location_id: string;
  date: string;
  start_time: string;
  end_time: string;
  min_staff: number;
  max_staff: number;
}

/** The staffing board (Manager, requires location_id) or the caller's own
 * assignments (Employee) — same endpoint, scoped server-side by role.
 *
 * `enabled` defaults to true for the Employee case (no location_id is
 * expected there); pass `enabled: Boolean(locationId)` from a Manager
 * screen so the query doesn't fire — and 400 against the backend's
 * location_id-required guard — before a location has been selected. */
export function useShifts(params: { locationId?: string; week?: string; enabled?: boolean }) {
  return useQuery({
    queryKey: ['shifts', params.locationId ?? 'own', params.week ?? 'current'],
    queryFn: () =>
      api.get<ShiftResponse[]>('/shifts', { location_id: params.locationId, week: params.week }),
    enabled: params.enabled ?? true,
    // Polling, per the project blueprint's real-time-ish update strategy
    // (Section 5) — assignment actions already invalidate this query for
    // the actor themselves; polling covers changes made by other people.
    refetchInterval: 30_000,
  });
}

export function useRoster(locationId: string | undefined, week: string) {
  return useQuery({
    queryKey: ['roster', locationId, week],
    queryFn: () => api.get<ShiftResponse[]>('/roster', { location_id: locationId, week }),
    enabled: Boolean(locationId),
  });
}

export function useCandidates(shiftId: string | null) {
  return useQuery({
    queryKey: ['shift-candidates', shiftId],
    queryFn: () => api.get<CandidateResponse[]>(`/shifts/${shiftId}/candidates`),
    enabled: Boolean(shiftId),
  });
}

export function useCreateShift() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ShiftCreatePayload) => api.post<ShiftResponse>('/shifts', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
      queryClient.invalidateQueries({ queryKey: ['roster'] });
    },
  });
}
