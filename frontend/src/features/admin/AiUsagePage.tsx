import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { SearchBox, SortableTh } from '../../components/listing';
import { useClientTable } from '../../components/useListState';
import { formatDateTime } from '../../components/format';
import { type AiUsageSource, useAiUsage, useRefreshAiUsage } from './useAi';

const money = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 4,
});
const quantity = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 });

/** Panel de uso y coste de IA (LiteLLM y GitHub Copilot), con la caché corta del servidor. */
export function AiUsagePage() {
  const { t } = useTranslation();
  const usage = useAiUsage();
  const refresh = useRefreshAiUsage();

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('ai.usage.title')}</Title>
        <Button variant="default" onClick={() => refresh.mutate()} loading={refresh.isPending}>
          {t('ai.usage.refresh')}
        </Button>
      </Group>
      <Text c="dimmed">{t('ai.usage.intro')}</Text>
      {refresh.isError && <ErrorAlert error={refresh.error} />}
      {usage.isPending ? (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      ) : usage.isError ? (
        <ErrorAlert error={usage.error} />
      ) : (
        usage.data.map((source) => <SourceCard key={source.source} source={source} />)
      )}
    </Stack>
  );
}

type UsageItem = NonNullable<ReturnType<typeof useAiUsage>['data']>[number]['items'][number];

const USAGE_COLUMNS = {
  date: (item: UsageItem) => item.date,
  product: (item: UsageItem) => item.product,
  quantity: (item: UsageItem) => item.quantity,
  cost: (item: UsageItem) => item.cost_usd,
};

function SourceCard({ source }: { source: AiUsageSource }) {
  const { t } = useTranslation();
  const title = t(`ai.usage.sources.${source.source}`);
  // Una tabla por fuente: cada una con su página y su orden en la URL (`?github-page=2`).
  const table = useClientTable(
    source.items,
    USAGE_COLUMNS,
    (item) => `${item.date} ${item.product} ${item.sku ?? ''}`,
    `${source.source}-`,
  );
  return (
    <Card withBorder component="section" aria-label={title}>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {title}
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
          <Anchor component={Link} to="/admin/ai-settings">
            {t('ai.usage.configure')}
          </Anchor>
        </Text>
      ) : source.error ? (
        <Alert color="red" role="alert" title={t('ai.usage.errorTitle')}>
          {t(`ai.errors.${source.error}`)}
        </Alert>
      ) : (
        <Stack gap="xs">
          <Group gap="lg">
            <Text size="sm">
              {t('ai.usage.period', { start: source.period_start, end: source.period_end })}
            </Text>
            {source.total_cost_usd !== null && (
              <Badge variant="light" size="lg">
                {t('ai.usage.total', { cost: money.format(source.total_cost_usd) })}
              </Badge>
            )}
          </Group>
          {source.items.length === 0 ? (
            <Text c="dimmed" role="status">
              {t('ai.usage.empty')}
            </Text>
          ) : (
            <>
              <SearchBox
                value={table.q}
                onChange={table.setQ}
                label={t('ai.usage.search', { source: title })}
              />
              <Table.ScrollContainer minWidth={560}>
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <SortableTh state={table} sortKey="date">
                        {t('ai.usage.date')}
                      </SortableTh>
                      <SortableTh state={table} sortKey="product">
                        {t('ai.usage.product')}
                      </SortableTh>
                      <SortableTh state={table} sortKey="quantity">
                        {t('ai.usage.quantity')}
                      </SortableTh>
                      <SortableTh state={table} sortKey="cost">
                        {t('ai.usage.cost')}
                      </SortableTh>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {table.pageRows.map((item, index) => (
                      <Table.Tr key={`${item.date}-${item.product}-${item.sku ?? ''}-${index}`}>
                        <Table.Td>{item.date}</Table.Td>
                        <Table.Td>
                          {item.product}
                          {item.sku && (
                            <Text size="xs" c="dimmed">
                              {item.sku}
                            </Text>
                          )}
                        </Table.Td>
                        <Table.Td>
                          {quantity.format(item.quantity)} {item.unit_type}
                        </Table.Td>
                        <Table.Td>{item.cost_usd === null ? '—' : money.format(item.cost_usd)}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
              <PageControls state={table.paging} total={table.total} label={t('paging.label')} />
            </>
          )}
        </Stack>
      )}
    </Card>
  );
}
