import { useQuery } from '@tanstack/react-query';

import { api, ApiError, type Problem } from '../../api/client';
import type { components } from '../../api/schema';

export type HealthStatus = components['schemas']['HealthStatus'];

/** Estado del servicio; un 503 trae el mismo cuerpo con `status: 'degraded'` y se muestra, no es un error. */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async (): Promise<HealthStatus> => {
      const { data, error, response } = await api.GET('/api/health');
      if (data !== undefined) {
        return data;
      }
      if (response.status === 503 && error !== undefined) {
        return error;
      }
      throw new ApiError({
        title: response.statusText || 'Error',
        status: response.status,
      } satisfies Problem);
    },
    refetchInterval: 60_000,
  });
}
