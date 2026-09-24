import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/apiClient';
import type { AssignmentResponse } from '@/types/api';

function invalidateShiftQueries(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['shifts'] });
  queryClient.invalidateQueries({ queryKey: ['roster'] });
  queryClient.invalidateQueries({ queryKey: ['shift-candidates'] });
  queryClient.invalidateQueries({ queryKey: ['notifications'] });
}

export function useOfferAssignment(shiftId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (employeeId: string) =>
      api.post<AssignmentResponse>(`/shifts/${shiftId}/assignments`, { employee_id: employeeId }),
    onSuccess: () => invalidateShiftQueries(queryClient),
  });
}

export function useAcceptAssignment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) =>
      api.post<AssignmentResponse>(`/assignments/${assignmentId}/accept`),
    onSuccess: () => invalidateShiftQueries(queryClient),
  });
}

export function useRejectAssignment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) =>
      api.post<AssignmentResponse>(`/assignments/${assignmentId}/reject`),
    onSuccess: () => invalidateShiftQueries(queryClient),
  });
}

export function useWithdrawAssignment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ assignmentId, confirm }: { assignmentId: string; confirm?: boolean }) =>
      api.delete<AssignmentResponse>(`/assignments/${assignmentId}`, { confirm: confirm ?? false }),
    onSuccess: () => invalidateShiftQueries(queryClient),
  });
}
