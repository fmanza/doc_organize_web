import {
  Badge,
  Center,
  Code,
  Loader,
  Pagination,
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

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { PAGE_SIZE, useAudit } from './useAdmin';

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
  const [page, setPage] = useState(1);
  const { data, isPending, isError, error } = useAudit(action, actor.trim(), page);

  return (
    <Stack>
      <Title order={2}>{t('admin.audit.title')}</Title>
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
              setPage(1);
            }}
            w="fit-content"
          />
        </Stack>
        <TextInput
          label={t('admin.audit.actorFilter')}
          value={actor}
          onChange={(event) => {
            setActor(event.currentTarget.value);
            setPage(1);
          }}
          maw={240}
        />
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
                <Table.Th>{t('admin.audit.ts')}</Table.Th>
                <Table.Th>{t('admin.audit.action')}</Table.Th>
                <Table.Th>{t('admin.audit.outcome')}</Table.Th>
                <Table.Th>{t('admin.audit.actor')}</Table.Th>
                <Table.Th>{t('admin.audit.target')}</Table.Th>
                <Table.Th>{t('admin.sessions.ip')}</Table.Th>
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
      {data && data.total > PAGE_SIZE && (
        <Pagination total={Math.ceil(data.total / PAGE_SIZE)} value={page} onChange={setPage} />
      )}
    </Stack>
  );
}
