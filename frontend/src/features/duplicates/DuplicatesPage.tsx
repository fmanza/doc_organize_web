import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Checkbox,
  Group,
  Loader,
  NumberInput,
  Radio,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { SearchBox, SortableTh, SortSelect } from '../../components/listing';
import { sortRows, useListState, useLocalSort } from '../../components/useListState';
import { formatBytes, formatCount, formatDateTime } from '../../components/format';
import { canDo, useEnqueueRun, useProject } from '../projects/useProjects';
import { RunResult } from '../runs/RunResult';
import { useRun } from '../runs/useRuns';
import { ApplyModal } from './ApplyModal';
import {
  decision,
  type DuplicateGroup,
  type DuplicateReason,
  type GroupOverride,
  type GroupSort,
  GROUPS_PAGE_SIZE,
  type KeepPolicy,
  storedReview,
  storeReview,
  useDuplicateGroups,
  useLastDuplicates,
} from './useDuplicates';

const REASON_COLOR: Record<DuplicateReason, string> = {
  exact_duplicate: 'blue',
  version_conflict: 'grape',
  fuzzy_name_match: 'orange',
};
const DEFAULT_FUZZY = 85;

/**
 * Resolutor de duplicados en dos pasos (sustituye a `duplicates_resolver.html.j2`): buscar (vista previa, sin tocar
 * ficheros), revisar grupo a grupo qué se conserva y aplicar solo lo confirmado.
 */
const GROUP_SORT: readonly GroupSort[] = ['position', 'reason', 'member_count'];

export function DuplicatesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const projectId = Number(useParams().projectId);
  const [params] = useSearchParams();
  const project = useProject(projectId);
  const last = useLastDuplicates(projectId);
  const enqueue = useEnqueueRun(projectId);
  const [fuzzy, setFuzzy] = useState(false);
  const [threshold, setThreshold] = useState<number>(DEFAULT_FUZZY);
  const [reason, setReason] = useState<DuplicateReason | null>(null);
  const list = useListState(GROUP_SORT, '', GROUPS_PAGE_SIZE);
  const { paging } = list;
  const [applying, setApplying] = useState(false);

  const runId = params.get('run') ?? last.data?.preview?.id ?? null;
  // Decisiones de la búsqueda que se revisa: guardadas en la pestaña y nuevas al cambiar de búsqueda.
  const [review, setReview] = useState(() => ({ runId, ...storedReview(runId) }));
  if (review.runId !== runId) {
    setReview({ runId, ...storedReview(runId) });
  }
  const { policy, overrides } = review;
  const updateReview = (change: Partial<{ policy: KeepPolicy; overrides: Record<string, GroupOverride> }>) =>
    setReview((current) => {
      const next = { ...current, ...change };
      if (next.runId) storeReview(next.runId, { policy: next.policy, overrides: next.overrides });
      return next;
    });
  const preview = useRun(runId);
  const groups = useDuplicateGroups(runId, reason, list.query);

  if (project.isPending || last.isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (project.isError) {
    return <ErrorAlert error={project.error} />;
  }
  if (last.isError) {
    return <ErrorAlert error={last.error} />;
  }
  const canEdit = canDo(project.data, 'editor');
  const lastApply = last.data.apply;
  const reviewed = preview.data;
  const appliedAfter =
    lastApply && reviewed && new Date(lastApply.created_at) > new Date(reviewed.created_at);
  const override = (groupId: string, change: GroupOverride) =>
    updateReview({ overrides: { ...overrides, [groupId]: { ...overrides[groupId], ...change } } });

  return (
    <Stack>
      <Anchor component={Link} to={`/projects/${projectId}`} size="sm">
        {t('duplicates.back', { name: project.data.name })}
      </Anchor>
      <Title order={2}>{t('duplicates.title')}</Title>
      <Text c="dimmed">{t('duplicates.intro')}</Text>

      {canEdit && (
        <Card withBorder>
          <Title order={3} size="h4" mb="xs">
            {t('duplicates.search.title')}
          </Title>
          <Group align="flex-end">
            <Switch
              label={t('duplicates.search.fuzzy')}
              description={t('duplicates.search.fuzzyHelp')}
              checked={fuzzy}
              onChange={(event) => setFuzzy(event.currentTarget.checked)}
            />
            {fuzzy && (
              <NumberInput
                label={t('duplicates.search.threshold')}
                min={50}
                max={100}
                clampBehavior="strict"
                value={threshold}
                onChange={(value) => setThreshold(typeof value === 'number' ? value : DEFAULT_FUZZY)}
                w={140}
              />
            )}
            <Button
              loading={enqueue.isPending}
              onClick={() =>
                enqueue.mutate(
                  { operation: 'dedup_preview', fuzzy_threshold: fuzzy ? threshold : null },
                  { onSuccess: (run) => void navigate(`/runs/${run.id}`) },
                )
              }
            >
              {t('duplicates.search.run')}
            </Button>
          </Group>
          {enqueue.isError && <ErrorAlert error={enqueue.error} mt="sm" />}
        </Card>
      )}

      {lastApply && (
        <Alert color={appliedAfter ? 'orange' : 'gray'}>
          {t(appliedAfter ? 'duplicates.appliedAfter' : 'duplicates.lastApply', {
            date: formatDateTime(lastApply.finished_at ?? lastApply.created_at),
          })}{' '}
          <Anchor component={Link} to={`/runs/${lastApply.id}`}>
            {t('duplicates.openRun')}
          </Anchor>
        </Alert>
      )}

      {runId === null ? (
        <Text c="dimmed">{t('duplicates.noPreview')}</Text>
      ) : preview.isError ? (
        <ErrorAlert error={preview.error} />
      ) : !reviewed ? (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      ) : reviewed.status !== 'succeeded' ? (
        <Alert color="gray">
          {t('duplicates.previewNotReady')}{' '}
          <Anchor component={Link} to={`/runs/${reviewed.id}`}>
            {t('duplicates.openRun')}
          </Anchor>
        </Alert>
      ) : (
        <>
          <Card withBorder>
            <Group justify="space-between" mb="xs">
              <Title order={3} size="h4">
                {t('duplicates.preview', { date: formatDateTime(reviewed.finished_at) })}
              </Title>
              <Anchor component={Link} to={`/runs/${reviewed.id}`} size="sm">
                {t('duplicates.openRun')}
              </Anchor>
            </Group>
            {reviewed.result && <RunResult result={reviewed.result} />}
          </Card>

          <Group align="flex-end" justify="space-between">
            <SegmentedControl
              value={reason ?? 'all'}
              onChange={(value) => {
                setReason(value === 'all' ? null : (value as DuplicateReason));
                paging.setPage(1, true);
              }}
              data={[
                { value: 'all', label: t('duplicates.reasons.all') },
                { value: 'exact_duplicate', label: t('duplicates.reasons.exact_duplicate') },
                { value: 'version_conflict', label: t('duplicates.reasons.version_conflict') },
                { value: 'fuzzy_name_match', label: t('duplicates.reasons.fuzzy_name_match') },
              ]}
            />
            <Group align="flex-end">
              <Select
                label={t('duplicates.policy.label')}
                value={policy}
                onChange={(value) => updateReview({ policy: (value as KeepPolicy | null) ?? 'oldest' })}
                allowDeselect={false}
                data={(['oldest', 'newest', 'shortest'] as const).map((value) => ({
                  value,
                  label: t(`duplicates.policy.${value}`),
                }))}
              />
              {Object.keys(overrides).length > 0 && (
                <Button variant="subtle" onClick={() => updateReview({ overrides: {} })}>
                  {t('duplicates.resetChoices')}
                </Button>
              )}
              {canEdit && (
                <Button
                  color="orange"
                  onClick={() => setApplying(true)}
                  disabled={!reviewed.result || reviewed.result.groups === 0}
                >
                  {t('duplicates.applyButton')}
                </Button>
              )}
            </Group>
          </Group>

          <Group align="flex-end">
            <SearchBox value={list.q} onChange={list.setQ} label={t('duplicates.groupSearch')} />
            <SortSelect
              state={list}
              label={t('listing.sortLabel')}
              options={GROUP_SORT.map((value) => ({ value, label: t(`duplicates.sort.${value}`) }))}
            />
          </Group>
          {groups.isError ? (
            <ErrorAlert error={groups.error} />
          ) : !groups.data ? (
            <Center>
              <Loader aria-label={t('common.loading')} />
            </Center>
          ) : groups.data.total === 0 ? (
            <Text c="dimmed" role="status">
              {t(list.q ? 'listing.empty' : 'duplicates.empty')}
            </Text>
          ) : (
            <>
              <Text size="sm" role="status">
                {t('duplicates.total', {
                  count: groups.data.total,
                  formatted: formatCount(groups.data.total),
                })}
              </Text>
              {groups.data.items.map((group, index) => (
                <GroupCard
                  key={group.group_id}
                  number={paging.offset + index + 1}
                  manual={overrides[group.group_id]?.keep !== undefined}
                  projectId={projectId}
                  group={group}
                  choice={decision(group, policy, overrides)}
                  editable={canEdit}
                  onChange={(change) => override(group.group_id, change)}
                />
              ))}
              <PageControls state={paging} total={groups.data.total} label={t('duplicates.pages')} />
            </>
          )}
          {applying && (
            <ApplyModal
              projectId={projectId}
              projectName={project.data.name}
              groupsRunId={reviewed.id}
              policy={policy}
              overrides={overrides}
              canMove={canDo(project.data, 'owner') && project.data.source_location.access === 'rw'}
              onClose={() => setApplying(false)}
            />
          )}
        </>
      )}
    </Stack>
  );
}

/** Miembros que se ven de un grupo plegado. */
const FOLDED_MEMBERS = 5;

interface GroupCardProps {
  /** Posición del grupo en la búsqueda (para su nombre accesible). */
  number: number;
  manual: boolean;
  projectId: number;
  group: DuplicateGroup;
  choice: { include: boolean; keep: string };
  editable: boolean;
  onChange: (change: GroupOverride) => void;
}

type Member = DuplicateGroup['members'][number];
type MemberSort = 'document' | 'size' | 'modified' | 'hash';

function memberValue(member: Member, key: MemberSort): string | number | null {
  switch (key) {
    case 'document':
      return member.key;
    case 'size':
      return member.size_bytes;
    case 'modified':
      return member.modified_at;
    case 'hash':
      return member.sha256;
  }
}

/** Un grupo con sus documentos lado a lado: cuál se conserva y si el grupo se aplica. */
function GroupCard({ number, manual, projectId, group, choice, editable, onChange }: GroupCardProps) {
  const { t } = useTranslation();
  const name = `keep-${group.group_id}`;
  const label = { number, name: group.members[0]?.path.split('/').at(-1) ?? '' };
  const [expanded, setExpanded] = useState(false);
  // Orden de los documentos del grupo (web 1.2.0): local, no va a la URL.
  const memberSort = useLocalSort<MemberSort>();
  const members = sortRows(group.members, memberSort, memberValue);
  // Un grupo grande se pliega a los primeros (y al que se conserva, si está más abajo): la página no se alarga.
  const folded = !expanded && members.length > FOLDED_MEMBERS;
  const visible = folded
    ? members.filter((member, index) => index < FOLDED_MEMBERS || member.key === choice.keep)
    : members;
  const hidden = group.members.length - visible.length;
  return (
    <Card
      withBorder
      padding="sm"
      bg={choice.include ? 'var(--mantine-color-body)' : 'var(--mantine-color-default-hover)'}
    >
      <Group justify="space-between" mb="xs">
        <Group gap="xs">
          <Badge color={REASON_COLOR[group.reason]} variant="light">
            {t(`duplicates.reasons.${group.reason}`)}
          </Badge>
          {!choice.include && (
            <Badge color="gray" variant="outline">
              {t('duplicates.excluded')}
            </Badge>
          )}
          {manual && (
            <Badge color="teal" variant="outline">
              {t('duplicates.chosen')}
            </Badge>
          )}
        </Group>
        <Checkbox
          label={t('duplicates.include')}
          aria-label={t('duplicates.includeGroup', label)}
          checked={choice.include}
          disabled={!editable}
          onChange={(event) => onChange({ include: event.currentTarget.checked })}
        />
      </Group>
      <Radio.Group
        name={name}
        value={choice.keep}
        onChange={(keep) => onChange({ keep })}
        label={t('duplicates.keepGroup', label)}
        size="xs"
      >
        <Table.ScrollContainer minWidth={640}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('duplicates.fields.keep')}</Table.Th>
                <SortableTh state={memberSort} sortKey="document">
                  {t('duplicates.fields.document')}
                </SortableTh>
                <SortableTh state={memberSort} sortKey="size">
                  {t('duplicates.fields.size')}
                </SortableTh>
                <SortableTh state={memberSort} sortKey="modified">
                  {t('duplicates.fields.modified')}
                </SortableTh>
                <SortableTh state={memberSort} sortKey="hash">
                  {t('duplicates.fields.hash')}
                </SortableTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {visible.map((member) => (
                <Table.Tr key={member.key}>
                  <Table.Td>
                    <Radio
                      value={member.key}
                      disabled={!editable}
                      aria-label={t('duplicates.keepMember', { path: member.key })}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Text ff="monospace" size="sm" style={{ wordBreak: 'break-all' }}>
                      {member.key}
                    </Text>
                    {member.output_path && (
                      <Anchor
                        component={Link}
                        to={`/projects/${projectId}/documents/view?path=${encodeURIComponent(member.output_path)}`}
                        size="xs"
                      >
                        {t('duplicates.view')}
                      </Anchor>
                    )}
                  </Table.Td>
                  <Table.Td>{formatBytes(member.size_bytes)}</Table.Td>
                  <Table.Td>{formatDateTime(member.modified_at)}</Table.Td>
                  <Table.Td>
                    <Text ff="monospace" size="xs" title={member.sha256}>
                      {member.sha256.slice(0, 12)}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Radio.Group>
      {hidden > 0 && (
        <Button variant="subtle" size="xs" mt="xs" onClick={() => setExpanded(true)}>
          {t('duplicates.showAll', { count: hidden })}
        </Button>
      )}
    </Card>
  );
}
