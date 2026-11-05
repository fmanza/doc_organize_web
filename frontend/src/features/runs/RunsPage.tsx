import { Center, Group, Loader, Select, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { PageControls } from '../../components/Paging';
import { usePageState } from '../../components/usePageState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { RunsTable } from './RunsTable';
import { type Operation, RUNS_PAGE_SIZE, type RunStatus, useRuns } from './useRuns';

const STATUSES: RunStatus[] = ['queued', 'running', 'succeeded', 'failed', 'cancelled'];
const OPERATIONS: Operation[] = ['noop', 'history_clear', 'project_move', 'project_delete'];

/** Historial de ejecuciones de los proyectos visibles, agrupado por ejecución y con filtros. */
export function RunsPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [operation, setOperation] = useState<Operation | null>(null);
  const paging = usePageState(RUNS_PAGE_SIZE);
  const { page } = paging;
  const projectParam = Number(useSearchParams()[0].get('project_id'));
  const projectId = Number.isInteger(projectParam) && projectParam > 0 ? projectParam : undefined;
  const { data, isPending, isError, error } = useRuns(
    {
      ...(projectId ? { project_id: projectId } : {}),
      ...(status ? { status } : {}),
      ...(operation ? { operation } : {}),
    },
    page,
  );

  return (
    <Stack>
      <Title order={2}>{t('runs.title')}</Title>
      <Text c="dimmed">{t('runs.intro')}</Text>
      <Group>
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
        <Select
          label={t('runs.fields.operation')}
          placeholder={t('runs.all')}
          clearable
          data={OPERATIONS.map((value) => ({ value, label: t(`runs.operations.${value}`) }))}
          value={operation}
          onChange={(value) => {
            setOperation(value as Operation | null);
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
      {data && data.items.length > 0 && <RunsTable runs={data.items} showProject />}
      {data && <PageControls state={paging} total={data.total} label={t('paging.label')} fixedSize />}
    </Stack>
  );
}
