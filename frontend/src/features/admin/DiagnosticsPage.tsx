import { Alert, Badge, Button, Card, Checkbox, Group, Stack, Table, Text, Title } from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '../../api/client';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';

const STATUS_COLOR: Record<string, string> = { ok: 'teal', warning: 'yellow', error: 'red' };

/**
 * Diagnóstico del entorno (W4, `check_environment` de doc_organize): Python, docling y sus modelos, extras, sitio de
 * prueba, GPU, LibreOffice, audio y vídeo y, si se pide, los modelos de IA. Sin claves ni rutas del servidor.
 */
export function DiagnosticsPage() {
  const { t } = useTranslation();
  const [checkAi, setCheckAi] = useState(false);
  const run = useMutation({
    mutationFn: async (withAi: boolean) =>
      unwrap(await api.POST('/api/v1/admin/diagnostics', { body: { check_ai: withAi } })),
  });
  const report = run.data;

  return (
    <Stack>
      <Title order={2}>{t('diagnostics.title')}</Title>
      <Text c="dimmed">{t('diagnostics.intro')}</Text>
      <Card withBorder>
        <Group justify="space-between" align="flex-end">
          <Checkbox
            label={t('diagnostics.checkAi')}
            description={t('diagnostics.checkAiHelp')}
            checked={checkAi}
            onChange={(event) => setCheckAi(event.currentTarget.checked)}
          />
          <Button loading={run.isPending} onClick={() => run.mutate(checkAi)}>
            {t('diagnostics.run')}
          </Button>
        </Group>
        {run.isPending && (
          <Text size="sm" c="dimmed" mt="xs" role="status">
            {t('diagnostics.running')}
          </Text>
        )}
      </Card>
      {run.isError && <ErrorAlert error={run.error} />}
      {report && (
        <Card withBorder component="section" aria-label={t('diagnostics.result')}>
          <Alert
            color={report.ok ? 'teal' : 'red'}
            mb="sm"
            title={t(report.ok ? 'diagnostics.ok' : 'diagnostics.failed')}
          >
            {t('diagnostics.checkedAt', { date: formatDateTime(report.checked_at) })}
          </Alert>
          <Table.ScrollContainer minWidth={560}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('diagnostics.check')}</Table.Th>
                  <Table.Th>{t('diagnostics.status')}</Table.Th>
                  <Table.Th>{t('diagnostics.detail')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {report.checks.map((check) => (
                  <Table.Tr key={check.name}>
                    <Table.Td>
                      <Text size="sm" ff="monospace">
                        {check.name}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge variant="light" color={STATUS_COLOR[check.status] ?? 'gray'}>
                        {t(`diagnostics.statuses.${check.status}`)}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{check.detail}</Text>
                      {check.remedy && (
                        <Text size="xs" c="dimmed">
                          {check.remedy}
                        </Text>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Card>
      )}
    </Stack>
  );
}
