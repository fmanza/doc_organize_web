import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ListParams, SortOf } from '../../api/listing';
import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { meQueryKey } from '../auth/useAuth';

export type User = components['schemas']['UserOut'];
export type UserCreate = components['schemas']['UserCreate'];
export type UserUpdate = components['schemas']['UserUpdate'];
export type SessionInfo = components['schemas']['SessionOut'];
export type AuditEntry = components['schemas']['AuditEntryOut'];
export type UserRole = User['role'];

export type UserSort = SortOf<'/api/v1/users'>;
export type SessionSort = SortOf<'/api/v1/sessions'>;
export type AuditSort = SortOf<'/api/v1/audit'>;

export function useUsers(query: ListParams<UserSort>) {
  return useQuery({
    queryKey: ['users', query],
    queryFn: async () => unwrap(await api.GET('/api/v1/users', { params: { query } })),
    placeholderData: keepPreviousData,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: UserCreate) => unwrap(await api.POST('/api/v1/users', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: UserUpdate }) =>
      unwrap(await api.PATCH('/api/v1/users/{user_id}', { params: { path: { user_id: id } }, body })),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['users'] }),
        queryClient.invalidateQueries({ queryKey: ['sessions'] }),
      ]),
  });
}

export function useSessions(query: ListParams<SessionSort>) {
  return useQuery({
    queryKey: ['sessions', query],
    queryFn: async () => unwrap(await api.GET('/api/v1/sessions', { params: { query } })),
    placeholderData: keepPreviousData,
  });
}

export function useRevokeSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (session: SessionInfo) =>
      ensureOk(
        await api.DELETE('/api/v1/sessions/{session_id}', { params: { path: { session_id: session.id } } }),
      ),
    onSuccess: (_data, session) =>
      session.current
        ? queryClient.invalidateQueries({ queryKey: meQueryKey })
        : queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  });
}

export function useAudit(action: string, actor: string, list: ListParams<AuditSort>) {
  return useQuery({
    queryKey: ['audit', { action, actor, ...list }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/audit', {
          params: { query: { action: action || null, actor: actor || null, ...list } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export type AuditPurge = components['schemas']['AuditPurgeIn'];

/** Cuenta (`dry_run`) o borra la auditoría del tenant activo en un rango de fechas (web 1.2.0, admin de instancia). */
export function useAuditPurge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: AuditPurge) => unwrap(await api.POST('/api/v1/audit/purge', { body })),
    onSuccess: (_data, body) =>
      body.dry_run ? undefined : queryClient.invalidateQueries({ queryKey: ['audit'] }),
  });
}
