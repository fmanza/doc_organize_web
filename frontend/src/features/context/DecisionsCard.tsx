import { Alert, Button, Card, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { type Decision, useDecisions, useRevoke } from './useReview';

/** Decisiones vigentes (con «Revocar»), las que la última construcción no aplicó y el historial. */
export function DecisionsCard({ projectId, editable }: { projectId: number; editable: boolean }) {
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
