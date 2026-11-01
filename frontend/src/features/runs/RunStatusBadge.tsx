import { Badge } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import type { RunStatus } from './useRuns';

const STYLE: Record<RunStatus, { color: string; icon: string }> = {
  queued: { color: 'gray', icon: '…' },
  running: { color: 'blue', icon: '▶' },
  succeeded: { color: 'green', icon: '✓' },
  failed: { color: 'red', icon: '✕' },
  cancelled: { color: 'orange', icon: '■' },
};

/** Estado de una ejecución con icono y texto, no solo color (WCAG 1.4.1). */
export function RunStatusBadge({ status }: { status: RunStatus }) {
  const { t } = useTranslation();
  const { color, icon } = STYLE[status];
  return (
    <Badge color={color} variant="light" leftSection={<span aria-hidden="true">{icon}</span>}>
      {t(`runs.status.${status}`)}
    </Badge>
  );
}
