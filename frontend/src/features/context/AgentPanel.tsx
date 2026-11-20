import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { can, useMe } from '../auth/useAuth';
import { TEMPLATE_NAME, useSaveTemplate, useTemplates } from './useContext';
import { useFollowedRun } from './useFollowedRun';

interface AxisReport {
  axis: string;
  documents: number;
  covered: number;
  conflicts: number;
  coverage: number;
  empty_entries: string[];
  unused_keywords: Record<string, string[]>;
}
interface RulesReport {
  axes: AxisReport[];
  documents: number;
  markdown: string;
}
interface DesignResult {
  stop_reason: string;
  finished: boolean;
  steps: number;
  tool_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  max_steps: number;
  documents: number;
  improves: boolean | null;
  rationale: string | null;
  edits: number;
  markdown: string | null;
  draft_markdown: string | null;
  best_markdown: string | null;
  base_report: RulesReport | null;
  report: RulesReport | null;
  best_report: RulesReport | null;
}

const pct = (value: number | undefined) => (typeof value === 'number' ? `${Math.round(value * 100)} %` : '—');

/** Por eje: cobertura y conflictos de uno o dos informes por reglas (antes y después). */
function RulesTable({ before, after }: { before: RulesReport | null; after: RulesReport | null }) {
  const { t } = useTranslation();
  const report = after ?? before;
  if (!report) {
    return null;
  }
  const previous = Object.fromEntries((before?.axes ?? []).map((axis) => [axis.axis, axis]));
  return (
    <Table.ScrollContainer minWidth={480}>
      <Table aria-label={t('context.agent.rules')}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('quality.axis')}</Table.Th>
            {after && before && <Table.Th>{t('context.agent.coverageBefore')}</Table.Th>}
            <Table.Th>{t('quality.coverage')}</Table.Th>
            {after && before && <Table.Th>{t('context.agent.conflictsBefore')}</Table.Th>}
            <Table.Th>{t('context.agent.conflicts')}</Table.Th>
            <Table.Th>{t('context.agent.empty')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {report.axes.map((axis) => (
            <Table.Tr key={axis.axis}>
              <Table.Td>{axis.axis}</Table.Td>
              {after && before && <Table.Td>{pct(previous[axis.axis]?.coverage)}</Table.Td>}
              <Table.Td>{pct(axis.coverage)}</Table.Td>
              {after && before && <Table.Td>{previous[axis.axis]?.conflicts ?? '—'}</Table.Td>}
              <Table.Td>{axis.conflicts}</Table.Td>
              <Table.Td>{axis.empty_entries.join(', ') || '—'}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

/** «Comprobar manifiesto» (W7, `check_taxonomy_rules`): el texto del editor contra todos los documentos, sin IA. */
export function RulesCheck({ projectId, markdown }: { projectId: number; markdown: string }) {
  const { t } = useTranslation();
  const check = useFollowedRun<{ report: RulesReport }>(projectId);
  return (
    <Stack gap="xs" mt="xs">
      <Group>
        <Button
          variant="default"
          size="xs"
          loading={check.running}
          disabled={!markdown.trim()}
          onClick={() => check.start({ operation: 'taxonomy_check', markdown })}
        >
          {t('context.agent.check')}
        </Button>
        <Text size="xs" c="dimmed">
          {t('context.agent.checkHelp')}
        </Text>
      </Group>
      {check.error && <ErrorAlert error={check.error} />}
      {check.failure && <Alert color="red">{check.failure}</Alert>}
      {check.result && (
        <>
          <Text size="xs">{t('context.agent.documents', { count: check.result.report.documents })}</Text>
          <RulesTable before={null} after={check.result.report} />
        </>
      )}
    </Stack>
  );
}

/**
 * «Diseñar taxonomía con IA» (W7, `TaxonomyDesignAgent`, tarea `agent`): el agente propone cambios comprobados por
 * reglas; la propuesta se carga en el editor para revisarla y guardarla a mano (nunca se guarda sola).
 */
export function AgentPanel({
  projectId,
  hasManifest,
  onLoad,
}: {
  projectId: number;
  hasManifest: boolean;
  onLoad: (markdown: string) => void;
}) {
  const { t } = useTranslation();
  const me = useMe();
  const templates = useTemplates();
  const agent = useFollowedRun<DesignResult>(projectId);
  const [base, setBase] = useState<'manifest' | 'template' | 'none'>(hasManifest ? 'manifest' : 'none');
  const [template, setTemplate] = useState<string | null>(null);
  const [instructions, setInstructions] = useState('');
  const [steps, setSteps] = useState<number | string>(30);
  const [saving, setSaving] = useState<string | null>(null);
  const result = agent.result;
  const proposal = result?.markdown ?? result?.draft_markdown ?? null;
  const ready = base !== 'template' || template !== null;

  return (
    <Card withBorder mb="sm" component="section" aria-label={t('context.agent.title')}>
      <Text fw={500} size="sm">
        {t('context.agent.title')}
      </Text>
      <Text size="xs" c="dimmed" mb="xs">
        {t('context.agent.intro')}
      </Text>
      <Stack gap="xs">
        <SegmentedControl
          size="xs"
          value={base}
          onChange={(value) => setBase(value as typeof base)}
          aria-label={t('context.agent.base')}
          data={[
            { value: 'manifest', label: t('context.agent.bases.manifest'), disabled: !hasManifest },
            { value: 'template', label: t('context.agent.bases.template') },
            { value: 'none', label: t('context.agent.bases.none') },
          ]}
        />
        {base === 'template' && (
          <Select
            label={t('quality.catalog')}
            value={template}
            onChange={setTemplate}
            data={(templates.data ?? []).map((item) => ({
              value: item.name,
              label: item.title ?? item.name,
            }))}
          />
        )}
        <Textarea
          label={t('context.agent.instructions')}
          placeholder={t('context.agent.instructionsPlaceholder')}
          maxLength={2000}
          value={instructions}
          onChange={(event) => setInstructions(event.currentTarget.value)}
          rows={2}
        />
        <Group align="flex-end">
          <NumberInput
            label={t('context.agent.maxSteps')}
            description={t('context.agent.maxStepsHelp')}
            min={1}
            max={60}
            w={220}
            value={steps}
            onChange={setSteps}
          />
          <Button
            loading={agent.running}
            disabled={!ready}
            onClick={() =>
              agent.start({
                operation: 'taxonomy_agent',
                catalog: base,
                template_name: base === 'template' ? template : null,
                instructions,
                max_steps: Number(steps) || 30,
              })
            }
          >
            {t('context.agent.start')}
          </Button>
        </Group>
        <Alert color="orange">{t('context.agent.warning')}</Alert>
        {agent.error && <ErrorAlert error={agent.error} />}
        {agent.failure && <Alert color="red">{agent.failure}</Alert>}
        {result && (
          <Stack gap="xs">
            <Group gap="xs">
              <Badge color={result.finished ? 'teal' : 'orange'} variant="light">
                {t(`context.agent.stop.${result.stop_reason}`, { defaultValue: result.stop_reason })}
              </Badge>
              {result.improves !== null && (
                <Badge color={result.improves ? 'teal' : 'gray'} variant="light">
                  {t(result.improves ? 'context.agent.improves' : 'context.agent.notImproves')}
                </Badge>
              )}
              <Text size="xs" c="dimmed">
                {t('context.agent.usage', {
                  steps: result.steps,
                  max: result.max_steps,
                  tools: result.tool_calls,
                  tokens: result.prompt_tokens + result.completion_tokens,
                  edits: result.edits,
                })}
              </Text>
            </Group>
            {result.rationale && <Text size="sm">{result.rationale}</Text>}
            <RulesTable before={result.base_report} after={result.report ?? result.best_report} />
            <Group>
              {proposal && (
                <Button size="xs" onClick={() => onLoad(proposal)}>
                  {t(result.markdown ? 'context.agent.load' : 'context.agent.loadDraft')}
                </Button>
              )}
              {result.best_markdown && (
                <Button size="xs" variant="light" onClick={() => onLoad(result.best_markdown ?? '')}>
                  {t('context.agent.loadBest')}
                </Button>
              )}
              {proposal && can(me.data, 'templates.manage') && (
                <Button size="xs" variant="default" onClick={() => setSaving(proposal)}>
                  {t('context.agent.saveTemplate')}
                </Button>
              )}
            </Group>
          </Stack>
        )}
      </Stack>
      {saving !== null && (
        <SaveTemplateModal
          markdown={saving}
          taken={(templates.data ?? []).map((item) => item.name)}
          onClose={() => setSaving(null)}
        />
      )}
    </Card>
  );
}

/** Guardar la propuesta como plantilla nueva (`templates.manage`), tras revisarla. */
function SaveTemplateModal({
  markdown,
  taken,
  onClose,
}: {
  markdown: string;
  taken: string[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const save = useSaveTemplate();
  const [name, setName] = useState('');
  return (
    <Modal opened onClose={onClose} title={t('context.agent.saveTemplate')}>
      <Stack>
        <TextInput
          label={t('templates.fields.name')}
          description={t('templates.nameHelp')}
          value={name}
          maxLength={64}
          onChange={(event) => setName(event.currentTarget.value)}
          error={
            taken.includes(name)
              ? t('templates.nameTaken')
              : name && !TEMPLATE_NAME.test(name)
                ? t('templates.nameInvalid')
                : undefined
          }
        />
        {save.isError && <ErrorAlert error={save.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            loading={save.isPending}
            disabled={!TEMPLATE_NAME.test(name) || taken.includes(name)}
            onClick={() => save.mutate({ name, markdown }, { onSuccess: onClose })}
          >
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
