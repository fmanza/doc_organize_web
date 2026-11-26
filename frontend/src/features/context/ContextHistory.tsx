import { Alert, Badge, Button, Card, Group, Loader, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatCount, formatDateTime } from '../../components/format';
import { useEnqueueRun } from '../projects/useProjects';
import { CONTEXT_HISTORY_XLSX, type ContextBuild, useContextHistory } from './useContext';

/**
 * Historial del contexto (1.5.0): las últimas construcciones (fecha, versión, modelos y recuentos) y, al desplegar
 * una, los documentos que entraron, salieron o cambiaron de sitio. Se conserva al borrar el contexto.
 */
export function HistoryCard({ projectId }: { projectId: number }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const history = useContextHistory(projectId);
  const enqueue = useEnqueueRun(projectId);
  const exportButton = (
    <Button
      variant="light"
      size="xs"
      loading={enqueue.isPending}
      onClick={() =>
        enqueue.mutate(CONTEXT_HISTORY_XLSX, { onSuccess: (run) => void navigate(`/runs/${run.id}`) })
      }
    >
      {t('context.history.export')}
    </Button>
  );

  return (
    <Card withBorder component="section" aria-label={t('context.history.title')}>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {t('context.history.title')}
        </Title>
        {history.data && (history.data.total > 0 || history.data.error) && exportButton}
      </Group>
      <Text size="sm" c="dimmed" mb="xs">
        {t('context.history.intro')}
      </Text>
      {enqueue.isError && <ErrorAlert error={enqueue.error} mb="xs" />}
      {history.isError ? (
        <ErrorAlert error={history.error} />
      ) : !history.data ? (
        <Loader size="sm" aria-label={t('common.loading')} />
      ) : history.data.error ? (
        <Alert color="orange">{t('context.history.tooLarge')}</Alert>
      ) : history.data.items.length === 0 ? (
        <Text c="dimmed" role="status">
          {t('context.history.empty')}
        </Text>
      ) : (
        <Stack gap="xs">
          {history.data.items.map((build) => (
            <BuildEntry key={build.built_at} build={build} />
          ))}
          {history.data.total > history.data.items.length && (
            <Text size="xs" c="dimmed">
              {t('context.history.older', { count: history.data.total - history.data.items.length })}
            </Text>
          )}
        </Stack>
      )}
    </Card>
  );
}

function BuildEntry({ build }: { build: ContextBuild }) {
  const { t } = useTranslation();
  const none = t('context.history.none');
  const trace = [
    build.built_with_version && t('context.trace.version', { version: build.built_with_version }),
    build.ai_classification_model &&
      t('context.trace.classificationModel', { model: build.ai_classification_model }),
    build.ai_enrichment_model && t('context.trace.enrichmentModel', { model: build.ai_enrichment_model }),
  ].filter(Boolean);
  return (
    <Text component="details" size="sm">
      <summary style={{ cursor: 'pointer' }}>
        {t('context.history.build', {
          date: formatDateTime(build.built_at),
          classified: formatCount(build.classified),
          unclassified: formatCount(build.unclassified),
        })}{' '}
        <Badge size="xs" variant="light" color={build.changes_total ? 'blue' : 'gray'}>
          {build.changes_total
            ? t('context.history.changes', { count: build.changes_total })
            : t('context.history.noChanges')}
        </Badge>
      </summary>
      {trace.length > 0 && (
        <Text size="xs" c="dimmed" mt={4}>
          {trace.join(' · ')}
        </Text>
      )}
      {build.changes.length > 0 && (
        <Table.ScrollContainer minWidth={480} mt="xs">
          <Table>
            <Table.Tbody>
              {build.changes.map((change) => (
                <Table.Tr key={`${change.change}:${change.path}`}>
                  <Table.Td w={80}>
                    <Badge size="xs" variant="light">
                      {t(`context.history.kinds.${change.change}`)}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text ff="monospace" size="xs" style={{ wordBreak: 'break-all' }}>
                      {change.path}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs">
                      {change.change === 'added'
                        ? (change.domain ?? none)
                        : `${change.previous_domain ?? none} → ${change.domain ?? none}`}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {build.changes_total > build.changes.length && (
        <Text size="xs" c="dimmed" mt={4}>
          {t('context.history.shown', { shown: build.changes.length, total: build.changes_total })}
        </Text>
      )}
    </Text>
  );
}
