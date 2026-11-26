import {
  Alert,
  Anchor,
  Button,
  Card,
  Group,
  NumberInput,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';
import { ErrorAlert } from '../../components/ErrorAlert';
import { useAiStatus } from '../admin/useAi';
import { type ProjectOut, useEnqueueRun } from '../projects/useProjects';
import {
  AI_CLASSIFY_TASK,
  buildParams,
  type ContextBuildParams,
  type ContextOut,
  DEFAULT_OUTPUT_FOLDER,
  type NotReady,
  type Selection,
  stepHref,
} from './useContext';

type AiScope = NonNullable<ContextBuildParams['ai_scope']>;

/**
 * Paso 2 · Construir: con qué taxonomía se construye (y «Cambiar», que vuelve al paso 1), carpeta, umbral, sitio e IA.
 * La taxonomía se elige en el paso 1; aquí solo se dice por qué no se puede construir todavía.
 */
export function BuildCard({
  project,
  context,
  selection,
  domains,
  notReady,
  leftoverFolder,
}: {
  project: ProjectOut;
  context: ContextOut | null;
  selection: Selection;
  domains: string[];
  notReady: NotReady | null;
  /** Carpeta de un contexto a medio guardar: la construcción la reutiliza (el job lo hace igual). */
  leftoverFolder: string | null;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const enqueue = useEnqueueRun(project.id);
  const { catalog, template } = selection;
  const [folder, setFolder] = useState(DEFAULT_OUTPUT_FOLDER);
  const [threshold, setThreshold] = useState(0.5);
  const [buildSite, setBuildSite] = useState(true);
  const status = useAiStatus();
  const [withAi, setWithAi] = useState(false);
  const [withEnrichment, setWithEnrichment] = useState(false);
  // 2.1: qué se envía a la IA. «También los ejes vacíos» solo tiene sentido con ejes de etiqueta (plantilla o
  // manifiesto); por defecto, lo de siempre (D2: no disparar el coste sin querer).
  const [scope, setScope] = useState<AiScope>('unclassified');
  const scopable = catalog === 'template' || catalog === 'manifest';
  const aiScope: AiScope = scopable ? scope : 'unclassified';
  const aiAvailable = status.data?.[AI_CLASSIFY_TASK] === true;
  const enrichmentAvailable = status.data?.enrich === true;

  const launch = () =>
    enqueue.mutate(
      buildParams({
        catalog,
        domains: catalog === 'domains' ? domains : [],
        template_name: catalog === 'template' ? template : null,
        output_folder_name: context ? null : folder.trim() || null,
        threshold,
        build_site: buildSite,
        ai_classification: withAi && aiAvailable,
        ai_scope: withAi && aiAvailable ? aiScope : 'unclassified',
        ai_enrichment: withEnrichment && enrichmentAvailable,
      }),
      { onSuccess: (run) => void navigate(`/runs/${run.id}`) },
    );

  return (
    <Card
      withBorder
      component="section"
      aria-label={t(context ? 'context.build.rebuildTitle' : 'context.build.title')}
    >
      <Title order={3} size="h4" mb="xs">
        {t(context ? 'context.build.rebuildTitle' : 'context.build.title')}
      </Title>
      <Stack>
        <Group gap="xs">
          <Text size="sm">
            {t('context.build.uses', { catalog: t(`context.catalog.${catalog}`) })}
            {catalog === 'template' && template ? ` «${template}»` : ''}
            {catalog === 'domains' && domains.length > 0 ? ` (${domains.join(', ')})` : ''}
          </Text>
          <Anchor component={Link} to={stepHref(project.id, 'taxonomia')} size="sm">
            {t('context.build.change')}
          </Anchor>
        </Group>
        <Group align="flex-end">
          {context ? (
            <Text size="sm">{t('context.build.folderFixed', { folder: context.output_folder_name })}</Text>
          ) : leftoverFolder ? (
            <Text size="sm">{t('context.build.folderLeftover', { folder: leftoverFolder })}</Text>
          ) : (
            <TextInput
              label={t('context.build.folder')}
              description={t('context.build.folderHelp')}
              value={folder}
              maxLength={120}
              onChange={(event) => setFolder(event.currentTarget.value)}
            />
          )}
          <NumberInput
            label={t('context.build.threshold')}
            min={0}
            max={1}
            step={0.05}
            decimalScale={2}
            clampBehavior="strict"
            value={threshold}
            onChange={(value) => setThreshold(typeof value === 'number' ? value : 0.5)}
            w={160}
          />
          <Switch
            label={t('context.build.site')}
            checked={buildSite}
            onChange={(event) => setBuildSite(event.currentTarget.checked)}
          />
        </Group>
        <Switch
          label={t('context.ai.classify')}
          description={t(
            aiAvailable ? 'context.ai.classifyHelp' : `context.ai.notConfigured.${AI_CLASSIFY_TASK}`,
          )}
          checked={withAi && aiAvailable}
          disabled={!aiAvailable}
          onChange={(event) => setWithAi(event.currentTarget.checked)}
        />
        {withAi && aiAvailable && scopable && (
          <Stack gap={4}>
            <Text size="sm" fw={500} id="alcance-ia">
              {t('context.ai.scope')}
            </Text>
            <SegmentedControl
              w="fit-content"
              value={aiScope}
              onChange={(value) => setScope(value as AiScope)}
              aria-labelledby="alcance-ia"
              data={(['unclassified', 'missing_axes'] as const).map((value) => ({
                value,
                label: t(`context.ai.scopes.${value}`),
              }))}
            />
            <Text size="xs" c="dimmed">
              {t(`context.ai.scopeHelp.${aiScope}`)}
            </Text>
          </Stack>
        )}
        {withAi && aiAvailable && (
          <Alert color="grape" title={t('context.ai.egressTitle')}>
            {t('context.ai.egress')}
          </Alert>
        )}
        <Switch
          label={t('context.ai.enrich')}
          description={t(enrichmentAvailable ? 'context.ai.enrichHelp' : 'context.ai.notConfigured.enrich')}
          checked={withEnrichment && enrichmentAvailable}
          disabled={!enrichmentAvailable}
          onChange={(event) => setWithEnrichment(event.currentTarget.checked)}
        />
        {withEnrichment && enrichmentAvailable && (
          <Alert color="grape" title={t('context.ai.egressTitle')}>
            {t('context.ai.enrichEgress')}
          </Alert>
        )}
        {notReady && (
          <Alert color="orange" role="status">
            {t(`context.build.notReady.${notReady}`)}{' '}
            <Anchor component={Link} to={stepHref(project.id, 'taxonomia')} size="sm">
              {t('context.build.change')}
            </Anchor>
          </Alert>
        )}
        {enqueue.isError && <ErrorAlert error={enqueue.error} />}
        <Group justify="flex-end">
          <Button onClick={launch} loading={enqueue.isPending} disabled={notReady !== null}>
            {t(context ? 'context.build.rebuild' : 'context.build.run')}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}
