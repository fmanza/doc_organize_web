import {
  Badge,
  Button,
  Center,
  Code,
  Loader,
  Group,
  SegmentedControl,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PageControls } from '../../components/Paging';
import { ClearSection, SearchBox, SortableTh } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { useMe } from '../auth/useAuth';
import { AuditPurgeModal } from './AuditPurgeModal';
import { type AuditSort, useAudit } from './useAdmin';

const AUDIT_SORT: readonly AuditSort[] = ['ts', 'action', 'outcome', 'actor', 'target', 'ip'];

// Filtro por prefijo de acción (`auth.login`, `user.create`…).
const ACTION_FILTERS = [
  { value: '', key: 'all' },
  { value: 'auth.', key: 'auth' },
  { value: 'user.', key: 'user' },
  { value: 'session.', key: 'session' },
] as const;

export function AuditPage() {
  const { t } = useTranslation();
  const [action, setAction] = useState('');
  const [actor, setActor] = useState('');
  const list = useListState(AUDIT_SORT);
  const { paging } = list;
  const { data: me } = useMe();
  const [purging, setPurging] = useState(false);
  const { data, isPending, isError, error } = useAudit(action, actor.trim(), list.query);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('admin.audit.title')}</Title>
        {/* Solo el admin de instancia borra auditoría (la API lo exige igualmente). */}
        {me?.is_instance_admin && (
          <Button color="red" variant="light" onClick={() => setPurging(true)}>
            {t('admin.audit.purge.open')}
          </Button>
        )}
      </Group>
      <Group align="flex-end">
        <Stack gap={4}>
          <Text size="sm" fw={500} id="audit-filter-label">
            {t('admin.audit.filter')}
          </Text>
          <SegmentedControl
            aria-labelledby="audit-filter-label"
            data={ACTION_FILTERS.map(({ value, key }) => ({ value, label: t(`admin.audit.filters.${key}`) }))}
            value={action}
            onChange={(value) => {
              setAction(value);
              paging.setPage(1, true);
            }}
            w="fit-content"
          />
        </Stack>
        <TextInput
          label={t('admin.audit.actorFilter')}
          value={actor}
          onChange={(event) => {
            setActor(event.currentTarget.value);
            paging.setPage(1, true);
          }}
          maw={240}
          rightSectionPointerEvents="auto"
          rightSection={
            <ClearSection
              text={actor}
              onClear={() => {
                setActor('');
                paging.setPage(1, true);
              }}
            />
          }
        />
        <SearchBox value={list.q} onChange={list.setQ} label={t('admin.audit.search')} />
      </Group>
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && data.items.length === 0 && <Text c="dimmed">{t('admin.audit.empty')}</Text>}
      {data && data.items.length > 0 && (
        <Table.ScrollContainer minWidth={820}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <SortableTh state={list} sortKey="ts">
                  {t('admin.audit.ts')}
                </SortableTh>
                <SortableTh state={list} sortKey="action">
                  {t('admin.audit.action')}
                </SortableTh>
                <SortableTh state={list} sortKey="outcome">
                  {t('admin.audit.outcome')}
                </SortableTh>
                <SortableTh state={list} sortKey="actor">
                  {t('admin.audit.actor')}
                </SortableTh>
                <SortableTh state={list} sortKey="target">
                  {t('admin.audit.target')}
                </SortableTh>
                <SortableTh state={list} sortKey="ip">
                  {t('admin.sessions.ip')}
                </SortableTh>
                <Table.Th>{t('admin.audit.details')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.items.map((entry) => (
                <Table.Tr key={entry.id}>
                  <Table.Td>{formatDateTime(entry.ts)}</Table.Td>
                  <Table.Td>
                    {t(`admin.audit.actions.${entry.action}`, { defaultValue: entry.action })}
                  </Table.Td>
                  <Table.Td>
                    <Badge color={entry.outcome === 'success' ? 'green' : 'red'} variant="light">
                      {t(`admin.audit.outcomes.${entry.outcome}`, { defaultValue: entry.outcome })}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{entry.actor_username ?? t('admin.audit.system')}</Table.Td>
                  <Table.Td>
                    {entry.target_type ? `${entry.target_type} #${entry.target_id ?? ''}` : '—'}
                  </Table.Td>
                  <Table.Td>{entry.ip ?? '—'}</Table.Td>
                  <Table.Td>{entry.details ? <Code>{JSON.stringify(entry.details)}</Code> : '—'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {data && <PageControls state={paging} total={data.total} label={t('paging.label')} />}
      {purging && <AuditPurgeModal onClose={() => setPurging(false)} />}
    </Stack>
  );
}
