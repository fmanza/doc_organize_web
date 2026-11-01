import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import { api, unwrap } from '../../api/client';
import type { components, operations } from '../../api/schema';

export type RunOut = components['schemas']['RunOut'];
export type RunStatus = RunOut['status'];
export type Operation = RunOut['operation'];
export type RunProgress = components['schemas']['RunProgress'];
export type RunFilters = NonNullable<operations['list_runs_api_v1_runs_get']['parameters']['query']>;

export const RUNS_PAGE_SIZE = 25;
export const ACTIVE_STATUSES: readonly RunStatus[] = ['queued', 'running'];

export function isActive(run: Pick<RunOut, 'status'>): boolean {
  return ACTIVE_STATUSES.includes(run.status);
}

/** Historial paginado; se refresca cada 5 s mientras alguna ejecución de la página siga activa. */
export function useRuns(
  filters: Omit<RunFilters, 'limit' | 'offset'>,
  page: number,
  pageSize = RUNS_PAGE_SIZE,
) {
  return useQuery({
    queryKey: ['runs', 'list', filters, page, pageSize],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/runs', {
          params: { query: { ...filters, limit: pageSize, offset: (page - 1) * pageSize } },
        }),
      ),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => (query.state.data?.items.some(isActive) ? 5_000 : false),
  });
}

/** Un run; mientras está activo se vuelve a pedir (respaldo del SSE, que actualiza la caché al instante). */
export function useRun(runId: string | null, pollMs = 5_000) {
  return useQuery({
    queryKey: ['runs', runId],
    enabled: runId !== null,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/runs/{run_id}', { params: { path: { run_id: runId ?? '' } } })),
    refetchInterval: (query) => (query.state.data && isActive(query.state.data) ? pollMs : false),
  });
}

export function useCancelRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (runId: string) =>
      unwrap(await api.POST('/api/v1/runs/{run_id}/cancel', { params: { path: { run_id: runId } } })),
    onSuccess: (run) => {
      queryClient.setQueryData(['runs', run.id], run);
      return queryClient.invalidateQueries({ queryKey: ['runs', 'list'] });
    },
  });
}

export interface RunLogEntry {
  id: string;
  level: string;
  message: string;
  ts: string;
}

/**
 * Progreso en vivo por SSE (ADR-008). `EventSource` envía la cookie de sesión (mismo origen) y, si la conexión se
 * corta, reconecta solo con `Last-Event-ID`. Cada `status`/`artifact` refresca el run; `end` cierra la conexión.
 *
 * También se abre para runs terminados: el servidor reenvía los avisos (`log`) y `end`, y se cierra. Con `active`
 * falso, un error de conexión cierra en lugar de reintentar.
 */
export function useRunEvents(runId: string, enabled: boolean, active: boolean) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<{
    runId: string;
    progress: RunProgress | null;
    log: RunLogEntry[];
  }>({ runId, progress: null, log: [] });
  const activeRef = useRef(active);
  useEffect(() => {
    activeRef.current = active;
  }, [active]);
  // Al pasar a otro run (misma página, otra ruta) se descarta lo recibido del anterior.
  const current = state.runId === runId ? state : { runId, progress: null, log: [] };

  useEffect(() => {
    if (!enabled || typeof EventSource === 'undefined') {
      return undefined;
    }
    const source = new EventSource(`/api/v1/runs/${encodeURIComponent(runId)}/events`);
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: ['runs', runId] });
    };
    source.addEventListener('progress', (event) => {
      const progress = JSON.parse((event as MessageEvent<string>).data) as RunProgress;
      setState((previous) => ({ ...previous, runId, progress }));
    });
    source.addEventListener('log', (event) => {
      const message = event as MessageEvent<string>;
      const data = JSON.parse(message.data) as { level: string; message: string; ts: string };
      setState((previous) =>
        previous.log.some((entry) => entry.id === message.lastEventId)
          ? previous
          : { ...previous, runId, log: [...previous.log, { id: message.lastEventId, ...data }] },
      );
    });
    source.addEventListener('error', () => {
      if (!activeRef.current) {
        source.close();
      }
    });
    source.addEventListener('status', refresh);
    source.addEventListener('artifact', refresh);
    source.addEventListener('end', () => {
      refresh();
      // Al terminar cambian el proyecto (`active_run`), sus carpetas escaneadas y los errores de escaneo.
      void queryClient.invalidateQueries({ queryKey: ['runs', 'list'] });
      void queryClient.invalidateQueries({ queryKey: ['projects'] });
      void queryClient.invalidateQueries({ queryKey: ['scan-errors'] });
      source.close();
    });
    return () => source.close();
  }, [runId, enabled, queryClient]);

  return { progress: current.progress, log: current.log };
}

export function artifactUrl(runId: string, artifactId: number): string {
  return `/api/v1/runs/${encodeURIComponent(runId)}/artifacts/${artifactId}`;
}
