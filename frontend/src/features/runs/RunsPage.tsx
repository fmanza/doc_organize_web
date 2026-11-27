import { Center, Group, Loader, Select, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { PageControls } from '../../components/Paging';
import { SearchBox } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { RunsTable } from './RunsTable';
import { type Operation, type RunSort, type RunStatus, useRuns } from './useRuns';

const STATUSES: RunStatus[] = ['queued', 'running', 'succeeded', 'failed', 'cancelled'];
/**
 * Todas las operaciones, para el filtro. Es un registro y no una lista para que `tsc` falle si el backend añade una
 * operación (`Operation` sale del contrato generado) y aquí no se ofrece: antes el filtro solo tenía cuatro.
 */
const OPERATION_FILTER: Record<Operation, true> = {
  noop: true,
  history_clear: true,
  project_move: true,
  project_delete: true,
  scan: true,
  export_zip: true,
  export_xlsx: true,
  export_site: true,
  export_ai_bundle: true,
  search_index: true,
  dedup_preview: true,
  dedup_apply: true,
  context_build: true,
  context_delete: true,
  taxonomy_draft: true,
  context_evaluate: true,
  context_dry_run: true,
  taxonomy_agent: true,
  taxonomy_check: true,
  context_review_agent: true,
  context_audit: true,
};
const OPERATIONS = Object.keys(OPERATION_FILTER) as Operation[];
const RUN_SORT: readonly RunSort[] = [
  'operation',
  'project',
  'status',
  'created_at',
  'duration',
  'created_by',
];

/** Historial de ejecuciones de los proyectos visibles, agrupado por ejecución y con filtros. */
export function RunsPage() {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [operation, setOperation] = useState<Operation | null>(null);
  const list = useListState(RUN_SORT);
  const { paging } = list;
  const projectParam = Number(useSearchParams()[0].get('project_id'));
  const projectId = Number.isInteger(projectParam) && projectParam > 0 ? projectParam : undefined;
  const { data, isPending, isError, error } = useRuns(
    {
      ...(projectId ? { project_id: projectId } : {}),
      ...(status ? { status } : {}),
      ...(operation ? { operation } : {}),
    },
    list.query,
  );

  return (
    <Stack>
      <Title order={2}>{t('runs.title')}</Title>
      <Text c="dimmed">{t('runs.intro')}</Text>
      <Group align="flex-end">
        <SearchBox value={list.q} onChange={list.setQ} label={t('runs.search')} />
        <Select
          label={t('runs.fields.operation')}
          placeholder={t('runs.all')}
          clearable
          searchable
          w={280}
          data={OPERATIONS.map((value) => ({ value, label: t(`runs.operations.${value}`) })).sort((a, b) =>
            a.label.localeCompare(b.label, i18n.language),
          )}
          value={operation}
          onChange={(value) => {
            setOperation(value as Operation | null);
            paging.setPage(1, true);
          }}
        />
        <Select
          label={t('runs.fields.status')}
          placeholder={t('runs.all')}
          clearable
          data={STATUSES.map((value) => ({ value, label: t(`runs.status.${value}`) }))}
          value={status}
          onChange={(value) => {
            setStatus(value as RunStatus | null);
            paging.setPage(1, true);
          }}
        />
      </Group>
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && data.items.length === 0 && <Text c="dimmed">{t('runs.empty')}</Text>}
      {data && data.items.length > 0 && <RunsTable runs={data.items} showProject list={list} />}
      {data && <PageControls state={paging} total={data.total} label={t('paging.label')} />}
    </Stack>
  );
}
