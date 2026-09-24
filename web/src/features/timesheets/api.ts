import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/apiClient';
import type { TimesheetResponse } from '@/types/api';

export function useTimesheet(params: { employeeId?: string; week?: string }) {
  return useQuery({
    queryKey: ['timesheets', params.employeeId ?? 'self', params.week ?? 'current'],
    queryFn: () =>
      api.get<TimesheetResponse>('/timesheets', {
        employee_id: params.employeeId,
        week: params.week,
      }),
  });
}
