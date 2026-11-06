import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import type { ListParams, SortOf } from '../../api/listing';

import { api, ensureOk, isApiError, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { useEnqueueRun } from '../projects/useProjects';
import { useRun } from '../runs/useRuns';

export type ContextDocumentSort = SortOf<'/api/v1/projects/{project_id}/context/documents'>;

export type ContextOut = components['schemas']['ContextOut'];
export type ContextDocument = components['schemas']['ContextDocumentOut'];
export type ContextBuildParams = components['schemas']['ContextBuildParams'];
export type Catalog = ContextBuildParams['catalog'];
export type TaxonomyTemplate = components['schemas']['TaxonomyTemplateOut'];
export type TaxonomyTemplateDetail = components['schemas']['TaxonomyTemplateDetail'];
export type DocumentFilter = 'failed' | 'collision';

/** Tamaño máximo de una plantilla o manifiesto (`MAX_TEMPLATE_BYTES` de la API). */
export const MAX_TEMPLATE_BYTES = 256 * 1024;
/** Nombre de una plantilla personalizada: minúsculas, dígitos y guiones. */
export const TEMPLATE_NAME = /^[a-z0-9][a-z0-9-]{0,63}$/;

/** Parámetros completos de `context_build` (el cliente generado exige los campos con valor por defecto). */
export function buildParams(change: Partial<ContextBuildParams>): ContextBuildParams {
  return {
    operation: 'context_build',
    catalog: 'discover',
    domains: [],
    template_name: null,
    output_folder_name: null,
    threshold: 0.5,
    build_site: true,
    ai_classification: false,
    template_markdown: null,
    ...change,
  };
}

/** Familia de IA que usa `catalog`: con plantilla o manifiesto clasifica en dos ejes (taxonomía). */
export function aiFamily(catalog: Catalog): 'litellm_classification' | 'litellm_taxonomy_classification' {
  return catalog === 'template' || catalog === 'manifest'
    ? 'litellm_taxonomy_classification'
    : 'litellm_classification';
}

/** Resultado del run `taxonomy_draft` (lo que devuelve el job). */
export interface TaxonomyDraftResult {
  manifest_markdown: string;
  reasoning: string | null;
  sample_documents: number;
  total_documents: number;
}

function isDraftResult(value: unknown): value is TaxonomyDraftResult {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as { manifest_markdown?: unknown }).manifest_markdown === 'string'
  );
}

/**
 * Lanza `taxonomy_draft` y sigue el run (cada 2 s) hasta que termina. Al acabar bien entrega el Markdown a `onDraft`
 * una sola vez; si falla, `failure` lleva el mensaje del run.
 */
export function useTaxonomyDraft(projectId: number, onDraft: (markdown: string) => void) {
  const enqueue = useEnqueueRun(projectId);
  const [runId, setRunId] = useState<string | null>(null);
  const run = useRun(runId, 2_000);
  const delivered = useRef<string | null>(null);
  const status = run.data?.status;
  const result: unknown = run.data?.result;
  const loaded = status === 'succeeded' && isDraftResult(result) ? result : null;

  useEffect(() => {
    if (loaded && runId && delivered.current !== runId) {
      delivered.current = runId;
      onDraft(loaded.manifest_markdown);
    }
  }, [loaded, runId, onDraft]);

  return {
    runId,
    running: enqueue.isPending || status === 'queued' || status === 'running',
    error: enqueue.error ?? run.error,
    failure: status === 'failed' || status === 'cancelled' ? (run.data?.error_message ?? status) : null,
    loaded,
    start: (sampleSize: number) =>
      enqueue.mutate(
        { operation: 'taxonomy_draft', sample_size: sampleSize },
        { onSuccess: (created) => setRunId(created.id) },
      ),
  };
}

/** Contexto del proyecto, o `null` si todavía no se ha construido (404 `context_not_found`). */
export function useProjectContext(projectId: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'context'],
    queryFn: async (): Promise<ContextOut | null> => {
      try {
        return unwrap(
          await api.GET('/api/v1/projects/{project_id}/context', {
            params: { path: { project_id: projectId } },
          }),
        );
      } catch (error) {
        if (isApiError(error, 404) && error.problem.code === 'context_not_found') {
          return null;
        }
        throw error;
      }
    },
  });
}

/** Documentos de un dominio (`domain`) o sin clasificar (`null`), paginados en el servidor. */
export function useContextDocuments(
  projectId: number,
  domain: string | null,
  only: DocumentFilter | null,
  list: ListParams<ContextDocumentSort>,
  enabled = true,
) {
  return useQuery({
    queryKey: ['projects', projectId, 'context', 'documents', { domain, only, ...list }],
    enabled,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/documents', {
          params: {
            path: { project_id: projectId },
            query: { domain, only, ...list },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useManifest(projectId: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'context', 'manifest'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/taxonomy-manifest', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

export function useSaveManifest(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (markdown: string) =>
      unwrap(
        await api.PUT('/api/v1/projects/{project_id}/context/taxonomy-manifest', {
          params: { path: { project_id: projectId } },
          body: { markdown },
        }),
      ),
    onSuccess: (manifest) =>
      queryClient.setQueryData(['projects', projectId, 'context', 'manifest'], manifest),
  });
}

/** Abre una sesión del sitio aislado: URL con su token (caduca en una hora). */
export function useOpenSite(projectId: number) {
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/context/site-session', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

// --- plantillas de taxonomía ---------------------------------------------------------------------------------------

export function useTemplates() {
  return useQuery({
    queryKey: ['taxonomy-templates'],
    queryFn: async () => unwrap(await api.GET('/api/v1/taxonomy-templates')).items,
  });
}

export function useTemplate(name: string | null) {
  return useQuery({
    queryKey: ['taxonomy-templates', name],
    enabled: name !== null,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/taxonomy-templates/{name}', { params: { path: { name: name ?? '' } } })),
  });
}

export function useSaveTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ name, markdown }: { name: string; markdown: string }) =>
      unwrap(
        await api.PUT('/api/v1/taxonomy-templates/{name}', {
          params: { path: { name } },
          body: { markdown },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['taxonomy-templates'] }),
  });
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) =>
      ensureOk(await api.DELETE('/api/v1/taxonomy-templates/{name}', { params: { path: { name } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['taxonomy-templates'] }),
  });
}

/** Descarga de la plantilla como `.md` (mismo origen: la cookie de sesión viaja sola). */
export function templateDownloadUrl(name: string): string {
  return `/api/v1/taxonomy-templates/${encodeURIComponent(name)}/download`;
}

/** Nombre sugerido para importar un `.md`: el del fichero en minúsculas, solo con letras, dígitos y guiones. */
export function nameFromFile(fileName: string): string {
  return fileName
    .replace(/\.md$/i, '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64);
}
