import {
  Alert,
  Anchor,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Progress,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { TokensByDayChart } from './AiUsageCharts';
import { type AiUsage, type AiUsagePeriod, type AiUsageSource, useAiUsage, useRefreshAiUsage } from './useAi';

const money = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 4,
});
const number = new Intl.NumberFormat('es-ES');
const PERIODS: readonly AiUsagePeriod[] = ['7d', '30d', 'month', 'all'];

type Local = NonNullable<AiUsage['local']>;
type Totals = Local['totals'];
type Group = Local['by_task'][number];

/**
 * Uso de IA (2.1): el gasto y el presupuesto de la clave de LiteLLM, y el consumo que registra la web en cada
 * ejecución (documentos, caché y tokens) por periodo, día local, tarea, modelo, proyecto y ejecución. El proxy no da
 * el coste por llamada, así que el coste solo es el de la clave.
 */
export function AiUsagePage() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<AiUsagePeriod>('30d');
  const usage = useAiUsage(period);
  const refresh = useRefreshAiUsage(period);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('ai.usage.title')}</Title>
        <Button variant="default" onClick={() => refresh.mutate()} loading={refresh.isPending}>
          {t('ai.usage.refresh')}
        </Button>
      </Group>
      <Text c="dimmed">{t('ai.usage.intro')}</Text>
      <Text size="sm">
        {t('ai.usage.limits')}{' '}
        <Anchor component={Link} to="/admin/ai/parameters">
          {t('ai.usage.parameters')}
        </Anchor>
      </Text>
      <SegmentedControl
        w="fit-content"
        value={period}
        onChange={(value) => setPeriod(value as AiUsagePeriod)}
        aria-label={t('ai.usage.local.period')}
        data={PERIODS.map((value) => ({ value, label: t(`ai.usage.local.periods.${value}`) }))}
      />
      {refresh.isError && <ErrorAlert error={refresh.error} />}
      {usage.isPending ? (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      ) : usage.isError ? (
        <ErrorAlert error={usage.error} />
      ) : (
        <>
          {usage.data.local && <Indicators totals={usage.data.local.totals} />}
          {usage.data.sources.map((source) => (
            <KeyCard key={source.source} source={source} />
          ))}
          {usage.data.local && <LocalUsage local={usage.data.local} />}
        </>
      )}
    </Stack>
  );
}

const tokens = (value: number, estimated: boolean) => `${estimated ? '≈ ' : ''}${number.format(value)}`;

/** Fila de indicadores del periodo. */
function Indicators({ totals }: { totals: Totals }) {
  const { t } = useTranslation();
  const asked = totals.calls + totals.cached;
  const saved = asked > 0 ? Math.round((totals.cached / asked) * 100) : 0;
  const tiles: [string, string, string | null][] = [
    ['runs', number.format(totals.runs), null],
    ['calls', number.format(totals.calls), null],
    [
      'cached',
      number.format(totals.cached),
      asked > 0 ? t('ai.usage.local.savedShare', { percent: saved }) : null,
    ],
    ['prompt', tokens(totals.prompt_tokens, totals.tokens_estimated), null],
    ['completion', tokens(totals.completion_tokens, totals.tokens_estimated), null],
  ];
  return (
    <SimpleGrid cols={{ base: 2, sm: 5 }} spacing="xs" component="dl" m={0}>
      {tiles.map(([key, value, hint]) => (
        <Card key={key} withBorder padding="sm">
          <Text size="xs" c="dimmed" component="dt">
            {t(`ai.usage.local.kpi.${key}`)}
          </Text>
          <Text component="dd" m={0} fz="xl" fw={600}>
            {value}
          </Text>
          {hint && (
            <Text size="xs" c="dimmed">
              {hint}
            </Text>
          )}
        </Card>
      ))}
    </SimpleGrid>
  );
}

/** Gasto acumulado y presupuesto de la clave de LiteLLM (`/key/info`). */
function KeyCard({ source }: { source: AiUsageSource }) {
  const { t } = useTranslation();
  const budget = source.budget;
  const spend = budget?.spend ?? source.total_cost_usd;
  const used = budget?.max_budget ? Math.min(((budget.spend ?? 0) / budget.max_budget) * 100, 100) : null;
  return (
    <Card withBorder component="section" aria-label={t('ai.usage.key.title')}>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {t('ai.usage.key.title')}
        </Title>
        {source.fetched_at && (
          <Text size="xs" c="dimmed">
            {t(source.cached ? 'ai.usage.cachedAt' : 'ai.usage.fetchedAt', {
              date: formatDateTime(source.fetched_at),
            })}
          </Text>
        )}
      </Group>
      {!source.configured ? (
        <Text c="dimmed" role="status">
          {t('ai.usage.notConfigured')}{' '}
          <Anchor component={Link} to="/admin/ai/settings">
            {t('ai.usage.configure')}
          </Anchor>
        </Text>
      ) : source.error ? (
        <Alert color="red" role="alert" title={t('ai.usage.errorTitle')}>
          {t(`ai.errors.${source.error}`)}
        </Alert>
      ) : (
        <Stack gap="xs">
          <Group gap="xl">
            <Stat
              label={t('ai.usage.key.spend')}
              value={spend === null || spend === undefined ? '—' : money.format(spend)}
            />
            {budget?.max_budget != null && (
              <Stat label={t('ai.usage.key.budget')} value={money.format(budget.max_budget)} />
            )}
            {budget?.remaining != null && (
              <Stat label={t('ai.usage.key.remaining')} value={money.format(budget.remaining)} />
            )}
            {budget?.budget_reset_at && (
              <Stat label={t('ai.usage.key.reset')} value={formatDateTime(budget.budget_reset_at)} />
            )}
          </Group>
          {used !== null && (
            <Progress value={used} aria-label={t('ai.usage.key.used', { percent: Math.round(used) })} />
          )}
          <Text size="xs" c="dimmed">
            {t(budget?.max_budget != null ? 'ai.usage.key.help' : 'ai.usage.key.noBudget')}
          </Text>
        </Stack>
      )}
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={500}>{value}</Text>
    </div>
  );
}

/** Consumo registrado por la web: tokens por día y tablas por tarea, modelo, proyecto y ejecución. */
function LocalUsage({ local }: { local: Local }) {
  const { t } = useTranslation();
  if (local.totals.runs === 0) {
    return (
      <Text c="dimmed" role="status">
        {t('ai.usage.local.empty')}
      </Text>
    );
  }
  return (
    <>
      <Card withBorder component="section" aria-label={t('ai.usage.local.byDay')}>
        <Title order={3} size="h4" mb="xs">
          {t('ai.usage.local.byDay')}
        </Title>
        <TokensByDayChart
          days={local.by_day.map((day) => ({
            day: day.day,
            prompt_tokens: day.prompt_tokens,
            completion_tokens: day.completion_tokens,
          }))}
          timezone={local.timezone}
        />
      </Card>
      <GroupTable
        title={t('ai.usage.local.byTask')}
        groups={local.by_task}
        name={(group) => t(`ai.tasks.${group.key}`, { defaultValue: group.key })}
      />
      <GroupTable
        title={t('ai.usage.local.byModel')}
        groups={local.by_model}
        name={(group) => group.key || t('ai.usage.local.unknownModel')}
      />
      <GroupTable
        title={t('ai.usage.local.byProject')}
        groups={local.by_project}
        name={(group) =>
          group.project_id !== null && group.project_id !== undefined ? (
            <Anchor component={Link} to={`/projects/${group.project_id}`}>
              {group.label ?? group.key}
            </Anchor>
          ) : (
            (group.label ?? t('ai.usage.local.deletedProject'))
          )
        }
      />
      <TopRuns runs={local.top_runs} />
    </>
  );
}

function Counts({ totals }: { totals: Totals }) {
  return (
    <>
      <Table.Td>{number.format(totals.runs)}</Table.Td>
      <Table.Td>{number.format(totals.calls)}</Table.Td>
      <Table.Td>{number.format(totals.cached)}</Table.Td>
      <Table.Td>{tokens(totals.prompt_tokens, totals.tokens_estimated)}</Table.Td>
      <Table.Td>{tokens(totals.completion_tokens, totals.tokens_estimated)}</Table.Td>
    </>
  );
}

function CountHeaders() {
  const { t } = useTranslation();
  return (
    <>
      <Table.Th>{t('ai.usage.local.kpi.runs')}</Table.Th>
      <Table.Th>{t('ai.usage.local.kpi.calls')}</Table.Th>
      <Table.Th>{t('ai.usage.local.kpi.cached')}</Table.Th>
      <Table.Th>{t('ai.usage.local.kpi.prompt')}</Table.Th>
      <Table.Th>{t('ai.usage.local.kpi.completion')}</Table.Th>
    </>
  );
}

function GroupTable({
  title,
  groups,
  name,
}: {
  title: string;
  groups: Group[];
  name: (group: Group) => React.ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <Card withBorder component="section" aria-label={title}>
      <Title order={3} size="h4" mb="xs">
        {title}
      </Title>
      <Table.ScrollContainer minWidth={560}>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('ai.usage.local.name')}</Table.Th>
              <CountHeaders />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {groups.map((group) => (
              <Table.Tr key={group.key}>
                <Table.Td>{name(group)}</Table.Td>
                <Counts totals={group} />
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Card>
  );
}

function TopRuns({ runs }: { runs: Local['top_runs'] }) {
  const { t } = useTranslation();
  if (runs.length === 0) {
    return null;
  }
  return (
    <Card withBorder component="section" aria-label={t('ai.usage.local.topRuns')}>
      <Title order={3} size="h4" mb="xs">
        {t('ai.usage.local.topRuns')}
      </Title>
      <Table.ScrollContainer minWidth={640}>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('ai.usage.local.run')}</Table.Th>
              <Table.Th>{t('ai.usage.local.project')}</Table.Th>
              <CountHeaders />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {runs.map((run, index) => (
              <Table.Tr key={run.run_id ?? index}>
                <Table.Td>
                  {run.run_id ? (
                    <Anchor component={Link} to={`/runs/${run.run_id}`}>
                      {t(`runs.operations.${run.operation}`, { defaultValue: run.operation })}
                    </Anchor>
                  ) : (
                    t(`runs.operations.${run.operation}`, { defaultValue: run.operation })
                  )}
                  <Text size="xs" c="dimmed">
                    {formatDateTime(run.created_at)}
                  </Text>
                </Table.Td>
                <Table.Td>{run.project_name ?? t('ai.usage.local.deletedProject')}</Table.Td>
                <Counts totals={run} />
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Card>
  );
}
