import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Modal,
  MultiSelect,
  NumberInput,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { BackLink } from '../../components/BackLink';
import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { type PageState, usePageState } from '../../components/usePageState';
import { formatCount, formatDateTime } from '../../components/format';
import { canDo, useProject } from '../projects/useProjects';
import { AxisBadges } from './Axes';
import { type ContextOut, useProjectContext } from './useContext';
import { useFollowedRun } from './useFollowedRun';

type ReviewItem = components['schemas']['ReviewItemOut'];
type ReviewReason = components['schemas']['ReviewItemOut']['reason'];
type Decision = components['schemas']['DecisionOut'];
type DecisionIn = components['schemas']['DecisionIn'];
type Proposal = components['schemas']['ProposalOut'];

interface ReviewAgentResult {
  stop_reason: string;
  finished: boolean;
  steps: number;
  tool_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  max_steps: number;
  reviewed: number;
  summary: string | null;
  proposals: number;
}

const REASONS: ReviewReason[] = [
  'stale_decision',
  'unclassified',
  'rules_ai_disagreement',
  'unverified_evidence',
  'low_confidence',
  'unconfirmed_version',
];

const reviewKey = (projectId: number) => ['projects', projectId, 'context', 'review'] as const;

function useReview(projectId: number, reason: ReviewReason | null, paging: PageState) {
  const { pageSize, offset } = paging;
  return useQuery({
    queryKey: [...reviewKey(projectId), { reason, pageSize, offset }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/review', {
          params: {
            path: { project_id: projectId },
            query: { reason, limit: pageSize, offset },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

function useDecisions(projectId: number) {
  return useQuery({
    queryKey: [...reviewKey(projectId), 'decisions'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/decisions', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

function useDecide(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: DecisionIn) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/context/decisions', {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reviewKey(projectId) }),
  });
}

function useRevoke(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string | null }) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/context/decisions/{decision_id}/revoke', {
          params: { path: { project_id: projectId, decision_id: id } },
          body: { reason },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reviewKey(projectId) }),
  });
}

function useProposals(projectId: number) {
  return useQuery({
    queryKey: [...reviewKey(projectId), 'proposals'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/review/proposals', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

function useProposalAction(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, accept }: { id: number; accept: boolean }) => {
      const params = { params: { path: { project_id: projectId, proposal_id: id } } };
      if (accept) {
        unwrap(
          await api.POST(
            '/api/v1/projects/{project_id}/context/review/proposals/{proposal_id}/accept',
            params,
          ),
        );
      } else {
        unwrap(
          await api.POST(
            '/api/v1/projects/{project_id}/context/review/proposals/{proposal_id}/discard',
            params,
          ),
        );
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reviewKey(projectId) }),
  });
}

/**
 * Revisar la clasificación (W5, doc_organize 2.0 F6): la cola de la última construcción (`review_queue`) y las
 * decisiones de personas, que se aplican al reconstruir.
 */
export function ReviewPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const context = useProjectContext(projectId);
  const [reason, setReason] = useState<ReviewReason | null>(null);
  const paging = usePageState();
  const review = useReview(projectId, reason, paging);

  if (project.isError || context.isError) {
    return <ErrorAlert error={project.error ?? context.error} />;
  }
  if (!project.data || context.data === undefined) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  const editable = canDo(project.data, 'editor') && project.data.destination_location.access === 'rw';
  const built = context.data;

  return (
    <Stack>
      <BackLink to={`/projects/${projectId}/context`}>{t('review.back')}</BackLink>
      <Title order={2}>{t('review.title')}</Title>
      <Text c="dimmed">{t('review.intro')}</Text>
      {!built ? (
        <Text c="dimmed" role="status">
          {t('context.empty')}
        </Text>
      ) : (
        <>
          <ProposalsCard projectId={projectId} context={built} editable={editable} />
          <Card withBorder>
            <Group align="flex-end" justify="space-between">
              <Select
                label={t('review.reason')}
                w={320}
                clearable
                value={reason}
                placeholder={t('review.allReasons')}
                data={REASONS.map((value) => ({
                  value,
                  label: t('review.option', {
                    label: t(`review.reasons.${value}`),
                    count: formatCount(review.data?.counts?.[value] ?? 0),
                  }),
                }))}
                onChange={(value) => {
                  setReason(value as ReviewReason | null);
                  paging.setPage(1, true);
                }}
              />
              {review.data && (
                <Text size="sm" role="status">
                  {t('review.total', { count: review.data.total, formatted: formatCount(review.data.total) })}
                </Text>
              )}
            </Group>
            {review.isError && <ErrorAlert error={review.error} mt="sm" />}
            {review.data && review.data.total === 0 && (
              <Text c="dimmed" mt="sm">
                {t('review.empty')}
              </Text>
            )}
            {review.data && review.data.items.length > 0 && (
              <>
                <Table.ScrollContainer minWidth={760} mt="sm">
                  <Table>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>{t('review.document')}</Table.Th>
                        <Table.Th>{t('review.why')}</Table.Th>
                        <Table.Th>{t('review.decision')}</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {review.data.items.map((item) => (
                        <ReviewRow
                          key={item.id}
                          item={item}
                          context={built}
                          projectId={projectId}
                          editable={editable}
                        />
                      ))}
                    </Table.Tbody>
                  </Table>
                </Table.ScrollContainer>
                <PageControls state={paging} total={review.data.total} label={t('paging.label')} />
              </>
            )}
          </Card>
          <DecisionsCard projectId={projectId} editable={editable} />
        </>
      )}
    </Stack>
  );
}

function ReviewRow({
  item,
  context,
  projectId,
  editable,
}: {
  item: ReviewItem;
  context: ContextOut;
  projectId: number;
  editable: boolean;
}) {
  const { t } = useTranslation();
  const decide = useDecide(projectId);
  const [changing, setChanging] = useState(false);
  const doc = item.document;
  const axes = context.taxonomy_axes ?? [];
  const axisName = axes.find((axis) => axis.key === item.axis)?.name ?? item.axis;
  const confirmAxes = Object.fromEntries(
    Object.entries(doc?.axes ?? {})
      .filter(([, values]) => values.length > 0)
      .map(([key, values]) => [key, values.map((value) => value.slug)]),
  );
  const send = (body: Omit<DecisionIn, 'document_key'>) =>
    decide.mutate({ document_key: item.document_key, ...body });

  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm">{doc?.title ?? item.document_key}</Text>
        <Text size="xs" ff="monospace" c="dimmed" style={{ wordBreak: 'break-all' }}>
          {item.document_key}
        </Text>
        {doc && <AxisBadges axes={axes} values={doc.axes} />}
        {doc?.version && (
          <Text size="xs" c="dimmed">
            {t('review.version', { version: doc.version })}
            {doc.is_current && ` · ${t('review.current')}`}
          </Text>
        )}
        {doc?.output_path && (
          <Anchor
            component={Link}
            to={`/projects/${projectId}/documents/view?path=${encodeURIComponent(doc.output_path)}`}
            size="xs"
          >
            {t('context.documents.view')}
          </Anchor>
        )}
      </Table.Td>
      <Table.Td>
        <Badge variant="light" color={item.priority <= 1 ? 'red' : item.priority <= 3 ? 'orange' : 'gray'}>
          {t(`review.reasons.${item.reason}`)}
        </Badge>
        {item.axis && (
          <Text size="xs" mt={2}>
            {axisName}
            {item.value && `: ${item.value}`}
            {typeof item.confidence === 'number' && ` (${Math.round(item.confidence * 100)} %)`}
          </Text>
        )}
        {item.detail && (
          <Text size="xs" c="dimmed">
            {item.detail}
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        {item.decision ? (
          <Text size="xs">
            {t('review.decided', {
              action: t(`review.actions.${item.decision.action}`),
              author: item.decision.author ?? '—',
              date: formatDateTime(item.decision.decided_at),
            })}
          </Text>
        ) : (
          <Text size="xs" c="dimmed">
            {t('review.noDecision')}
          </Text>
        )}
        {editable && doc && (
          <Group gap={4} mt={4}>
            <Button
              size="compact-xs"
              variant="light"
              disabled={Object.keys(confirmAxes).length === 0}
              loading={decide.isPending && decide.variables?.action === 'confirm'}
              onClick={() => send({ action: 'confirm', axes: confirmAxes })}
            >
              {t('review.actions.confirm')}
            </Button>
            <Button size="compact-xs" variant="light" onClick={() => setChanging(true)}>
              {t('review.change')}
            </Button>
            <Button
              size="compact-xs"
              variant="light"
              color="red"
              loading={decide.isPending && decide.variables?.action === 'exclude'}
              onClick={() => send({ action: 'exclude' })}
            >
              {t('review.actions.exclude')}
            </Button>
            {doc.version_group && !doc.is_current && (
              <Button
                size="compact-xs"
                variant="light"
                loading={decide.isPending && decide.variables?.action === 'set_current_version'}
                onClick={() => send({ action: 'set_current_version' })}
              >
                {t('review.actions.set_current_version')}
              </Button>
            )}
          </Group>
        )}
        {decide.isError && <ErrorAlert error={decide.error} mt={4} />}
        {changing && (
          <ChangeAxisModal
            item={item}
            context={context}
            onClose={() => setChanging(false)}
            onSave={(axis, values, reason) =>
              decide.mutate(
                { document_key: item.document_key, action: 'set_axis', axes: { [axis]: values }, reason },
                { onSuccess: () => setChanging(false) },
              )
            }
            saving={decide.isPending}
          />
        )}
      </Table.Td>
    </Table.Tr>
  );
}

/** Fijar los valores de un eje (solo valores del catálogo; uno en los ejes que organizan carpetas). */
function ChangeAxisModal({
  item,
  context,
  onClose,
  onSave,
  saving,
}: {
  item: ReviewItem;
  context: ContextOut;
  onClose: () => void;
  onSave: (axis: string, values: string[], reason: string | null) => void;
  saving: boolean;
}) {
  const { t } = useTranslation();
  const axes = context.taxonomy_axes ?? [];
  const [axisKey, setAxisKey] = useState<string | null>(item.axis ?? axes[0]?.key ?? null);
  const axis = axes.find((candidate) => candidate.key === axisKey);
  const current = (axisKey && item.document?.axes[axisKey]?.map((value) => value.slug)) || [];
  const [values, setValues] = useState<string[]>(current);
  const [reason, setReason] = useState('');
  const single = !axis?.multiple || Boolean(axis?.organizes);
  const options = (axis?.values ?? []).map((value) => ({ value: value.slug, label: value.name }));
  return (
    <Modal opened onClose={onClose} title={t('review.changeTitle')}>
      <Stack>
        <Select
          label={t('review.axis')}
          value={axisKey}
          data={axes.map((candidate) => ({ value: candidate.key, label: candidate.name }))}
          onChange={(value) => {
            setAxisKey(value);
            setValues((value && item.document?.axes[value]?.map((v) => v.slug)) || []);
          }}
        />
        {single ? (
          <Select
            label={t('review.value')}
            value={values[0] ?? null}
            data={options}
            searchable
            clearable={!axis?.organizes}
            onChange={(value) => setValues(value ? [value] : [])}
          />
        ) : (
          <MultiSelect
            label={t('review.values')}
            value={values}
            data={options}
            searchable
            onChange={setValues}
          />
        )}
        <TextInput
          label={t('review.why')}
          maxLength={500}
          value={reason}
          onChange={(event) => setReason(event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            loading={saving}
            disabled={!axisKey || (Boolean(axis?.organizes) && values.length !== 1)}
            onClick={() => axisKey && onSave(axisKey, values, reason.trim() || null)}
          >
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Decisiones vigentes (con «Revocar»), las que la última construcción no aplicó y el historial. */
function DecisionsCard({ projectId, editable }: { projectId: number; editable: boolean }) {
  const { t } = useTranslation();
  const decisions = useDecisions(projectId);
  const revoke = useRevoke(projectId);
  if (decisions.isError) {
    return <ErrorAlert error={decisions.error} />;
  }
  if (!decisions.data) {
    return null;
  }
  const { data } = decisions;
  const describe = (decision: Decision) =>
    [
      t(`review.actions.${decision.action}`),
      ...Object.entries(decision.axes).map(([axis, values]) => `${axis}: ${values.join(', ') || '—'}`),
    ].join(' · ');
  return (
    <Card withBorder component="section" aria-label={t('review.decisionsTitle')}>
      <Title order={3} size="h4" mb="xs">
        {t('review.decisionsTitle')}
      </Title>
      <Text size="sm" c="dimmed" mb="xs">
        {t('review.decisionsIntro', { applied: data.applied })}
      </Text>
      {[...data.stale, ...data.orphan].length > 0 && (
        <Alert color="orange" mb="xs" title={t('review.notApplied')}>
          <Stack gap={0}>
            {[...data.stale, ...data.orphan].map((issue) => (
              <Text key={issue.decision_id} size="xs">
                {issue.document_key}: {t(`review.issues.${issue.reason}`, { defaultValue: issue.reason })}
              </Text>
            ))}
          </Stack>
        </Alert>
      )}
      {data.decisions.length === 0 ? (
        <Text size="sm" c="dimmed">
          {t('review.noDecisions')}
        </Text>
      ) : (
        <Table>
          <Table.Tbody>
            {data.decisions.map((decision) => (
              <Table.Tr key={decision.id}>
                <Table.Td>
                  <Text size="xs" ff="monospace" style={{ wordBreak: 'break-all' }}>
                    {decision.document_key}
                  </Text>
                  <Text size="xs">{describe(decision)}</Text>
                  <Text size="xs" c="dimmed">
                    {t('review.by', {
                      author: decision.author ?? '—',
                      date: formatDateTime(decision.decided_at),
                    })}
                    {decision.reason && ` · ${decision.reason}`}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {editable && (
                    <Button
                      size="compact-xs"
                      variant="subtle"
                      color="red"
                      loading={revoke.isPending && revoke.variables?.id === decision.id}
                      onClick={() => revoke.mutate({ id: decision.id, reason: null })}
                      aria-label={t('review.revokeLabel', { key: decision.document_key })}
                    >
                      {t('review.revoke')}
                    </Button>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {revoke.isError && <ErrorAlert error={revoke.error} mt="xs" />}
      {data.revoked.length > 0 && (
        <Text component="details" size="xs" mt="sm">
          <summary style={{ cursor: 'pointer' }}>
            {t('review.history', { count: data.revoked.length })}
          </summary>
          <Stack gap={2} mt={4}>
            {data.revoked.map((decision) => (
              <Text key={`${decision.id}:${decision.revoked_at}`} size="xs">
                {decision.document_key} · {describe(decision)} ·{' '}
                {t('review.revokedBy', {
                  author: decision.revoked_by ?? '—',
                  date: decision.revoked_at ? formatDateTime(decision.revoked_at) : '—',
                })}
                {decision.revoke_reason && ` (${decision.revoke_reason})`}
              </Text>
            ))}
          </Stack>
        </Text>
      )}
    </Card>
  );
}

/**
 * Propuestas del revisor (W7, `ReviewAgent`, tarea `agent`): se piden como un trabajo; se guardan sin aplicarse y cada
 * una se acepta (decisión de quien la acepta) o se descarta.
 */
function ProposalsCard({
  projectId,
  context,
  editable,
}: {
  projectId: number;
  context: ContextOut;
  editable: boolean;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const proposals = useProposals(projectId);
  const action = useProposalAction(projectId);
  const agent = useFollowedRun<ReviewAgentResult>(projectId);
  const [items, setItems] = useState<number | string>(20);
  const [steps, setSteps] = useState<number | string>(40);
  const [instructions, setInstructions] = useState('');
  const result = agent.result;
  useEffect(() => {
    if (result) {
      void queryClient.invalidateQueries({ queryKey: reviewKey(projectId) });
    }
  }, [result, projectId, queryClient]);
  const axes = context.taxonomy_axes ?? [];
  const describe = (proposal: Proposal) =>
    [
      t(`review.actions.${proposal.action}`),
      ...Object.entries(proposal.axes ?? {}).map(
        ([axis, values]) =>
          `${axes.find((candidate) => candidate.key === axis)?.name ?? axis}: ${values.join(', ') || '—'}`,
      ),
    ].join(' · ');

  return (
    <Card withBorder component="section" aria-label={t('review.proposals.title')}>
      <Title order={3} size="h4" mb="xs">
        {t('review.proposals.title')}
      </Title>
      <Text size="sm" c="dimmed" mb="xs">
        {t('review.proposals.intro')}
      </Text>
      {editable && (
        <Stack gap="xs" mb="sm">
          <Group align="flex-end">
            <NumberInput
              label={t('review.proposals.maxItems')}
              description={t('review.proposals.maxItemsHelp')}
              min={1}
              max={100}
              w={200}
              value={items}
              onChange={setItems}
            />
            <NumberInput
              label={t('review.proposals.maxSteps')}
              description={t('review.proposals.maxStepsHelp')}
              min={1}
              max={80}
              w={200}
              value={steps}
              onChange={setSteps}
            />
          </Group>
          <Textarea
            label={t('review.proposals.instructions')}
            maxLength={2000}
            rows={2}
            value={instructions}
            onChange={(event) => setInstructions(event.currentTarget.value)}
          />
          <Alert color="orange">{t('review.proposals.warning')}</Alert>
          <Group>
            <Button
              loading={agent.running}
              onClick={() =>
                agent.start({
                  operation: 'context_review_agent',
                  max_items: Number(items) || 20,
                  max_steps: Number(steps) || 40,
                  instructions,
                })
              }
            >
              {t('review.proposals.start')}
            </Button>
          </Group>
          {agent.error && <ErrorAlert error={agent.error} />}
          {agent.failure && <Alert color="red">{agent.failure}</Alert>}
          {result && (
            <Stack gap={4}>
              <Group gap="xs">
                <Badge color={result.finished ? 'teal' : 'orange'} variant="light">
                  {t(`context.agent.stop.${result.stop_reason}`, { defaultValue: result.stop_reason })}
                </Badge>
                <Text size="xs" c="dimmed">
                  {t('review.proposals.usage', {
                    steps: result.steps,
                    max: result.max_steps,
                    tools: result.tool_calls,
                    tokens: result.prompt_tokens + result.completion_tokens,
                    proposals: result.proposals,
                    reviewed: result.reviewed,
                  })}
                </Text>
              </Group>
              {result.summary && <Text size="sm">{result.summary}</Text>}
            </Stack>
          )}
        </Stack>
      )}
      {proposals.isError && <ErrorAlert error={proposals.error} />}
      {proposals.data && proposals.data.items.length === 0 && (
        <Text size="sm" c="dimmed">
          {t('review.proposals.empty')}
        </Text>
      )}
      {proposals.data && proposals.data.items.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table>
            <Table.Tbody>
              {proposals.data.items.map((proposal) => (
                <Table.Tr key={proposal.id}>
                  <Table.Td>
                    <Text size="sm">{proposal.document?.title ?? proposal.document_key}</Text>
                    <Text size="xs" ff="monospace" c="dimmed" style={{ wordBreak: 'break-all' }}>
                      {proposal.document_key}
                    </Text>
                    {proposal.document ? (
                      <AxisBadges axes={axes} values={proposal.document.axes} />
                    ) : (
                      <Text size="xs" c="orange">
                        {t('review.proposals.noDocument')}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" fw={500}>
                      {describe(proposal)}
                    </Text>
                    {proposal.rationale && <Text size="xs">{proposal.rationale}</Text>}
                    {proposal.evidence && (
                      <Text size="xs" c="dimmed">
                        {t('review.proposals.evidence', { evidence: proposal.evidence })}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    {editable && (
                      <Group gap={4} wrap="nowrap">
                        <Button
                          size="compact-xs"
                          variant="light"
                          loading={
                            action.isPending &&
                            action.variables?.id === proposal.id &&
                            action.variables.accept
                          }
                          onClick={() => action.mutate({ id: proposal.id, accept: true })}
                          aria-label={t('review.proposals.acceptLabel', { key: proposal.document_key })}
                        >
                          {t('review.proposals.accept')}
                        </Button>
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="red"
                          loading={
                            action.isPending &&
                            action.variables?.id === proposal.id &&
                            !action.variables.accept
                          }
                          onClick={() => action.mutate({ id: proposal.id, accept: false })}
                          aria-label={t('review.proposals.discardLabel', { key: proposal.document_key })}
                        >
                          {t('review.proposals.discard')}
                        </Button>
                      </Group>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {action.isError && <ErrorAlert error={action.error} mt="xs" />}
    </Card>
  );
}
