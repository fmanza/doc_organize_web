import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type ProjectOut = components['schemas']['ProjectOut'];
export type ProjectCreate = components['schemas']['ProjectCreate'];
export type ProjectUpdate = components['schemas']['ProjectUpdate'];
export type MemberOut = components['schemas']['MemberOut'];
export type MemberRole = MemberOut['role'];
export type UserBrief = components['schemas']['UserBrief'];
export type RunRequest =
  | components['schemas']['NoopParams']
  | components['schemas']['HistoryClearParams']
  | components['schemas']['ProjectMoveParams']
  | components['schemas']['ProjectDeleteParams'];

/** Lanzar la prueba del motor con sus valores por defecto (el cliente generado exige todos los campos). */
export const NOOP_RUN: RunRequest = { operation: 'noop', steps: 5, step_seconds: 1, fail_at_step: null };

export const PROJECTS_PAGE_SIZE = 50;
export const ROLE_RANK: Record<MemberRole, number> = { viewer: 1, editor: 2, owner: 3 };

export function canDo(project: Pick<ProjectOut, 'role'>, minRole: MemberRole): boolean {
  return ROLE_RANK[project.role] >= ROLE_RANK[minRole];
}

export function useProjects(q: string, page: number) {
  return useQuery({
    queryKey: ['projects', 'list', q, page],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects', {
          params: {
            query: {
              ...(q ? { q } : {}),
              limit: PROJECTS_PAGE_SIZE,
              offset: (page - 1) * PROJECTS_PAGE_SIZE,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useProject(id: number) {
  return useQuery({
    queryKey: ['projects', id],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/projects/{project_id}', { params: { path: { project_id: id } } })),
    refetchInterval: (query) => (query.state.data?.active_run ? 5_000 : false),
  });
}

function useInvalidateProjects() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['projects'] }),
      queryClient.invalidateQueries({ queryKey: ['runs', 'list'] }),
    ]);
}

export function useCreateProject() {
  const invalidate = useInvalidateProjects();
  return useMutation({
    mutationFn: async (body: ProjectCreate) => unwrap(await api.POST('/api/v1/projects', { body })),
    onSuccess: invalidate,
  });
}

export function useUpdateProject(id: number) {
  const invalidate = useInvalidateProjects();
  return useMutation({
    mutationFn: async (body: ProjectUpdate) =>
      unwrap(
        await api.PATCH('/api/v1/projects/{project_id}', { params: { path: { project_id: id } }, body }),
      ),
    onSuccess: invalidate,
  });
}

export function useEnqueueRun(projectId: number) {
  const invalidate = useInvalidateProjects();
  return useMutation({
    mutationFn: async (body: RunRequest) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/runs', {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: invalidate,
  });
}

// --- miembros ------------------------------------------------------------------------------------------------------

export function useMembers(projectId: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'members'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/members', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

function useInvalidateMembers(projectId: number) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'members'] });
}

export function useAddMember(projectId: number) {
  const invalidate = useInvalidateMembers(projectId);
  return useMutation({
    mutationFn: async (body: { user_id: number; role: MemberRole }) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/members', {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useUpdateMember(projectId: number) {
  const invalidate = useInvalidateMembers(projectId);
  return useMutation({
    mutationFn: async ({ userId, role }: { userId: number; role: MemberRole }) =>
      unwrap(
        await api.PATCH('/api/v1/projects/{project_id}/members/{user_id}', {
          params: { path: { project_id: projectId, user_id: userId } },
          body: { role },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useRemoveMember(projectId: number) {
  const invalidate = useInvalidateMembers(projectId);
  return useMutation({
    mutationFn: async (userId: number) =>
      ensureOk(
        await api.DELETE('/api/v1/projects/{project_id}/members/{user_id}', {
          params: { path: { project_id: projectId, user_id: userId } },
        }),
      ),
    onSuccess: invalidate,
  });
}

/** Usuarios activos que empiezan por `q` (al menos 2 caracteres), para invitar. */
export function useUserLookup(q: string) {
  const term = q.trim();
  return useQuery({
    queryKey: ['users', 'lookup', term],
    enabled: term.length >= 2,
    queryFn: async () => unwrap(await api.GET('/api/v1/users/lookup', { params: { query: { q: term } } })),
    placeholderData: keepPreviousData,
  });
}
