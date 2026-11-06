import { Alert, Anchor, Badge, Center, Group, Loader, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { formatCount, formatDateTime } from '../../components/format';
import { SearchBox, SortableTh } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { type ScanErrorSort, useScanErrors } from './useScan';

const SCAN_ERROR_SORT: readonly ScanErrorSort[] = ['path', 'message', 'retry_count'];

/**
 * Documentos que no se pudieron convertir (sustituye a `scan_errors.html.j2`): de un run (`/runs/:runId/errors`) o del
 * último escaneo del proyecto (`/projects/:projectId/scan-errors`). Paginado en servidor; rutas relativas al origen.
 */
export function ScanErrorsPage() {
  const { t } = useTranslation();
  const params = useParams();
  const target = params.runId ? { runId: params.runId } : { projectId: Number(params.projectId) };
  const list = useListState(SCAN_ERROR_SORT);
  const { data, isPending, isError, error } = useScanErrors(target, list.query);

  if (isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (isError) {
    return <ErrorAlert error={error} />;
  }
  return (
    <Stack>
      {'projectId' in target ? (
        <Anchor component={Link} to={`/projects/${target.projectId}/scan`} size="sm">
          {t('scanErrors.backToScan')}
        </Anchor>
      ) : (
        <Anchor component={Link} to={`/runs/${target.runId}`} size="sm">
          {t('scanErrors.backToRun')}
        </Anchor>
      )}
      <Title order={2}>{t('scanErrors.title')}</Title>
      {data.run ? (
        <Text c="dimmed">
          {t('scanErrors.ofRun', { date: formatDateTime(data.run.finished_at ?? data.run.created_at) })}{' '}
          <Anchor component={Link} to={`/runs/${data.run.id}`}>
            {t('scanErrors.openRun')}
          </Anchor>
        </Text>
      ) : (
        <Alert color="gray">{t('scanErrors.noScan')}</Alert>
      )}
      {data.run && (data.total > 0 || list.q) && (
        <SearchBox value={list.q} onChange={list.setQ} label={t('scanErrors.search')} />
      )}
      {data.run && data.total === 0 && <Text>{t(list.q ? 'listing.empty' : 'scanErrors.empty')}</Text>}
      {data.total > 0 && (
        <>
          <Text size="sm">
            {t('scanErrors.total', { count: data.total, formatted: formatCount(data.total) })}
          </Text>
          <Table.ScrollContainer minWidth={640}>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <SortableTh state={list} sortKey="path">
                    {t('scanErrors.fields.path')}
                  </SortableTh>
                  <SortableTh state={list} sortKey="message">
                    {t('scanErrors.fields.message')}
                  </SortableTh>
                  <SortableTh state={list} sortKey="retry_count">
                    {t('scanErrors.fields.retries')}
                  </SortableTh>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.items.map((item) => (
                  <Table.Tr key={item.id}>
                    <Table.Td>
                      <Text ff="monospace" size="sm" style={{ wordBreak: 'break-all' }}>
                        {item.path}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{item.message}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs" wrap="nowrap">
                        <Text size="sm">{item.retry_count}</Text>
                        {item.capped && (
                          <Badge color="orange" variant="light">
                            {t('scanErrors.capped')}
                          </Badge>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <PageControls state={list.paging} total={data.total} label={t('paging.label')} />
        </>
      )}
    </Stack>
  );
}
