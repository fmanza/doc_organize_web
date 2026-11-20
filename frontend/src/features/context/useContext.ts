import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import type { ListParams, SortOf } from '../../api/listing';

import { api, ensureOk, isApiError, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { type RunRequest, useEnqueueRun } from '../projects/useProjects';
import { useRun } from '../runs/useRuns';

export type ContextDocumentSort = SortOf<'/api/v1/projects/{project_id}/context/documents'>;

export type ContextOut = components['schemas']['ContextOut'];
export type ContextDocument = components['schemas']['ContextDocumentOut'];
export type ContextBuildParams = components['schemas']['ContextBuildParams'];
export type Catalog = ContextBuildParams['catalog'];
export type TaxonomyTemplate = components['schemas']['TaxonomyTemplateOut'];
export type TaxonomyTemplateDetail = components['schemas']['TaxonomyTemplateDetail'];
export type DocumentFilter = 'failed' | 'collision' | 'ai_disagrees';

/** Filtros de los documentos del contexto (idioma y palabra clave desde la 1.5.0). */
export interface ContextDocumentFilters {
  only: DocumentFilter | null;
  language: string | null;
  keyword: string;
  /** Filtros por eje `clave:slug` (W3): O dentro del eje, Y entre ejes. */
  axis?: string[];
  /** Solo las versiones vigentes (W6). */
  current?: boolean;
}

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
    ai_enrichment: false,
    template_markdown: null,
    ...change,
  };
}

/** Tarea de IA que clasifica (doc_organize 2.0): la misma con cualquier catálogo (`litellm`, modelo por tarea). */
export function aiTask(catalog: Catalog): 'classify' {
  void catalog;
  return 'classify';
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
  filters: ContextDocumentFilters,
  list: ListParams<ContextDocumentSort>,
  enabled = true,
) {
  const { only, language } = filters;
  const keyword = filters.keyword.trim() || null;
  const axis = filters.axis?.length ? filters.axis : null;
  const current = filters.current ?? false;
  return useQuery({
    queryKey: [
      'projects',
      projectId,
      'context',
      'documents',
      { domain, only, language, keyword, axis, current, ...list },
    ],
    enabled,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/documents', {
          params: {
            path: { project_id: projectId },
            query: { domain, only, language, keyword, axis, current, ...list },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export type Manifest = components['schemas']['TaxonomyManifestOut'];
export type ManifestVersion = components['schemas']['ManifestVersionOut'];
export type ManifestVersionDetail = components['schemas']['ManifestVersionDetail'];

export const manifestKey = (projectId: number) => ['projects', projectId, 'context', 'manifest'] as const;
const versionsKey = (projectId: number) =>
  ['projects', projectId, 'context', 'manifest', 'versions'] as const;

export function manifestQuery(projectId: number) {
  return {
    queryKey: manifestKey(projectId),
    queryFn: async (): Promise<Manifest> =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/taxonomy-manifest', {
          params: { path: { project_id: projectId } },
        }),
      ),
  };
}

export function useManifest(projectId: number) {
  return useQuery(manifestQuery(projectId));
}

/**
 * Tras guardar, borrar o restaurar: el manifiesto nuevo (con su `etag`) y la lista de versiones al día. Ante 409
 * `manifest_changed` (otro usuario lo cambió) se vuelve a leer el manifiesto; el borrador vive en la página y no se
 * pierde.
 */
function useManifestChange<V>(projectId: number, request: (vars: V) => Promise<Manifest>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: (manifest) => {
      queryClient.setQueryData(manifestKey(projectId), manifest);
      void queryClient.invalidateQueries({ queryKey: versionsKey(projectId) });
    },
    onError: (error) => {
      if (isApiError(error, 409) && error.problem.code === 'manifest_changed') {
        void queryClient.invalidateQueries({ queryKey: manifestKey(projectId), exact: true });
      }
    },
  });
}

export function useSaveManifest(projectId: number) {
  return useManifestChange(projectId, async ({ markdown, etag }: { markdown: string; etag: string }) =>
    unwrap(
      await api.PUT('/api/v1/projects/{project_id}/context/taxonomy-manifest', {
        params: { path: { project_id: projectId }, header: { 'if-match': etag } },
        body: { markdown },
      }),
    ),
  );
}

export function useDeleteManifest(projectId: number) {
  return useManifestChange(projectId, async ({ etag }: { etag: string }) =>
    unwrap(
      await api.DELETE('/api/v1/projects/{project_id}/context/taxonomy-manifest', {
        params: { path: { project_id: projectId }, header: { 'if-match': etag } },
      }),
    ),
  );
}

export function useRestoreManifest(projectId: number) {
  return useManifestChange(projectId, async ({ versionId, etag }: { versionId: number; etag: string }) =>
    unwrap(
      await api.POST(
        '/api/v1/projects/{project_id}/context/taxonomy-manifest/versions/{version_id}/restore',
        {
          params: { path: { project_id: projectId, version_id: versionId }, header: { 'if-match': etag } },
        },
      ),
    ),
  );
}

/** Versiones anteriores del manifiesto (las últimas `limit`), de la más reciente a la más antigua, sin el texto. */
export function useManifestVersions(projectId: number) {
  return useQuery({
    queryKey: versionsKey(projectId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/taxonomy-manifest/versions', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

/** Texto de una versión (se pide al pulsar «Ver» o «Cargar en el editor», no al pintar la lista). */
export function manifestVersionQuery(projectId: number, versionId: number) {
  return {
    queryKey: [...versionsKey(projectId), versionId] as const,
    queryFn: async (): Promise<ManifestVersionDetail> =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/taxonomy-manifest/versions/{version_id}', {
          params: { path: { project_id: projectId, version_id: versionId } },
        }),
      ),
  };
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

export function templateQuery(name: string) {
  return {
    queryKey: ['taxonomy-templates', name] as const,
    queryFn: async (): Promise<TaxonomyTemplateDetail> =>
      unwrap(await api.GET('/api/v1/taxonomy-templates/{name}', { params: { path: { name } } })),
  };
}

export function useTemplate(name: string | null) {
  return useQuery({ ...templateQuery(name ?? ''), enabled: name !== null });
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

export type ContextHistory = components['schemas']['ContextHistoryOut'];
export type ContextBuild = components['schemas']['ContextBuildOut'];

/** Construcciones más recientes del contexto con sus cambios (1.5.0). Se conserva al borrar el contexto. */
export function useContextHistory(projectId: number, limit = 10) {
  return useQuery({
    queryKey: ['projects', projectId, 'context', 'history', limit],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/history', {
          params: { path: { project_id: projectId }, query: { limit } },
        }),
      ),
  });
}

/** Construcciones y cambios del contexto (1.5.0) en Excel; el historial se conserva al borrar el contexto. */
export const CONTEXT_HISTORY_XLSX: RunRequest = { operation: 'export_xlsx', kind: 'context_history' };
/** Excel del contexto (2.0): documentos con sus ejes y, en otra hoja, cuántos hay de cada valor. */
export const CONTEXT_XLSX: RunRequest = { operation: 'export_xlsx', kind: 'context_documents' };

// --- manifiesto en la página del contexto (1.8.0) ---------------------------------------------------------------

/** Mismo texto salvo los saltos de línea (el navegador envía `\n`; el disco puede tener `\r\n`). */
export function sameText(a: string | null | undefined, b: string | null | undefined): boolean {
  return (a ?? '').replace(/\r\n/g, '\n') === (b ?? '').replace(/\r\n/g, '\n');
}

/** El contexto se construyó con el manifiesto antes del último cambio (B5): hay que reconstruir para aplicarlo. */
export function contextIsStale(context: ContextOut | null, manifest: Manifest): boolean {
  return (
    context?.catalog_kind === 'manifest' &&
    manifest.last_changed_at != null &&
    new Date(context.built_at) < new Date(manifest.last_changed_at)
  );
}

/** Catálogo y plantilla elegidos para construir (los comparten la tarjeta de construcción y el manifiesto). */
export interface Selection {
  catalog: Catalog;
  template: string | null;
}

/** Selección inicial: la del contexto construido, o «Descubrir dominios». */
export function initialSelection(context: ContextOut | null): Selection {
  return {
    catalog: (context?.catalog_kind as Catalog | undefined) ?? 'discover',
    template: context?.taxonomy_template_name ?? null,
  };
}
