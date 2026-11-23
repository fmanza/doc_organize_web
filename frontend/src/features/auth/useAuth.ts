import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, CSRF_HEADER, ensureOk, isApiError, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type Me = components['schemas']['Me'];
export type LoginRequest = components['schemas']['LoginRequest'];
export type PasswordChange = components['schemas']['PasswordChange'];
export type ColorScheme = Me['color_scheme'];

export const meQueryKey = ['auth', 'me'] as const;

export type Permission = Me['permissions'][number];

/** Si `me` tiene `permission` en su tenant activo (el admin de instancia los tiene todos). */
export function can(me: Me | null | undefined, permission: Permission): boolean {
  return !!me && (me.is_instance_admin || me.permissions.includes(permission));
}

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

/**
 * Guarda el tema del usuario (2.3). Optimista: `me` cambia al momento (y con él el tema, por `ColorSchemeSync`) y, si
 * el servidor falla, vuelve al anterior.
 */
export function useUpdateColorScheme() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (color_scheme: ColorScheme): Promise<Me> =>
      unwrap(await api.PUT('/api/v1/auth/me/preferences', { body: { color_scheme } })),
    onMutate: async (color_scheme) => {
      await queryClient.cancelQueries({ queryKey: meQueryKey });
      const previous = queryClient.getQueryData<Me | null>(meQueryKey);
      if (previous) {
        queryClient.setQueryData<Me>(meQueryKey, { ...previous, color_scheme });
      }
      return { previous };
    },
    onError: (_error, _scheme, context) => {
      if (context?.previous) {
        queryClient.setQueryData(meQueryKey, context.previous);
      }
    },
    onSuccess: (me) => {
      queryClient.setQueryData(meQueryKey, me);
    },
  });
}

/** Ruta interna segura a la que volver tras el login (evita redirecciones abiertas). */
export function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login') ? next : '/';
}
