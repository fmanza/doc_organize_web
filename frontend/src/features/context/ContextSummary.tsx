import { Alert, Anchor, Badge, Button, Card, Group, SimpleGrid, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { formatCount, formatDateTime } from '../../components/format';
import { type ContextOut } from './useContext';

export function Summary({
  context,
  canDelete,
  onDelete,
}: {
  context: ContextOut;
  canDelete: boolean;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const stats: [string, number][] = [
    ['domains', context.domains.length],
    ['documents', context.documents_count],
    ['unclassified', context.unclassified_count],
    ['failed', context.failed_count],
    ['collisions', context.collisions_count],
  ];
  return (
    <Card withBorder>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {t('context.summary.title', { date: formatDateTime(context.built_at) })}
        </Title>
        {context.built_by_run_id && (
          <Anchor component={Link} to={`/runs/${context.built_by_run_id}`} size="sm">
            {t('context.summary.openRun')}
          </Anchor>
        )}
      </Group>
      <Text size="sm" mb="xs">
        {t('context.summary.folder', { folder: context.output_folder_name })} ·{' '}
        <CatalogName context={context} />
        {context.ai_classification && (
          <Badge ml="xs" size="sm" variant="light" color="grape">
            {t('context.ai.badge')}
          </Badge>
        )}
      </Text>
      <Traceability context={context} />
      <SimpleGrid cols={{ base: 2, sm: 5 }} spacing="xs" component="dl">
        {stats.map(([key, value]) => (
          <div key={key}>
            <Text size="xs" c="dimmed" component="dt">
              {t(`context.summary.${key}`)}
            </Text>
            <Text component="dd" m={0}>
              {formatCount(value)}
            </Text>
          </div>
        ))}
      </SimpleGrid>
      {context.failed_count > 0 && (
        <Alert color="orange" mt="sm">
          {t('context.warnings.failed', { count: context.failed_count })}
        </Alert>
      )}
      {context.collisions_count > 0 && (
        <Alert color="orange" mt="sm">
          {t('context.warnings.collisions', { count: context.collisions_count })}
        </Alert>
      )}
      {canDelete && (
        <Group mt="sm" justify="flex-end">
          <Button color="red" variant="light" onClick={onDelete}>
            {t('projects.danger.context_delete.button')}
          </Button>
        </Group>
      )}
    </Card>
  );
}

/** Catálogo con el que se construyó el contexto, y su plantilla si la hay. */
function CatalogName({ context }: { context: ContextOut }) {
  const { t } = useTranslation();
  return (
    <>
      {t(`context.catalog.${context.catalog_kind}`, { defaultValue: context.catalog_kind })}
      {context.taxonomy_template_name ? ` «${context.taxonomy_template_name}»` : ''}
    </>
  );
}

/** Paso «Entregar»: el sitio navegable (o por qué no lo hay); el Excel, el ZIP y el paquete van en `DeliveryCard`. */
export function SiteCard({ context, projectId }: { context: ContextOut; projectId: number }) {
  const { t } = useTranslation();
  return (
    <Card withBorder component="section" aria-label={t('context.site.title')}>
      <Title order={3} size="h4" mb="xs">
        {t('context.site.title')}
      </Title>
      {context.site_built ? (
        <Button component={Link} to={`/projects/${projectId}/context/site`} w="fit-content">
          {t('context.site.open')}
        </Button>
      ) : (
        <Alert color="gray">{t('context.warnings.noSite')}</Alert>
      )}
    </Card>
  );
}

/** Versión de doc_organize y modelos de IA de la construcción (1.5.0); nada en contextos anteriores. */
function Traceability({ context }: { context: ContextOut }) {
  const { t } = useTranslation();
  const parts = [
    context.built_with_version && t('context.trace.version', { version: context.built_with_version }),
    context.ai_classification_model &&
      t('context.trace.classificationModel', { model: context.ai_classification_model }),
    context.ai_enrichment_model && t('context.trace.enrichmentModel', { model: context.ai_enrichment_model }),
  ].filter(Boolean);
  if (parts.length === 0) {
    return null;
  }
  return (
    <Text size="xs" c="dimmed" mb="xs">
      {parts.join(' · ')}
    </Text>
  );
}
