import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  NumberInput,
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
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { type GoldSource, pct, type Report } from './qualityReport';
import { useTemplates } from './useContext';
import { type Quality, useQualityRun } from './useQuality';

export function CompareCard({
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
