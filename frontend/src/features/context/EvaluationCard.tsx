import { Alert, Badge, Button, Card, Group, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { type GoldSource, pct, type Report } from './qualityReport';
import { type Quality, useQualityRun } from './useQuality';

function ReportTable({ report, label }: { report: Report; label: string }) {
  const { t } = useTranslation();
  return (
    <Stack gap="xs">
      <Text size="sm">
        {t('quality.matched', { matched: report.matched, documents: report.documents })}
        {(report.missing_total ?? report.missing_documents.length) > 0 &&
          ` ${t('quality.missing', { count: report.missing_total ?? report.missing_documents.length })}`}
      </Text>
      <Table.ScrollContainer minWidth={560}>
        <Table aria-label={label}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('quality.axis')}</Table.Th>
              <Table.Th>{t('quality.labelled')}</Table.Th>
              <Table.Th>{t('quality.accuracy')}</Table.Th>
              <Table.Th>{t('quality.coverage')}</Table.Th>
              <Table.Th>{t('quality.precision')}</Table.Th>
              <Table.Th>{t('quality.recall')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {Object.values(report.axes).map((axis) => (
              <Table.Tr key={axis.axis}>
                <Table.Td>{axis.axis}</Table.Td>
                <Table.Td>{axis.labelled}</Table.Td>
                <Table.Td>{pct(axis.accuracy)}</Table.Td>
                <Table.Td>{pct(axis.coverage)}</Table.Td>
                <Table.Td>{pct(axis.precision)}</Table.Td>
                <Table.Td>{pct(axis.recall)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {Object.values(report.axes).map((axis) => (
        <Text component="details" size="xs" key={`${axis.axis}-detail`}>
          <summary style={{ cursor: 'pointer' }}>{t('quality.detail', { axis: axis.axis })}</summary>
          <Stack gap={2} mt={4}>
            <Group gap={4}>
              {Object.entries(axis.accuracy_by_classified_by).map(([who, value]) => (
                <Badge key={who} variant="light" tt="none">
                  {t(`quality.by.${who}`, { defaultValue: who })}: {pct(value)} (
                  {axis.labelled_by_classified_by[who] ?? 0})
                </Badge>
              ))}
            </Group>
            {axis.confusions.map((confusion) => (
              <Text size="xs" key={`${confusion.label}>${confusion.assigned}`}>
                {t('quality.confusion', confusion)}
              </Text>
            ))}
          </Stack>
        </Text>
      ))}
    </Stack>
  );
}

export function EvaluationCard({
  projectId,
  quality,
  source,
  ready,
}: {
  projectId: number;
  quality: Quality;
  source: GoldSource;
  ready: boolean;
}) {
  const { t } = useTranslation();
  const run = useQualityRun(projectId);
  const last = quality.evaluation;
  const report = (last?.result as { report?: Report } | undefined)?.report;
  return (
    <Card withBorder component="section" aria-label={t('quality.evaluationTitle')}>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {t('quality.evaluationTitle')}
        </Title>
        <Button
          disabled={!ready}
          loading={run.running}
          onClick={() => run.start({ operation: 'context_evaluate', gold: source })}
        >
          {t('quality.evaluate')}
        </Button>
      </Group>
      {run.error && <ErrorAlert error={run.error} />}
      {run.failure && (
        <Alert color="red" role="alert">
          {run.failure}
        </Alert>
      )}
      {report && last ? (
        <>
          <Text size="xs" c="dimmed" mb="xs">
            {t('quality.lastRun', { date: last.finished_at ? formatDateTime(last.finished_at) : '—' })}
          </Text>
          <ReportTable report={report} label={t('quality.evaluationTitle')} />
        </>
      ) : (
        <Text size="sm" c="dimmed">
          {t('quality.noEvaluation')}
        </Text>
      )}
    </Card>
  );
}
