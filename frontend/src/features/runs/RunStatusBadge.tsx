import { Badge } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { Icon } from '../../components/Icon';
import { RUN_STATUS_ICONS } from '../../components/icons';
import type { RunStatus } from './useRuns';

const COLOR: Record<RunStatus, string> = {
  queued: 'gray',
  running: 'blue',
  succeeded: 'green',
  failed: 'red',
  cancelled: 'orange',
};

/** Estado de una ejecución con icono y texto, no solo color (WCAG 1.4.1). */
export function RunStatusBadge({ status }: { status: RunStatus }) {
  const { t } = useTranslation();
  return (
    <Badge color={COLOR[status]} variant="light" leftSection={<Icon of={RUN_STATUS_ICONS[status]} />}>
      {t(`runs.status.${status}`)}
    </Badge>
  );
}
