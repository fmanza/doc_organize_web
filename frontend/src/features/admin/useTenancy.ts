import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type Tenant = components['schemas']['TenantOut'];
export type TenantRole = components['schemas']['RoleOut'];
export type Permission = components['schemas']['RoleOut']['permissions'][number];

/** Catálogo de permisos en el orden de la API (`GET /permissions` exige `roles.manage`; es fijo). */
export const PERMISSIONS: readonly Permission[] = [
  'users.manage',
  'roles.manage',
  'audit.read',
  'templates.manage',
  'projects.create',
  'projects.all',
];

export function useTenants(enabled = true) {
  return useQuery({
    queryKey: ['tenants'],
    enabled,
    queryFn: async () => unwrap(await api.GET('/api/v1/tenants', { params: { query: { limit: 200 } } })),
  });
}

export function useCreateTenant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { slug: string; name: string }) =>
      unwrap(await api.POST('/api/v1/tenants', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tenants'] }),
  });
}

export function useRenameTenant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, name }: { id: number; name: string }) =>
      unwrap(
        await api.PATCH('/api/v1/tenants/{tenant_id}', {
          params: { path: { tenant_id: id } },
          body: { name },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tenants'] }),
  });
}

export function useDeleteTenant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      ensureOk(await api.DELETE('/api/v1/tenants/{tenant_id}', { params: { path: { tenant_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tenants'] }),
  });
}

/**
 * Cambia el tenant activo de la sesión (solo admin de instancia). Todo lo cargado era del tenant anterior: se borra
 * la caché y se vuelve a pedir.
 */
export function useSwitchTenant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (tenantId: number | null) =>
      unwrap(await api.PUT('/api/v1/auth/tenant', { body: { tenant_id: tenantId } })),
    onSuccess: async (me) => {
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== 'auth' });
      queryClient.setQueryData(['auth', 'me'], me);
      await queryClient.invalidateQueries();
    },
  });
}

export function useRoles(enabled = true) {
  return useQuery({
    queryKey: ['roles'],
    enabled,
    queryFn: async () => unwrap(await api.GET('/api/v1/roles')).items,
  });
}

export function useCreateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; permissions: Permission[] }) =>
      unwrap(await api.POST('/api/v1/roles', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['roles'] }),
  });
}

export function useUpdateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: number; name?: string; permissions?: Permission[] }) =>
      unwrap(await api.PATCH('/api/v1/roles/{role_id}', { params: { path: { role_id: id } }, body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['roles'] }),
  });
}

export function useDeleteRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      ensureOk(await api.DELETE('/api/v1/roles/{role_id}', { params: { path: { role_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['roles'] }),
  });
}
