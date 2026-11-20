import { Alert, Badge, Group, MultiSelect, Stack, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import type { components } from '../../api/schema';
import { formatCount } from '../../components/format';

type ContextAxis = components['schemas']['ContextAxisOut'];
type AxisValue = components['schemas']['AxisValueOut'];
type Provenance = components['schemas']['PromptProvenanceOut'];
type FrontMatterReport = components['schemas']['FrontMatterReportOut'];

/** Como mucho 20 valores de eje a la vez (`axis=clave:slug`, límite de la API). */
const MAX_AXIS_FILTERS = 20;

/** Color y texto de quién asignó un valor (doc_organize 2.0): las reglas no llevan marca. */
const ORIGIN: Record<string, { color: string; key: string }> = {
  ai: { color: 'grape', key: 'context.axes.byAi' },
  semantic: { color: 'cyan', key: 'context.axes.bySemantic' },
  human: { color: 'teal', key: 'context.axes.byHuman' },
};

/** Ejes por los que se puede filtrar: todos menos el que organiza carpetas (el dominio ya se elige en la tabla). */
function filterableAxes(axes: ContextAxis[]): ContextAxis[] {
  return axes.filter((axis) => axis.organizes !== 'folder' && axis.values.length > 0);
}

/**
 * Un `MultiSelect` por eje con el recuento de cada valor. `value` son filtros `clave:slug`: los valores de un mismo eje
 * se combinan con O y los ejes entre sí con Y (lo hace la API).
 */
export function AxisFilters({
  axes,
  value,
  onChange,
}: {
  axes: ContextAxis[];
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const { t } = useTranslation();
  const filterable = filterableAxes(axes);
  if (filterable.length === 0) {
    return null;
  }
  return (
    <Group align="flex-end" gap="sm" mt="xs">
      {filterable.map((axis) => {
        const prefix = `${axis.key}:`;
        const selected = value
          .filter((item) => item.startsWith(prefix))
          .map((item) => item.slice(prefix.length));
        const others = value.filter((item) => !item.startsWith(prefix));
        return (
          <MultiSelect
            key={axis.key}
            label={axis.name}
            w={260}
            clearable
            searchable
            value={selected}
            maxValues={Math.max(selected.length, MAX_AXIS_FILTERS - others.length)}
            data={axis.values.map((item) => ({
              value: item.slug,
              label: t('context.axes.option', { name: item.name, count: formatCount(item.documents) }),
            }))}
            onChange={(slugs) => onChange([...others, ...slugs.map((slug) => `${prefix}${slug}`)])}
          />
        );
      })}
    </Group>
  );
}

/** Insignias de los valores de cada eje del documento, con la marca de quién los asignó (salvo las reglas). */
export function AxisBadges({ axes, values }: { axes: ContextAxis[]; values: Record<string, AxisValue[]> }) {
  const { t } = useTranslation();
  const shown = axes.filter((axis) => axis.organizes !== 'folder' && (values[axis.key]?.length ?? 0) > 0);
  if (shown.length === 0) {
    return null;
  }
  return (
    <Group gap={4} mt={2}>
      {shown.map((axis) =>
        (values[axis.key] ?? []).map((item) => {
          const origin = item.classified_by ? ORIGIN[item.classified_by] : undefined;
          return (
            <Badge
              key={`${axis.key}:${item.slug}`}
              size="xs"
              variant="outline"
              color={origin?.color ?? 'blue'}
              tt="none"
              title={axis.name}
            >
              {item.name}
              {origin && ` · ${t(origin.key)}`}
            </Badge>
          );
        }),
      )}
    </Group>
  );
}

/**
 * Evidencia (cita de la IA y si se encontró en el texto enviado) de cada valor y, si los asignó la IA, con qué prompt
 * y modelo (procedencia de la construcción).
 */
export function AxisEvidence({
  axes,
  values,
  provenance,
}: {
  axes: ContextAxis[];
  values: Record<string, AxisValue[]>;
  provenance: Provenance[];
}) {
  const { t } = useTranslation();
  const names = Object.fromEntries(axes.map((axis) => [axis.key, axis.name]));
  const cited = Object.entries(values).flatMap(([key, items]) =>
    items.filter((item) => item.evidence).map((item) => ({ key, item })),
  );
  const byAi = Object.values(values).some((items) => items.some((item) => item.classified_by === 'ai'));
  const classify = provenance.find((item) => item.task === 'classify');
  if (cited.length === 0 && !(byAi && classify)) {
    return null;
  }
  return (
    <Stack gap={2}>
      {cited.map(({ key, item }) => (
        <Text size="xs" key={`${key}:${item.slug}`}>
          {t('context.axes.evidence', { axis: names[key] ?? key, value: item.name, evidence: item.evidence })}
          <Badge ml={4} size="xs" variant="light" color={item.evidence_verified ? 'teal' : 'orange'}>
            {t(item.evidence_verified ? 'context.axes.verified' : 'context.axes.notVerified')}
          </Badge>
        </Text>
      ))}
      {byAi && classify && (
        <Text size="xs" c="dimmed">
          {t('context.axes.provenance', {
            prompt: classify.prompt_id,
            version: classify.version,
            source: t(`context.axes.sources.${classify.source}`, { defaultValue: classify.source }),
            model: classify.model,
          })}
        </Text>
      )}
    </Stack>
  );
}

/** Avisos del front matter al guardar o ver una plantilla o manifiesto: claves que no se usan y ejes implícitos. */
export function FrontMatterNotices({ report }: { report: FrontMatterReport | undefined }) {
  const { t } = useTranslation();
  if (!report) {
    return null;
  }
  return (
    <>
      {report.ignored_keys.length > 0 && (
        <Alert color="orange" mt="xs" title={t('context.frontMatter.ignoredTitle')}>
          {t('context.frontMatter.ignored', { keys: report.ignored_keys.join(', ') })}
        </Alert>
      )}
      {report.implicit_axes.length > 0 && (
        <Alert color="gray" mt="xs" title={t('context.frontMatter.implicitTitle')}>
          {t('context.frontMatter.implicit', { keys: report.implicit_axes.join(', ') })}
        </Alert>
      )}
    </>
  );
}
