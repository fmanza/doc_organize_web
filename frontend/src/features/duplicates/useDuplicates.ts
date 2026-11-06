import { keepPreviousData, useQuery } from '@tanstack/react-query';

import type { ListParams, SortOf } from '../../api/listing';
import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type DuplicateGroup = components['schemas']['DuplicateGroupOut'];
export type DuplicateMember = components['schemas']['DuplicateMemberOut'];
export type DuplicateReason = DuplicateGroup['reason'];
export type DedupChoice = components['schemas']['DedupChoice'];
export type DedupMode = components['schemas']['DedupApplyParams']['mode'];

export const GROUPS_PAGE_SIZE = 10;
/** Página para reunir todos los grupos al aplicar (máximo de la API). */
const ALL_PAGE_SIZE = 200;
/** Grupos que admite una aplicación (`DedupApplyParams.groups`). */
export const MAX_APPLY_GROUPS = 10_000;

/** Qué documento se conserva por defecto en cada grupo. */
export type KeepPolicy = 'oldest' | 'newest' | 'shortest';

/** Decisión del usuario sobre un grupo (lo que haya tocado; lo demás lo decide la política). */
export interface GroupOverride {
  include?: boolean;
  keep?: string;
}

/** Los exactos y los conflictos de versión se aplican por defecto; los parecidos solo si se marcan. */
export function includedByDefault(group: Pick<DuplicateGroup, 'reason'>): boolean {
  return group.reason !== 'fuzzy_name_match';
}

/** Miembro que conserva la política (empates: el que doc_organize marca como canónico). */
export function keepByPolicy(group: Pick<DuplicateGroup, 'members'>, policy: KeepPolicy): string {
  const members = [...group.members];
  const time = (m: DuplicateMember) => new Date(m.modified_at).getTime();
  const sorters: Record<KeepPolicy, (a: DuplicateMember, b: DuplicateMember) => number> = {
    oldest: (a, b) => time(a) - time(b),
    newest: (a, b) => time(b) - time(a),
    shortest: (a, b) => a.key.length - b.key.length,
  };
  members.sort((a, b) => sorters[policy](a, b) || Number(b.canonical) - Number(a.canonical));
  return members[0]?.key ?? '';
}

/** Decisión efectiva de un grupo: la del usuario o, si no hay, la de la política. */
export function decision(
  group: DuplicateGroup,
  policy: KeepPolicy,
  overrides: Record<string, GroupOverride>,
): { include: boolean; keep: string } {
  const override = overrides[group.group_id] ?? {};
  return {
    include: override.include ?? includedByDefault(group),
    keep: override.keep ?? keepByPolicy(group, policy),
  };
}

/** Grupos que se aplican, con el documento que se conserva. */
export function choices(
  groups: DuplicateGroup[],
  policy: KeepPolicy,
  overrides: Record<string, GroupOverride>,
): DedupChoice[] {
  return groups.flatMap((group) => {
    const { include, keep } = decision(group, policy, overrides);
    return include ? [{ group_id: group.group_id, keep }] : [];
  });
}

export function useLastDuplicates(projectId: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'duplicates', 'last'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/duplicates/last', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

export type GroupSort = SortOf<'/api/v1/runs/{run_id}/duplicate-groups'>;

export function useDuplicateGroups(
  runId: string | null,
  reason: DuplicateReason | null,
  list: ListParams<GroupSort>,
) {
  return useQuery({
    queryKey: ['duplicate-groups', runId, reason, list],
    enabled: runId !== null,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/runs/{run_id}/duplicate-groups', {
          params: { path: { run_id: runId ?? '' }, query: { reason, ...list } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/**
 * Todos los grupos de una vista previa (para aplicar también los que no se han visto, con la política elegida) y el
 * total. Si hay más de `MAX_APPLY_GROUPS`, no se descargan: quien llama avisa en lugar de aplicar solo una parte.
 */
export async function fetchAllGroups(runId: string): Promise<{ groups: DuplicateGroup[]; total: number }> {
  const groups: DuplicateGroup[] = [];
  for (let offset = 0; ; offset += ALL_PAGE_SIZE) {
    const page = unwrap(
      await api.GET('/api/v1/runs/{run_id}/duplicate-groups', {
        params: { path: { run_id: runId }, query: { limit: ALL_PAGE_SIZE, offset } },
      }),
    );
    if (page.total > MAX_APPLY_GROUPS) return { groups: [], total: page.total };
    groups.push(...page.items);
    if (groups.length >= page.total || page.items.length === 0) return { groups, total: page.total };
  }
}

/** Decisiones guardadas por búsqueda en la pestaña: sobreviven a ir al visor y volver. */
export function storedReview(runId: string | null): {
  policy: KeepPolicy;
  overrides: Record<string, GroupOverride>;
} {
  const empty = { policy: 'oldest' as KeepPolicy, overrides: {} };
  if (!runId) return empty;
  try {
    const raw = sessionStorage.getItem(`dow:duplicates:${runId}`);
    return raw ? { ...empty, ...(JSON.parse(raw) as typeof empty) } : empty;
  } catch {
    return empty;
  }
}

export function storeReview(
  runId: string,
  review: { policy: KeepPolicy; overrides: Record<string, GroupOverride> },
): void {
  try {
    sessionStorage.setItem(`dow:duplicates:${runId}`, JSON.stringify(review));
  } catch {
    // Sin almacenamiento (modo privado lleno…): las decisiones solo duran mientras no se salga de la página.
  }
}
