import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  FileInput,
  Group,
  Loader,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { canDo, useProject } from '../projects/useProjects';
import { useTemplates } from './useContext';
import { ContextNav } from './ContextNav';
import { GOLD_DEFAULTS, type Quality, useQuality, useQualityRun, useUploadGold } from './useQuality';

type GoldSource = 'xlsx' | 'decisions';

interface AxisReport {
  axis: string;
  labelled: number;
  accuracy: number | null;
  coverage: number | null;
  precision: number | null;
  recall: number | null;
  accuracy_by_classified_by: Record<string, number>;
  labelled_by_classified_by: Record<string, number>;
  confusions: { label: string; assigned: string; count: number }[];
}
interface Report {
  axes: Record<string, AxisReport>;
  documents: number;
  matched: number;
  missing_documents: string[];
  missing_total?: number;
}

const pct = (value: number | null | undefined) =>
  typeof value === 'number' ? `${Math.round(value * 100)} %` : '—';

/**
 * Calidad de la clasificación (W5, doc_organize 2.0 G3): métricas por eje contra una referencia (Excel subido o
 * decisiones del proyecto) y «Comparar cambios» con una clasificación de prueba que no guarda nada.
 */
export function QualityPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const quality = useQuality(projectId);
  const [source, setSource] = useState<GoldSource>('xlsx');

  if (project.isError || quality.isError) {
    return <ErrorAlert error={project.error ?? quality.error} />;
  }
  if (!project.data || !quality.data) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  const editable = canDo(project.data, 'editor');
  const data = quality.data;
  const ready = source === 'decisions' ? data.decisions_available : Boolean(data.gold);

  return (
    <Stack>
      <ContextNav projectId={projectId} active="calidad" />
      <Title order={3}>{t('quality.title')}</Title>
      <Text c="dimmed">{t('quality.intro')}</Text>
      <GoldCard projectId={projectId} quality={data} editable={editable} />
      <Card withBorder>
        <SegmentedControl
          value={source}
          onChange={(value) => setSource(value as GoldSource)}
          aria-label={t('quality.source')}
          data={[
            { value: 'xlsx', label: t('quality.sources.xlsx') },
            { value: 'decisions', label: t('quality.sources.decisions') },
          ]}
        />
        {!ready && (
          <Text size="sm" c="dimmed" mt="xs">
            {t(source === 'decisions' ? 'quality.noDecisions' : 'quality.noGold')}
          </Text>
        )}
      </Card>
      <EvaluationCard projectId={projectId} quality={data} source={source} ready={ready && editable} />
      <CompareCard projectId={projectId} quality={data} source={source} ready={ready && editable} />
      <AuditCard projectId={projectId} quality={data} />
    </Stack>
  );
}

function GoldCard({
  projectId,
  quality,
  editable,
}: {
  projectId: number;
  quality: Quality;
  editable: boolean;
}) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [sheet, setSheet] = useState<string>(GOLD_DEFAULTS.sheet);
  const [documentColumn, setDocumentColumn] = useState<string>(GOLD_DEFAULTS.documentColumn);
  const [columns, setColumns] = useState<string>(GOLD_DEFAULTS.columns);
  const upload = useUploadGold(projectId);
  const gold = quality.gold;
  return (
    <Card withBorder component="section" aria-label={t('quality.goldTitle')}>
      <Title order={3} size="h4" mb="xs">
        {t('quality.goldTitle')}
      </Title>
      <Text size="sm" c="dimmed" mb="xs">
        {t('quality.goldIntro')}
      </Text>
      {gold ? (
        <Text size="sm" mb="xs">
          {t('quality.goldInfo', {
            file: gold.filename,
            labels: gold.labels,
            axes: gold.axes.join(', '),
            date: formatDateTime(gold.uploaded_at),
            author: gold.uploaded_by ?? '—',
          })}
        </Text>
      ) : (
        <Text size="sm" c="dimmed" mb="xs">
          {t('quality.noGold')}
        </Text>
      )}
      {editable && (
        <Stack gap="xs">
          <FileInput label={t('quality.file')} accept=".xlsx" value={file} onChange={setFile} clearable />
          <Group grow>
            <TextInput
              label={t('quality.sheet')}
              value={sheet}
              onChange={(e) => setSheet(e.currentTarget.value)}
            />
            <TextInput
              label={t('quality.documentColumn')}
              value={documentColumn}
              onChange={(e) => setDocumentColumn(e.currentTarget.value)}
            />
          </Group>
          <TextInput
            label={t('quality.columns')}
            description={t('quality.columnsHelp')}
            value={columns}
            onChange={(e) => setColumns(e.currentTarget.value)}
          />
          {upload.isError && <ErrorAlert error={upload.error} />}
          <Group justify="flex-end">
            <Button
              disabled={!file}
              loading={upload.isPending}
              onClick={() =>
                file &&
                upload.mutate({
                  file,
                  sheet,
                  documentColumn,
                  columns: columns
                    .split(',')
                    .map((item) => item.trim())
                    .filter(Boolean),
                })
              }
            >
              {t('quality.upload')}
            </Button>
          </Group>
        </Stack>
      )}
    </Card>
  );
}

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

function EvaluationCard({
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

function CompareCard({
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
  const templates = useTemplates();
  const [template, setTemplate] = useState<string | null>(null);
  const [scope, setScope] = useState<'off' | 'unclassified' | 'missing_axes'>('off');
  const [model, setModel] = useState('');
  const [profile, setProfile] = useState('');
  const [budget, setBudget] = useState<number | string>(50);
  const last = quality.dry_run;
  const result = last?.result as
    | {
        baseline: Report | null;
        candidate: Report | null;
        documents: number;
        ai: { calls: number; prompt_tokens: number; completion_tokens: number; model: string | null };
        changes_total?: number;
        changes?: { document_key: string; axis: string; before: string[]; after: string[] }[];
      }
    | undefined;
  return (
    <Card withBorder component="section" aria-label={t('quality.compareTitle')}>
      <Title order={3} size="h4" mb="xs">
        {t('quality.compareTitle')}
      </Title>
      <Text size="sm" c="dimmed" mb="xs">
        {t('quality.compareIntro')}
      </Text>
      <Stack gap="xs">
        <Group grow align="flex-end">
          <Select
            label={t('quality.catalog')}
            clearable
            placeholder={t('quality.manifest')}
            value={template}
            data={(templates.data ?? []).map((item) => ({
              value: item.name,
              label: item.title ?? item.name,
            }))}
            onChange={setTemplate}
          />
          <Select
            label={t('quality.scope')}
            value={scope}
            allowDeselect={false}
            data={(['off', 'unclassified', 'missing_axes'] as const).map((value) => ({
              value,
              label: t(`quality.scopes.${value}`),
            }))}
            onChange={(value) => setScope((value ?? 'off') as typeof scope)}
          />
        </Group>
        <Group grow align="flex-end">
          <TextInput
            label={t('quality.model')}
            placeholder="doc-organize-classify"
            value={model}
            disabled={scope === 'off'}
            onChange={(e) => setModel(e.currentTarget.value)}
          />
          <NumberInput
            label={t('quality.budget')}
            min={1}
            max={5000}
            value={budget}
            disabled={scope === 'off'}
            onChange={setBudget}
          />
        </Group>
        <Textarea
          label={t('quality.profile')}
          description={t('quality.profileHelp')}
          value={profile}
          onChange={(e) => setProfile(e.currentTarget.value)}
          rows={3}
        />
        {scope !== 'off' && <Alert color="orange">{t('quality.aiWarning')}</Alert>}
        {run.error && <ErrorAlert error={run.error} />}
        {run.failure && (
          <Alert color="red" role="alert">
            {run.failure}
          </Alert>
        )}
        <Group justify="flex-end">
          <Button
            disabled={!ready}
            loading={run.running}
            onClick={() =>
              run.start({
                operation: 'context_dry_run',
                gold: source,
                catalog: template ? 'template' : 'manifest',
                template_name: template,
                ai_scope: scope,
                model_classify: model.trim() || null,
                profile_markdown: profile.trim() ? profile : null,
                max_documents: Number(budget) || 50,
              })
            }
          >
            {t('quality.compare')}
          </Button>
        </Group>
      </Stack>
      {result?.candidate && last && (
        <Stack gap="xs" mt="sm">
          <Text size="xs" c="dimmed">
            {t('quality.lastRun', { date: last.finished_at ? formatDateTime(last.finished_at) : '—' })} ·{' '}
            {t('quality.aiUsed', {
              calls: result.ai.calls,
              tokens: result.ai.prompt_tokens + result.ai.completion_tokens,
              model: result.ai.model ?? '—',
            })}
          </Text>
          <Table aria-label={t('quality.comparison')}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('quality.axis')}</Table.Th>
                <Table.Th>{t('quality.current')}</Table.Th>
                <Table.Th>{t('quality.candidate')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {Object.values(result.candidate.axes).map((axis) => {
                const before = result.baseline?.axes[axis.axis]?.accuracy;
                return (
                  <Table.Tr key={axis.axis}>
                    <Table.Td>{axis.axis}</Table.Td>
                    <Table.Td>{pct(before)}</Table.Td>
                    <Table.Td>
                      {pct(axis.accuracy)}
                      {typeof before === 'number' && typeof axis.accuracy === 'number' && (
                        <Badge
                          ml={6}
                          size="xs"
                          variant="light"
                          color={axis.accuracy > before ? 'teal' : axis.accuracy < before ? 'red' : 'gray'}
                        >
                          {axis.accuracy > before ? '+' : ''}
                          {Math.round((axis.accuracy - before) * 100)}
                        </Badge>
                      )}
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
          {typeof result.changes_total === 'number' && (
            <Text size="sm" fw={500}>
              {t('quality.changes', { count: result.changes_total })}
            </Text>
          )}
          {result.changes && result.changes.length > 0 && (
            <Table.ScrollContainer minWidth={520}>
              <Table aria-label={t('quality.changesTitle')}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('review.document')}</Table.Th>
                    <Table.Th>{t('quality.axis')}</Table.Th>
                    <Table.Th>{t('quality.current')}</Table.Th>
                    <Table.Th>{t('quality.candidate')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {result.changes.slice(0, 50).map((change) => (
                    <Table.Tr key={`${change.document_key}:${change.axis}`}>
                      <Table.Td>
                        <Text size="xs" ff="monospace" style={{ wordBreak: 'break-all' }}>
                          {change.document_key}
                        </Text>
                      </Table.Td>
                      <Table.Td>{change.axis}</Table.Td>
                      <Table.Td>{change.before.join(', ') || '—'}</Table.Td>
                      <Table.Td>{change.after.join(', ') || '—'}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
        </Stack>
      )}
    </Card>
  );
}

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
function AuditCard({ projectId, quality }: { projectId: number; quality: Quality }) {
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
