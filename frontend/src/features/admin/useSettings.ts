import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type SettingOut = components['schemas']['SettingOut'];
export type InstanceCapabilities = components['schemas']['InstanceCapabilities'];

export function useAdminSettings() {
  return useQuery({
    queryKey: ['admin', 'settings'],
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/settings')),
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (values: Record<string, number | null>) =>
      unwrap(await api.PATCH('/api/v1/admin/settings', { body: { values } })),
    onSuccess: (data) => queryClient.setQueryData(['admin', 'settings'], data),
  });
}

/** Capacidades de la instancia; mientras están `pending`, se vuelven a pedir cada 5 s. */
export function useCapabilities() {
  return useQuery({
    queryKey: ['instance', 'capabilities'],
    queryFn: async () => unwrap(await api.GET('/api/v1/instance/capabilities')),
    refetchInterval: (query) => (query.state.data?.status === 'pending' ? 5_000 : false),
  });
}

export function useRefreshCapabilities() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => ensureOk(await api.POST('/api/v1/admin/capabilities/refresh')),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['instance', 'capabilities'] }),
  });
}
