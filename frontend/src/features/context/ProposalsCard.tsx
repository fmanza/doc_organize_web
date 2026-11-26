import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  NumberInput,
  Stack,
  Table,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { AxisBadges } from './Axes';
import { type ContextOut } from './useContext';
import { useFollowedRun } from './useFollowedRun';
import { type Proposal, reviewKey, useProposalAction, useProposals } from './useReview';

/**
 * Propuestas del revisor (W7, `ReviewAgent`, tarea `agent`): se piden como un trabajo; se guardan sin aplicarse y cada
 * una se acepta (decisión de quien la acepta) o se descarta.
 */
export function ProposalsCard({
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
  const agent = useFollowedRun(projectId, 'context_review_agent');
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
          {agent.failure && (
            <Alert color="red" role="alert">
              {agent.failure}
            </Alert>
          )}
          {result && (
            <Stack gap={4}>
              <Group gap="xs">
                <Badge color={result.finished ? 'teal' : 'orange'} variant="light">
                  {t(`context.agent.stop.${result.stop_reason}`, {
                    defaultValue: result.stop_reason ?? undefined,
                  })}
                </Badge>
                <Text size="xs" c="dimmed">
                  {t('review.proposals.usage', {
                    steps: result.steps,
                    max: result.max_steps,
                    tools: result.tool_calls,
                    tokens: (result.prompt_tokens ?? 0) + (result.completion_tokens ?? 0),
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
