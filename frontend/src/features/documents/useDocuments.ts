import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type DocumentOut = components['schemas']['DocumentOut'];
export type SearchPage = components['schemas']['SearchPage'];
export type SearchHit = components['schemas']['SearchHitOut'];

export const DOCUMENTS_PAGE_SIZE = 100;
/** Valor de los selectores de carpeta para la raíz de la ubicación (la API lo normaliza a «»). */
export const ROOT_FOLDER = '.';
export const SEARCH_PAGE_SIZE = 20;
/** Marcas de las coincidencias en los fragmentos de la búsqueda (U+0002 y U+0003). */
export const MARK_START = '\u0002';
export const MARK_END = '\u0003';

export interface DocumentFilters {
  search: string;
  folder: string | null;
}

/** Documentos de la caché paginados en servidor, página a página para la lista virtualizada. */
export function useDocuments(projectId: number, filters: DocumentFilters) {
  return useInfiniteQuery({
    queryKey: ['projects', projectId, 'documents', filters],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/documents', {
          params: {
            path: { project_id: projectId },
            query: {
              limit: DOCUMENTS_PAGE_SIZE,
              offset: pageParam,
              search: filters.search || null,
              folder: filters.folder,
            },
          },
        }),
      ),
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((sum, page) => sum + page.items.length, 0);
      return loaded < last.total && last.items.length > 0 ? loaded : undefined;
    },
    placeholderData: keepPreviousData,
  });
}

/** URL del visor para un fichero de `Conversión/` (imágenes del Markdown y enlaces de descarga). */
export function outputUrl(projectId: number, path: string): string {
  return `/api/v1/projects/${projectId}/outputs?path=${encodeURIComponent(path)}`;
}

/** Contenido de texto (Markdown o JSON) de una salida convertida. */
export function useOutputText(projectId: number, path: string | null) {
  return useQuery({
    queryKey: ['projects', projectId, 'outputs', path],
    enabled: path !== null,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/outputs', {
          params: { path: { project_id: projectId }, query: { path: path ?? '' } },
          parseAs: 'text',
        }),
      ) as unknown as string,
    retry: false,
  });
}

/** Búsqueda de texto completo en el Markdown convertido (todas las palabras). */
export function useContentSearch(projectId: number, q: string, folder: string | null, page: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'search', q, folder, page],
    enabled: q.trim().length > 0,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/search', {
          params: {
            path: { project_id: projectId },
            query: {
              q,
              folder,
              limit: SEARCH_PAGE_SIZE,
              offset: (page - 1) * SEARCH_PAGE_SIZE,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Fragmento de la búsqueda en trozos de texto normal y coincidencias (nunca HTML). */
export function snippetParts(snippet: string): { text: string; match: boolean }[] {
  const parts: { text: string; match: boolean }[] = [];
  for (const [index, chunk] of snippet.split(MARK_START).entries()) {
    if (index === 0) {
      if (chunk) parts.push({ text: chunk, match: false });
      continue;
    }
    const [match, rest] = chunk.split(MARK_END, 2) as [string, string | undefined];
    parts.push({ text: match, match: true });
    if (rest) parts.push({ text: rest, match: false });
  }
  return parts;
}
