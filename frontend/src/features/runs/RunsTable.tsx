import { Anchor, Table, Text, VisuallyHidden } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { formatDateTime, formatDuration } from '../../components/format';
import { RunStatusBadge } from './RunStatusBadge';
import type { RunOut } from './useRuns';

interface RunsTableProps {
  runs: RunOut[];
  /** Muestra la columna de proyecto (historial global). */
  showProject?: boolean;
}

/** Historial agrupado por ejecución: una fila por run con enlace a su detalle. */
export function RunsTable({ runs, showProject = false }: RunsTableProps) {
  const { t } = useTranslation();
  return (
    <Table.ScrollContainer minWidth={showProject ? 820 : 680}>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('runs.fields.operation')}</Table.Th>
            {showProject && <Table.Th>{t('runs.fields.project')}</Table.Th>}
            <Table.Th>{t('runs.fields.status')}</Table.Th>
            <Table.Th>{t('runs.fields.createdAt')}</Table.Th>
            <Table.Th>{t('runs.fields.duration')}</Table.Th>
            <Table.Th>{t('runs.fields.createdBy')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {runs.map((run) => (
            <Table.Tr key={run.id}>
              <Table.Td>
                <Anchor component={Link} to={`/runs/${run.id}`}>
                  {t(`runs.operations.${run.operation}`)}
                  {run.params.dry_run === true && <> {t('runs.preview')}</>}
                  <VisuallyHidden> ({formatDateTime(run.created_at)})</VisuallyHidden>
                </Anchor>
              </Table.Td>
              {showProject && (
                <Table.Td>
                  {run.project_id !== null ? (
                    <Anchor component={Link} to={`/projects/${run.project_id}`}>
                      {run.project_name}
                    </Anchor>
                  ) : (
                    <Text c="dimmed">—</Text>
                  )}
                </Table.Td>
              )}
              <Table.Td>
                <RunStatusBadge status={run.status} />
              </Table.Td>
              <Table.Td>{formatDateTime(run.created_at)}</Table.Td>
              <Table.Td>{run.started_at ? formatDuration(run.started_at, run.finished_at) : '—'}</Table.Td>
              <Table.Td>{run.created_by_username ?? '—'}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
