import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ListParams, SortOf } from '../../api/listing';
import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type ScanParams = components['schemas']['ScanParams'];
export type ScannedFolderOut = components['schemas']['ScannedFolderOut'];
export type ScanErrorPage = components['schemas']['ScanErrorPage'];
export type ScanOptionsAvailability = components['schemas']['ScanOptionsAvailability'];

/** Opciones del escaneo que elige el usuario (las de `ScanOptions` de doc_organize). */
export type ScanOptionKey =
  'use_ocr' | 'use_gpu' | 'include_audio_video' | 'extract_images' | 'use_picture_description';
export type ScanOptions = Record<ScanOptionKey, boolean>;

export const SCAN_OPTION_KEYS: readonly ScanOptionKey[] = [
  'use_ocr',
  'use_gpu',
  'include_audio_video',
  'extract_images',
  'use_picture_description',
];

/** Valores por defecto de doc_organize: OCR activado, el resto desactivado. */
export const DEFAULT_SCAN_OPTIONS: ScanOptions = {
  use_ocr: true,
  use_gpu: false,
  include_audio_video: false,
  extract_images: false,
  use_picture_description: false,
};

/** Cuerpo de un escaneo sin forzar (el cliente generado exige todos los campos con valor por defecto). */
export function scanRequest(folders: string[], options: ScanOptions): ScanParams {
  return { operation: 'scan', folders, ...options, force: false, dry_run: false };
}

export function useScannedFolders(projectId: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'scanned-folders'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/scanned-folders', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

function useInvalidateFolders(projectId: number) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'scanned-folders'] }),
      queryClient.invalidateQueries({ queryKey: ['projects', projectId], exact: true }),
    ]);
}

export function useAddFolder(projectId: number) {
  const invalidate = useInvalidateFolders(projectId);
  return useMutation({
    mutationFn: async (subpath: string) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/scanned-folders', {
          params: { path: { project_id: projectId } },
          body: { subpath },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useRemoveFolder(projectId: number) {
  const invalidate = useInvalidateFolders(projectId);
  return useMutation({
    mutationFn: async (subpath: string) =>
      unwrap(
        await api.DELETE('/api/v1/projects/{project_id}/scanned-folders', {
          params: { path: { project_id: projectId }, query: { subpath } },
        }),
      ),
    onSuccess: invalidate,
  });
}

/** Errores de un run (`runId`) o, sin él, del último escaneo terminado del proyecto; paginados en servidor. */
export type ScanErrorSort = SortOf<'/api/v1/runs/{run_id}/scan-errors'>;

export function useScanErrors(
  target: { runId: string } | { projectId: number },
  query: ListParams<ScanErrorSort>,
) {
  return useQuery({
    queryKey: ['scan-errors', target, query],
    queryFn: async () =>
      'runId' in target
        ? unwrap(
            await api.GET('/api/v1/runs/{run_id}/scan-errors', {
              params: { path: { run_id: target.runId }, query },
            }),
          )
        : unwrap(
            await api.GET('/api/v1/projects/{project_id}/scan-errors', {
              params: { path: { project_id: target.projectId }, query },
            }),
          ),
    placeholderData: keepPreviousData,
  });
}
