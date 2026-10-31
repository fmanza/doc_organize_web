import { Alert, Badge, Card, Group, Loader, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { useHealth } from './useHealth';

export function HomePage() {
  const { t } = useTranslation();
  const { data, isPending, isError } = useHealth();

  return (
    <Stack maw={720}>
      <Title order={2}>{t('home.title')}</Title>
      <Text c="dimmed">{t('home.intro')}</Text>
      <Card withBorder aria-live="polite">
        {isPending && (
          <Group>
            <Loader size="sm" />
            <Text>{t('health.loading')}</Text>
          </Group>
        )}
        {isError && (
          <Alert color="red" title={t('health.unreachable')}>
            {t('health.unreachableBody')}
          </Alert>
        )}
        {data && (
          <Stack gap="sm">
            <Group>
              <Badge color={data.status === 'ok' ? 'green' : 'orange'}>
                {data.status === 'ok' ? t('health.ok') : t('health.degraded')}
              </Badge>
            </Group>
            <Table>
              <Table.Tbody>
                <Table.Tr>
                  <Table.Th>{t('health.appVersion')}</Table.Th>
                  <Table.Td>{data.version}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Th>{t('health.libVersion')}</Table.Th>
                  <Table.Td>{data.doc_organize_version ?? t('health.notInstalled')}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Th>{t('health.database')}</Table.Th>
                  <Table.Td>
                    {data.database === 'ok' ? t('health.databaseOk') : t('health.databaseError')}
                  </Table.Td>
                </Table.Tr>
              </Table.Tbody>
            </Table>
          </Stack>
        )}
      </Card>
    </Stack>
  );
}
