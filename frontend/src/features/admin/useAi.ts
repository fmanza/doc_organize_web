import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type AiSettings = components['schemas']['AiSettingsOut'];
export type AiFamily = components['schemas']['AiFamilyOut'];
export type AiField = components['schemas']['AiFieldOut'];
export type AiFamilyKey = AiFamily['key'];
export type AiUsageSource = components['schemas']['AiUsageSourceOut'];

/** Configuración de IA de la instancia (solo admin; nunca trae secretos). */
export function useAiSettings() {
  return useQuery({
    queryKey: ['admin', 'ai-settings'],
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/ai-settings')),
  });
}

/** Guarda o borra campos de una familia: ausente = no se toca; `null` = borrar el valor guardado. */
export function useUpdateAiFamily() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ family, fields }: { family: AiFamilyKey; fields: Record<string, string | null> }) =>
      unwrap(
        await api.PUT('/api/v1/admin/ai-settings/{family}', {
          params: { path: { family } },
          body: { fields },
        }),
      ),
    onSuccess: (family) => {
      queryClient.setQueryData<AiSettings>(['admin', 'ai-settings'], (current) =>
        current
          ? {
              ...current,
              families: current.families.map((item) => (item.key === family.key ? family : item)),
            }
          : current,
      );
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ['ai', 'status'] }),
        queryClient.invalidateQueries({ queryKey: ['admin', 'ai-usage'] }),
      ]);
    },
  });
}

/** Familias configuradas (cualquier usuario): activa la IA en la página de contexto. */
export function useAiStatus() {
  return useQuery({
    queryKey: ['ai', 'status'],
    queryFn: async () => unwrap(await api.GET('/api/v1/ai/status')).families,
  });
}

/** Uso de LiteLLM y Copilot; el servidor lo guarda 5 minutos. */
export function useAiUsage() {
  return useQuery({
    queryKey: ['admin', 'ai-usage'],
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/ai-usage')).sources,
  });
}

/** Pide datos nuevos saltando la caché del servidor (como mucho una vez cada 30 s). */
export function useRefreshAiUsage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.GET('/api/v1/admin/ai-usage', { params: { query: { refresh: true } } })).sources,
    onSuccess: (sources) => queryClient.setQueryData(['admin', 'ai-usage'], sources),
  });
}
