import { Alert, Button, Group, ScrollArea, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { BackLink } from '../../components/BackLink';
import { formatCount, formatDateTime } from '../../components/format';
import { canDo, useProject } from '../projects/useProjects';
import {
  type ContextNavStep,
  type ContextOut,
  NEEDS_CONTEXT,
  stepHref,
  useProjectContext,
} from './useContext';

/** Orden de la navegación: los pasos de la página (`?paso=`) y las subpáginas Revisar y Calidad. */
const NAV: readonly ContextNavStep[] = [
  'taxonomia',
  'construir',
  'resultado',
  'revisar',
  'calidad',
  'entregar',
];

/**
 * Cabecera común de las páginas del contexto (2026-11-22): volver al proyecto, título, estado del contexto, aviso de
 * desactualización y los pasos en orden de trabajo (Taxonomía → Construir → Resultado → Revisar → Calidad →
 * Entregar, e Historial). Los pasos que necesitan un contexto se ven deshabilitados hasta construirlo; «Construir»
 * solo aparece a quien puede construir.
 *
 * `subpage` (2.1.1): la página es una subpágina del paso activo (p. ej. el visor del sitio dentro de «Entregar»). El
 * paso se resalta, pero como enlace para volver a él, no como la página actual.
 */
export function ContextNav({
  projectId,
  active,
  subpage = false,
}: {
  projectId: number;
  active: ContextNavStep;
  subpage?: boolean;
}) {
  const { t } = useTranslation();
  const project = useProject(projectId);
  const context = useProjectContext(projectId);
  const built = context.data ?? null;
  const canBuild =
    project.data !== undefined &&
    canDo(project.data, 'editor') &&
    project.data.destination_location.access === 'rw';
  const steps = NAV.filter((step) => step !== 'construir' || canBuild);

  const item = (step: ContextNavStep, label: string) => {
    const current = step === active;
    if (NEEDS_CONTEXT.has(step) && !built) {
      return (
        <Button key={step} size="xs" variant="subtle" disabled title={t('context.steps.needsContext')}>
          {label}
        </Button>
      );
    }
    return (
      <Button
        key={step}
        component={Link}
        to={stepHref(projectId, step)}
        size="xs"
        variant={current ? (subpage ? 'light' : 'filled') : 'subtle'}
        aria-current={current && !subpage ? 'page' : undefined}
      >
        {label}
      </Button>
    );
  };

  return (
    <Stack gap="xs">
      {project.data && (
        <BackLink to={`/projects/${projectId}`}>{t('context.back', { name: project.data.name })}</BackLink>
      )}
      <Title order={2}>{t('context.title')}</Title>
      <Text size="sm" c="dimmed" role="status">
        {built
          ? t('context.steps.status', {
              date: formatDateTime(built.built_at),
              count: built.documents_count,
              formatted: formatCount(built.documents_count),
            })
          : context.isSuccess
            ? t('context.empty')
            : ''}
      </Text>
      <ScrollArea type="auto" offsetScrollbars>
        <Group component="nav" aria-label={t('context.steps.label')} gap={4} wrap="nowrap">
          {steps.map((step) => item(step, t(`context.steps.${step}`)))}
          <Text c="dimmed" aria-hidden>
            ·
          </Text>
          {item('historial', t('context.steps.historial'))}
        </Group>
      </ScrollArea>
      {built?.freshness && (
        <FreshnessBanner
          freshness={built.freshness}
          rebuildHref={canBuild ? stepHref(projectId, 'construir') : null}
        />
      )}
    </Stack>
  );
}

type Freshness = NonNullable<ContextOut['freshness']>;

/**
 * Aviso de frescura (W4, `check_context_freshness`): el contexto ya no refleja la caché del último escaneo. Con los
 * recuentos, unos ejemplos y, si puede construir, el enlace al paso «Construir». Va en la cabecera para verse en
 * cualquier paso (A5).
 */
function FreshnessBanner({ freshness, rebuildHref }: { freshness: Freshness; rebuildHref: string | null }) {
  const { t } = useTranslation();
  if (freshness.up_to_date) {
    return freshness.unknown > 0 ? (
      <Alert color="gray" title={t('context.freshness.unknownTitle')}>
        {t('context.freshness.unknown', { count: freshness.unknown })}
      </Alert>
    ) : null;
  }
  const parts = (['changed', 'added', 'removed'] as const)
    .filter((key) => freshness[key] > 0)
    .map((key) => t(`context.freshness.${key}`, { count: freshness[key] }));
  if (freshness.stale_site) {
    parts.push(t('context.freshness.staleSite'));
  }
  const examples = (['changed', 'added', 'removed'] as const).flatMap((key) =>
    freshness.examples[key].map((path) => ({ key, path })),
  );
  return (
    <Alert color="orange" title={t('context.freshness.title')} role="status">
      <Text size="sm">{parts.join(' · ')}</Text>
      {examples.length > 0 && (
        <Text component="details" size="xs" mt={4}>
          <summary style={{ cursor: 'pointer' }}>{t('context.freshness.examples')}</summary>
          <Stack gap={0} mt={2}>
            {examples.map(({ key, path }) => (
              <Text key={`${key}:${path}`} size="xs" ff="monospace">
                {t(`context.freshness.kinds.${key}`)}: {path}
              </Text>
            ))}
          </Stack>
        </Text>
      )}
      <Text size="xs" c="dimmed" mt={4}>
        {t('context.freshness.checkedAt', { date: formatDateTime(freshness.checked_at) })}
      </Text>
      {rebuildHref && (
        <Button component={Link} to={rebuildHref} mt="xs" size="xs" variant="light">
          {t('context.freshness.rebuild')}
        </Button>
      )}
    </Alert>
  );
}
