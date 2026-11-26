import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { api, octetStreamBody, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { type RunRequest, useEnqueueRun } from '../projects/useProjects';
import { useRun } from '../runs/useRuns';

export type Quality = components['schemas']['QualityOut'];

/**
 * Valores iniciales del formulario de la referencia. Son nombres de la hoja y de las columnas del Excel del usuario,
 * no texto de la interfaz: coinciden con los valores por omisión de `PUT .../context/quality/gold` en el backend y no
 * se traducen con el idioma.
 */
export const GOLD_DEFAULTS = {
  sheet: 'Referencia',
  documentColumn: 'documento',
  columns: 'domains:dominio_ok, material_types:tipo_ok',
} as const;

const qualityKey = (projectId: number) => ['projects', projectId, 'context', 'quality'] as const;

export function useQuality(projectId: number) {
  return useQuery({
    queryKey: qualityKey(projectId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/quality', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

/** Lanza un run de calidad y lo sigue; al terminar bien, recarga la página de calidad. */
export function useQualityRun(projectId: number) {
  const queryClient = useQueryClient();
  const enqueue = useEnqueueRun(projectId);
  const [runId, setRunId] = useState<string | null>(null);
  const run = useRun(runId, 2_000);
  const status = run.data?.status;
  useEffect(() => {
    if (status === 'succeeded') {
      void queryClient.invalidateQueries({ queryKey: qualityKey(projectId) });
    }
  }, [status, projectId, queryClient]);
  return {
    running: enqueue.isPending || status === 'queued' || status === 'running',
    error: enqueue.error ?? run.error,
    failure: status === 'failed' || status === 'cancelled' ? (run.data?.error_message ?? status) : null,
    start: (body: RunRequest) => enqueue.mutate(body, { onSuccess: (created) => setRunId(created.id) }),
  };
}

/** Referencia de calidad: un Excel con la hoja, la columna del documento y las columnas `eje:columna`. */
export interface GoldUpload {
  file: File;
  sheet: string;
  documentColumn: string;
  columns: string[];
}

/** Sube (o sustituye) la referencia de calidad del proyecto como bytes sin transformar. */
export function useUploadGold(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, sheet, documentColumn, columns }: GoldUpload) =>
      unwrap(
        await api.PUT('/api/v1/projects/{project_id}/context/quality/gold', {
          params: {
            path: { project_id: projectId },
            query: { filename: file.name, sheet, document_column: documentColumn, columns },
          },
          ...octetStreamBody(await file.arrayBuffer()),
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qualityKey(projectId) }),
  });
}
