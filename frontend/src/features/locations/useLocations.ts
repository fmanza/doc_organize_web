import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type LocationPublic = components['schemas']['LocationPublic'];
export type LocationOut = components['schemas']['LocationOut'];
export type AnyLocation = LocationPublic | LocationOut;
export type LocationCreate = components['schemas']['LocationCreate'];
export type LocationUpdate = components['schemas']['LocationUpdate'];
export type FolderListing = components['schemas']['FolderListing'];
export type LocationStatus = LocationPublic['status'];

export const FOLDER_PAGE_SIZE = 200;

/** La respuesta trae `container_path` solo para administradores. */
export function isAdminView(location: AnyLocation): location is LocationOut {
  return 'container_path' in location;
}

export function useLocations() {
  return useQuery({
    queryKey: ['locations'],
    queryFn: async () => unwrap(await api.GET('/api/v1/locations', { params: { query: { limit: 200 } } })),
  });
}

export function useLocation(id: number) {
  return useQuery({
    queryKey: ['locations', id],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/locations/{location_id}', { params: { path: { location_id: id } } })),
  });
}

/** Subcarpetas de `path` en una ubicación; con `locationId === null`, bajo la raíz de montajes (solo admin). */
export function useFolders(locationId: number | null, path: string, page: number) {
  const offset = (page - 1) * FOLDER_PAGE_SIZE;
  return useQuery({
    queryKey: ['folders', locationId ?? 'mounts', path, page],
    queryFn: async () =>
      locationId === null
        ? unwrap(
            await api.GET('/api/v1/admin/mounts', {
              params: { query: { path, limit: FOLDER_PAGE_SIZE, offset } },
            }),
          )
        : unwrap(
            await api.GET('/api/v1/fs/browse', {
              params: { query: { location_id: locationId, path, limit: FOLDER_PAGE_SIZE, offset } },
            }),
          ),
    placeholderData: keepPreviousData,
    retry: false,
  });
}

function useInvalidateLocations() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['locations'] }),
      queryClient.invalidateQueries({ queryKey: ['folders'] }),
    ]);
}

export function useCreateLocation() {
  const invalidate = useInvalidateLocations();
  return useMutation({
    mutationFn: async (body: LocationCreate) => unwrap(await api.POST('/api/v1/locations', { body })),
    onSuccess: invalidate,
  });
}

export function useUpdateLocation() {
  const invalidate = useInvalidateLocations();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: LocationUpdate }) =>
      unwrap(
        await api.PATCH('/api/v1/locations/{location_id}', { params: { path: { location_id: id } }, body }),
      ),
    onSuccess: invalidate,
  });
}

export function useDeleteLocation() {
  const invalidate = useInvalidateLocations();
  return useMutation({
    mutationFn: async (id: number) =>
      ensureOk(
        await api.DELETE('/api/v1/locations/{location_id}', { params: { path: { location_id: id } } }),
      ),
    onSuccess: invalidate,
  });
}

export function useProbeLocation() {
  const invalidate = useInvalidateLocations();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.POST('/api/v1/locations/{location_id}/probe', { params: { path: { location_id: id } } }),
      ),
    onSuccess: invalidate,
  });
}
