import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import type { PageState } from '../../components/usePageState';

export type ReviewItem = components['schemas']['ReviewItemOut'];
export type ReviewReason = components['schemas']['ReviewItemOut']['reason'];
export type Decision = components['schemas']['DecisionOut'];
export type DecisionIn = components['schemas']['DecisionIn'];
export type Proposal = components['schemas']['ProposalOut'];

export const reviewKey = (projectId: number) => ['projects', projectId, 'context', 'review'] as const;

export function useReview(projectId: number, reason: ReviewReason | null, q: string, paging: PageState) {
  const { pageSize, offset } = paging;
  return useQuery({
    queryKey: [...reviewKey(projectId), { reason, q, pageSize, offset }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/review', {
          params: {
            path: { project_id: projectId },
            query: { reason, ...(q ? { q } : {}), limit: pageSize, offset },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useDecisions(projectId: number) {
  return useQuery({
    queryKey: [...reviewKey(projectId), 'decisions'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/decisions', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

export function useDecide(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: DecisionIn) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/context/decisions', {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reviewKey(projectId) }),
  });
}

export function useRevoke(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string | null }) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/context/decisions/{decision_id}/revoke', {
          params: { path: { project_id: projectId, decision_id: id } },
          body: { reason },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reviewKey(projectId) }),
  });
}

export function useProposals(projectId: number) {
  return useQuery({
    queryKey: [...reviewKey(projectId), 'proposals'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/review/proposals', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

export function useProposalAction(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, accept }: { id: number; accept: boolean }) => {
      const params = { params: { path: { project_id: projectId, proposal_id: id } } };
      if (accept) {
        unwrap(
          await api.POST(
            '/api/v1/projects/{project_id}/context/review/proposals/{proposal_id}/accept',
            params,
          ),
        );
      } else {
        unwrap(
          await api.POST(
            '/api/v1/projects/{project_id}/context/review/proposals/{proposal_id}/discard',
            params,
          ),
        );
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reviewKey(projectId) }),
  });
}
