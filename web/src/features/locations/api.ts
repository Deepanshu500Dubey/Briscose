import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/apiClient';
import type { LocationCreate, LocationResponse } from '@/types/api';

export function useLocations() {
  return useQuery({
    queryKey: ['locations'],
    queryFn: () => api.get<LocationResponse[]>('/locations'),
    staleTime: 60_000,
  });
}

export function useCreateLocation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LocationCreate) => api.post<LocationResponse>('/locations', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['locations'] }),
  });
}
