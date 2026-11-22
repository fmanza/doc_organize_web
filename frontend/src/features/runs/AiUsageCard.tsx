import { Card, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import type { components } from '../../api/schema';
import { formatCount } from '../../components/format';

type Row = components['schemas']['AiUsageRowOut'];

/**
 * Consumo de IA de la ejecución (2.1): por tarea, el modelo, los documentos enviados, los resueltos con la caché y los
 * tokens («≈» si son estimados). Sin coste: el proxy no lo da por llamada (el gasto está en IA › Uso).
 */
export function AiUsageCard({ rows }: { rows: Row[] }) {
  const { t } = useTranslation();
  const estimated = rows.some((row) => row.tokens_estimated);
  const tokens = (value: number, row: Row) => `${row.tokens_estimated ? '≈ ' : ''}${formatCount(value)}`;
  return (
    <Card withBorder component="section" aria-label={t('runs.aiUsage.title')}>
      <Title order={3} size="h4" mb="sm">
        {t('runs.aiUsage.title')}
      </Title>
      <Table.ScrollContainer minWidth={560}>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('runs.aiUsage.task')}</Table.Th>
              <Table.Th>{t('runs.aiUsage.model')}</Table.Th>
              <Table.Th>{t('runs.aiUsage.calls')}</Table.Th>
              <Table.Th>{t('runs.aiUsage.cached')}</Table.Th>
              <Table.Th>{t('runs.aiUsage.prompt')}</Table.Th>
              <Table.Th>{t('runs.aiUsage.completion')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((row) => (
              <Table.Tr key={row.task}>
                <Table.Td>{t(`ai.tasks.${row.task}`, { defaultValue: row.task })}</Table.Td>
                <Table.Td>
                  <Text size="sm" ff="monospace">
                    {row.model ?? '—'}
                  </Text>
                </Table.Td>
                <Table.Td>{formatCount(row.calls)}</Table.Td>
                <Table.Td>{formatCount(row.cached)}</Table.Td>
                <Table.Td>{tokens(row.prompt_tokens, row)}</Table.Td>
                <Table.Td>{tokens(row.completion_tokens, row)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {estimated && (
        <Text size="xs" c="dimmed" mt={4}>
          {t('runs.aiUsage.estimated')}
        </Text>
      )}
    </Card>
  );
}
