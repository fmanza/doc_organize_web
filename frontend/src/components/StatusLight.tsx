import { Badge, Tooltip, VisuallyHidden } from '@mantine/core';
import { useTranslation } from 'react-i18next';

export type LightStatus = 'unknown' | 'ok' | 'degraded' | 'unavailable';

const STYLE: Record<LightStatus, { color: string; icon: string }> = {
  ok: { color: 'green', icon: '●' },
  degraded: { color: 'orange', icon: '▲' },
  unavailable: { color: 'red', icon: '■' },
  unknown: { color: 'gray', icon: '?' },
};

interface StatusLightProps {
  status: LightStatus;
  /** Códigos de los problemas del último sondeo (`slow`, `low_space`…), que se explican en el tooltip. */
  reasons?: string[] | null | undefined;
}

/**
 * Semáforo de estado (sustituye a `_semaforo_macros` de la web integrada). El estado no depende solo del color:
 * cada uno tiene icono y texto propios (WCAG 1.4.1).
 */
export function StatusLight({ status, reasons }: StatusLightProps) {
  const { t } = useTranslation();
  const { color, icon } = STYLE[status];
  const badge = (
    <Badge color={color} variant="light" leftSection={<span aria-hidden="true">{icon}</span>}>
      {t(`status.${status}`)}
    </Badge>
  );
  if (!reasons || reasons.length === 0) {
    return badge;
  }
  const label = reasons.map((reason) => t(`status.reasons.${reason}`, { defaultValue: reason })).join(' · ');
  return (
    <Tooltip label={label} withArrow>
      <span>
        {badge}
        <VisuallyHidden> ({label})</VisuallyHidden>
      </span>
    </Tooltip>
  );
}
