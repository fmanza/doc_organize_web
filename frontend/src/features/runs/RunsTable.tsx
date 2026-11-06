import { Anchor, Table, Text, VisuallyHidden } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { formatDateTime, formatDuration } from '../../components/format';
import { SortableTh } from '../../components/listing';
import { type ListState } from '../../components/useListState';
import { RunStatusBadge } from './RunStatusBadge';
import type { RunOut, RunSort } from './useRuns';

interface RunsTableProps {
  runs: RunOut[];
  /** Muestra la columna de proyecto (historial global). */
  showProject?: boolean;
  /** Con él, las columnas se ordenan (historial completo, web 1.2.0); sin él, cabeceras fijas (últimos runs). */
  list?: Pick<ListState<RunSort>, 'sort' | 'order' | 'toggleSort'>;
}

/** Historial agrupado por ejecución: una fila por run con enlace a su detalle. */
export function RunsTable({ runs, showProject = false, list }: RunsTableProps) {
  const { t } = useTranslation();
  const head = (key: RunSort, label: string) =>
    list ? (
      <SortableTh state={list} sortKey={key}>
        {label}
      </SortableTh>
    ) : (
      <Table.Th>{label}</Table.Th>
    );
  return (
    <Table.ScrollContainer minWidth={showProject ? 820 : 680}>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            {head('operation', t('runs.fields.operation'))}
            {showProject && head('project', t('runs.fields.project'))}
            {head('status', t('runs.fields.status'))}
            {head('created_at', t('runs.fields.createdAt'))}
            {head('duration', t('runs.fields.duration'))}
            {head('created_by', t('runs.fields.createdBy'))}
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
