import { Alert, Badge, Button, Card, Group, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { type Quality, useQualityRun } from './useQuality';

interface AuditReport {
  documents: number;
  unclassified: number;
  axes: {
    axis: string;
    documents: number;
    with_value: number;
    value_counts: Record<string, number>;
    low_confidence: number;
    unverified_evidence: number;
  }[];
  findings: { kind: string; axis: string | null; values: string[]; count: number; message: string }[];
}

/** Informe del auditor (W7, `audit_taxonomy`): estadísticas por eje y qué revisar del catálogo, sin IA. */
export function AuditCard({ projectId, quality }: { projectId: number; quality: Quality }) {
  const { t } = useTranslation();
  const run = useQualityRun(projectId);
  const last = quality.audit;
  const report = (last?.result as { audit?: AuditReport } | undefined)?.audit;
  return (
    <Card withBorder component="section" aria-label={t('quality.audit.title')}>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {t('quality.audit.title')}
        </Title>
        <Button
          variant="default"
          loading={run.running}
          onClick={() => run.start({ operation: 'context_audit' })}
        >
          {t('quality.audit.start')}
        </Button>
      </Group>
      <Text size="sm" c="dimmed" mb="xs">
        {t('quality.audit.intro')}
      </Text>
      {run.error && <ErrorAlert error={run.error} />}
      {run.failure && (
        <Alert color="red" role="alert">
          {run.failure}
        </Alert>
      )}
      {!report ? (
        <Text size="sm" c="dimmed">
          {t('quality.audit.none')}
        </Text>
      ) : (
        <Stack gap="xs">
          <Text size="xs" c="dimmed">
            {t('quality.lastRun', { date: last?.finished_at ? formatDateTime(last.finished_at) : '—' })} ·{' '}
            {t('quality.audit.documents', { documents: report.documents, unclassified: report.unclassified })}
          </Text>
          <Table.ScrollContainer minWidth={560}>
            <Table aria-label={t('quality.audit.title')}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('quality.axis')}</Table.Th>
                  <Table.Th>{t('quality.audit.withValue')}</Table.Th>
                  <Table.Th>{t('quality.audit.values')}</Table.Th>
                  <Table.Th>{t('quality.audit.lowConfidence')}</Table.Th>
                  <Table.Th>{t('quality.audit.unverified')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {report.axes.map((axis) => (
                  <Table.Tr key={axis.axis}>
                    <Table.Td>{axis.axis}</Table.Td>
                    <Table.Td>
                      {axis.with_value} / {axis.documents}
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">
                        {Object.entries(axis.value_counts)
                          .map(([slug, count]) => `${slug} (${count})`)
                          .join(', ') || '—'}
                      </Text>
                    </Table.Td>
                    <Table.Td>{axis.low_confidence}</Table.Td>
                    <Table.Td>{axis.unverified_evidence}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <Text size="sm" fw={500}>
            {t('quality.audit.findings')}
          </Text>
          {report.findings.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t('quality.audit.noFindings')}
            </Text>
          ) : (
            <Stack gap={2}>
              {report.findings.map((finding, index) => (
                <Text key={`${finding.kind}:${finding.axis ?? ''}:${index}`} size="sm">
                  <Badge size="xs" variant="light" mr={6}>
                    {finding.axis ?? '—'}
                  </Badge>
                  {finding.message}
                </Text>
              ))}
            </Stack>
          )}
        </Stack>
      )}
    </Card>
  );
}
