import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';

import { isApiError } from '../api/client';
import { meQueryKey } from '../features/auth/useAuth';

export function createQueryClient(): QueryClient {
  // Un 401 en cualquier llamada (sesión caducada o revocada) revalida el usuario actual: la guarda de rutas
  // redirige entonces al login.
  const onError = (error: unknown) => {
    if (isApiError(error, 401)) {
      void client.invalidateQueries({ queryKey: meQueryKey });
    }
  };
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // Los 4xx no mejoran reintentando.
        retry: (failureCount, error) => failureCount < 1 && !(isApiError(error) && error.status < 500),
        refetchOnWindowFocus: false,
      },
    },
  });
  return client;
}
