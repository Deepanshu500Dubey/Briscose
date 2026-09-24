import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/apiClient';
import type { AvailabilityDayInput, AvailabilityResponse } from '@/types/api';

export function useAvailability(employeeId?: string) {
  return useQuery({
    queryKey: ['availability', employeeId ?? 'self'],
    queryFn: () =>
      api.get<AvailabilityResponse[]>('/availability', employeeId ? { employee_id: employeeId } : undefined),
  });
}

/** One GET /availability per employee, run concurrently — used by the
 * Team & Availability screen (MGR-06). There's no bulk
 * "availability for every employee at a location" endpoint, so this is
 * N requests rather than one; acceptable for a store-sized team, and each
 * request is still scoped/authorized exactly as a single-employee lookup
 * would be. */
export function useTeamAvailability(employeeIds: string[]) {
  return useQueries({
    queries: employeeIds.map((employeeId) => ({
      queryKey: ['availability', employeeId],
      queryFn: () => api.get<AvailabilityResponse[]>('/availability', { employee_id: employeeId }),
    })),
  });
}

export function useSaveAvailability() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (days: AvailabilityDayInput[]) =>
      api.patch<AvailabilityResponse[]>('/availability', { days }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['availability'] });
    },
  });
}
