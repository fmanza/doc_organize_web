import { Card, Center, Group, Loader, Select, Stack, Table, Text, Title } from '@mantine/core';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';
import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { formatCount } from '../../components/format';
import { SearchBox } from '../../components/listing';
import { usePageState } from '../../components/usePageState';
import { canDo, useProject } from '../projects/useProjects';
import { ContextNav } from './ContextNav';
import { DecisionsCard } from './DecisionsCard';
import { ProposalsCard } from './ProposalsCard';
import { ReviewRow } from './ReviewRow';
import { useProjectContext } from './useContext';
import { type ReviewReason, useReview } from './useReview';

const REASONS: ReviewReason[] = [
  'stale_decision',
  'unclassified',
  'rules_ai_disagreement',
  'unverified_evidence',
  'low_confidence',
  'unconfirmed_version',
];

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
  const [q, setQ] = useState('');
  const paging = usePageState();
  const review = useReview(projectId, reason, q.trim(), paging);
  const { setPage } = paging;
  const search = useCallback(
    (value: string) => {
      setQ(value);
      setPage(1, true);
    },
    [setPage],
  );

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
      <ContextNav projectId={projectId} active="revisar" />
      <Title order={3}>{t('review.title')}</Title>
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
              <SearchBox value={q} onChange={search} label={t('review.search')} />
              {review.data && (
                <Text size="sm" role="status">
                  {t('review.total', { count: review.data.total, formatted: formatCount(review.data.total) })}
                </Text>
              )}
            </Group>
            {review.isError && <ErrorAlert error={review.error} mt="sm" />}
            {review.data && review.data.total === 0 && (
              <Text c="dimmed" mt="sm">
                {q.trim() ? t('review.noMatches') : t('review.empty')}
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
