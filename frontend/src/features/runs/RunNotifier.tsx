import { Anchor, Notification, Portal, Stack } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { api, unwrap } from '../../api/client';
import { useMe } from '../auth/useAuth';
import type { RunOut } from './useRuns';

/** Cada cuánto se miran las ejecuciones propias en marcha. */
const POLL_MS = 15_000;
/** Cuánto se ve un aviso antes de cerrarse solo. */
const TOAST_MS = 15_000;
const ACTIVE = new Set<RunOut['status']>(['queued', 'running']);
const COLOR: Partial<Record<RunOut['status'], string>> = {
  succeeded: 'green',
  failed: 'red',
  cancelled: 'gray',
};

interface Toast {
  run: RunOut;
}

/** El navegador avisa si el usuario lo permitió y la pestaña no está a la vista. */
function browserNotice(title: string, body: string): void {
  try {
    // `window.Notification`: el `Notification` importado es el componente de Mantine.
    const Native = window.Notification as typeof window.Notification | undefined;
    if (Native && Native.permission === 'granted' && document.hidden) {
      new Native(title, { body, tag: 'dow-run' });
    }
  } catch {
    // Sin permiso o sin soporte: queda el aviso dentro de la aplicación.
  }
}

/**
 * Avisa cuando termina una ejecución propia (M2, Fase 10): aviso en la aplicación y, con la pestaña en segundo plano y
 * permiso concedido, notificación del navegador. Mira las ejecuciones recientes cada `POLL_MS`: avisa de las que pasan
 * a un estado final y de las que ya lo están pero terminaron después de abrir la aplicación (una corta puede empezar y
 * acabar entre dos consultas).
 */
export function RunNotifier() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const [openedAt] = useState(() => Date.now());
  const seen = useRef<Map<string, RunOut['status']>>(new Map());
  const [toasts, setToasts] = useState<Toast[]>([]);
  const recent = useQuery({
    queryKey: ['runs', 'notifier'],
    enabled: me !== undefined && me !== null,
    refetchInterval: POLL_MS,
    queryFn: async () => unwrap(await api.GET('/api/v1/runs', { params: { query: { limit: 25 } } })),
  });

  useEffect(() => {
    if (!recent.data || !me) {
      return;
    }
    for (const run of recent.data.items) {
      if (run.created_by_username !== me.username) {
        continue;
      }
      const before = seen.current.get(run.id);
      seen.current.set(run.id, run.status);
      const final = !ACTIVE.has(run.status);
      const wasActive = before !== undefined && ACTIVE.has(before);
      const finishedSinceOpened =
        before === undefined && run.finished_at !== null && Date.parse(run.finished_at) > openedAt;
      if (!final || !(wasActive || finishedSinceOpened)) {
        continue;
      }
      setToasts((current) => [...current.filter((toast) => toast.run.id !== run.id), { run }]);
      browserNotice(
        t('runs.notify.title', { operation: t(`runs.operations.${run.operation}`) }),
        t(`runs.notify.${run.status}`, { project: run.project_name ?? '' }),
      );
      window.setTimeout(
        () => setToasts((current) => current.filter((toast) => toast.run.id !== run.id)),
        TOAST_MS,
      );
    }
  }, [recent.data, me, t, openedAt]);

  if (toasts.length === 0) {
    return null;
  }
  return (
    <Portal>
      <Stack
        gap="xs"
        role="status"
        aria-live="polite"
        style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 400, maxWidth: 360 }}
      >
        {toasts.map(({ run }) => (
          <Notification
            key={run.id}
            color={COLOR[run.status] ?? 'blue'}
            title={t('runs.notify.title', { operation: t(`runs.operations.${run.operation}`) })}
            onClose={() => setToasts((current) => current.filter((toast) => toast.run.id !== run.id))}
            closeButtonProps={{ 'aria-label': t('runs.notify.close') }}
          >
            {t(`runs.notify.${run.status}`, { project: run.project_name ?? '' })}{' '}
            <Anchor component={Link} to={`/runs/${run.id}`} size="sm">
              {t('runs.notify.open')}
            </Anchor>
          </Notification>
        ))}
      </Stack>
    </Portal>
  );
}
