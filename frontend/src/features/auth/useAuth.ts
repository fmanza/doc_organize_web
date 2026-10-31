import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, CSRF_HEADER, ensureOk, isApiError, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type Me = components['schemas']['Me'];
export type LoginRequest = components['schemas']['LoginRequest'];
export type PasswordChange = components['schemas']['PasswordChange'];

export const meQueryKey = ['auth', 'me'] as const;

// La política real (incluidas las contraseñas comunes) la valida el servidor (DOW_PASSWORD_MIN_LENGTH); aquí solo se
// adelanta el mínimo por defecto.
export const PASSWORD_MIN_LENGTH = 12;

/** Usuario de la sesión actual; `null` si no hay sesión (401). */
export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async (): Promise<Me | null> => {
      try {
        return unwrap(await api.GET('/api/v1/auth/me'));
      } catch (error) {
        if (isApiError(error, 401)) {
          return null;
        }
        throw error;
      }
    },
    staleTime: 5 * 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: LoginRequest): Promise<Me> => {
      // Token CSRF previo al login: también pone la cookie CSRF.
      const { csrf_token } = unwrap(await api.GET('/api/v1/auth/csrf'));
      return unwrap(await api.POST('/api/v1/auth/login', { body, headers: { [CSRF_HEADER]: csrf_token } }));
    },
    onSuccess: (me) => {
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== meQueryKey[0] });
      queryClient.setQueryData(meQueryKey, me);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => ensureOk(await api.POST('/api/v1/auth/logout')),
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(meQueryKey, null);
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (body: PasswordChange) => ensureOk(await api.POST('/api/v1/auth/password', { body })),
  });
}

/** Ruta interna segura a la que volver tras el login (evita redirecciones abiertas). */
export function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login') ? next : '/';
}
