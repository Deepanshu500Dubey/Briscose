import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/apiClient';
import type { UserCreate, UserResponse } from '@/types/api';

/** Manager/Admin only — used to populate the employee picker on the team
 * timesheets screen and the assign-drawer's manual override list. */
export function useUsers(locationId: string | undefined) {
  return useQuery({
    queryKey: ['users', locationId],
    queryFn: () => api.get<UserResponse[]>('/users', { location_id: locationId }),
    enabled: Boolean(locationId),
  });
}

/** Admin only — GET /users with no location_id returns everyone; a Manager
 * calling this would get every user tied to any location they manage,
 * which isn't useful for the Admin-only "all users" list this backs. */
export function useAllUsers(enabled: boolean) {
  return useQuery({
    queryKey: ['users', 'all'],
    queryFn: () => api.get<UserResponse[]>('/users'),
    enabled,
  });
}

export function useProvisionUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UserCreate) => api.post<UserResponse>('/users', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}
