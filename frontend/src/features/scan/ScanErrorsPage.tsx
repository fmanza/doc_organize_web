import {
  Alert,
  Anchor,
  Badge,
  Center,
  Group,
  Loader,
  Pagination,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatCount, formatDateTime } from '../../components/format';
import { SCAN_ERRORS_PAGE_SIZE, useScanErrors } from './useScan';

/**
 * Documentos que no se pudieron convertir (sustituye a `scan_errors.html.j2`): de un run (`/runs/:runId/errors`) o del
 * último escaneo del proyecto (`/projects/:projectId/scan-errors`). Paginado en servidor; rutas relativas al origen.
 */
export function ScanErrorsPage() {
  const { t } = useTranslation();
  const params = useParams();
  const target = params.runId ? { runId: params.runId } : { projectId: Number(params.projectId) };
  const [page, setPage] = useState(1);
  const { data, isPending, isError, error } = useScanErrors(target, page);

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
  const pages = Math.max(1, Math.ceil(data.total / SCAN_ERRORS_PAGE_SIZE));
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
      {data.run && data.total === 0 && <Text>{t('scanErrors.empty')}</Text>}
      {data.total > 0 && (
        <>
          <Text size="sm">
            {t('scanErrors.total', { count: data.total, formatted: formatCount(data.total) })}
          </Text>
          <Table.ScrollContainer minWidth={640}>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('scanErrors.fields.path')}</Table.Th>
                  <Table.Th>{t('scanErrors.fields.message')}</Table.Th>
                  <Table.Th>{t('scanErrors.fields.retries')}</Table.Th>
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
          {pages > 1 && <Pagination total={pages} value={page} onChange={setPage} />}
        </>
      )}
    </Stack>
  );
}
