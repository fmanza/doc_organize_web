import {
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PageControls } from '../../components/Paging';
import { SearchBox, SortableTh } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { can, useMe } from '../auth/useAuth';
import { type SessionInfo, type SessionSort, useRevokeSession, useSessions } from './useAdmin';

const SESSION_SORT: readonly SessionSort[] = [
  'username',
  'ip',
  'user_agent',
  'created_at',
  'last_seen_at',
  'expires_at',
];

export function SessionsPage() {
  const { t } = useTranslation();
  // Quien gestiona usuarios ve las de su tenant; el resto, solo las suyas (la API filtra igualmente).
  const { data: me } = useMe();
  const scope = can(me, 'users.manage') ? 'all' : 'own';
  const list = useListState(SESSION_SORT);
  const [revoking, setRevoking] = useState<SessionInfo | null>(null);
  const { data, isPending, isError, error } = useSessions(list.query);
  const revoke = useRevokeSession();

  const close = () => {
    setRevoking(null);
    revoke.reset();
  };

  return (
    <Stack>
      <Title order={2}>{t(`admin.sessions.title.${scope}`)}</Title>
      <Text c="dimmed">{t(`admin.sessions.intro.${scope}`)}</Text>
      <SearchBox value={list.q} onChange={list.setQ} label={t('admin.sessions.search')} />
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && data.items.length === 0 && <Text c="dimmed">{t('admin.sessions.empty')}</Text>}
      {data && data.items.length > 0 && (
        <Table.ScrollContainer minWidth={820}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <SortableTh state={list} sortKey="username">
                  {t('auth.username')}
                </SortableTh>
                <SortableTh state={list} sortKey="ip">
                  {t('admin.sessions.ip')}
                </SortableTh>
                <SortableTh state={list} sortKey="user_agent">
                  {t('admin.sessions.userAgent')}
                </SortableTh>
                <SortableTh state={list} sortKey="created_at">
                  {t('admin.sessions.createdAt')}
                </SortableTh>
                <SortableTh state={list} sortKey="last_seen_at">
                  {t('admin.sessions.lastSeen')}
                </SortableTh>
                <SortableTh state={list} sortKey="expires_at">
                  {t('admin.sessions.expiresAt')}
                </SortableTh>
                <Table.Th>
                  <VisuallyHidden>{t('common.actions')}</VisuallyHidden>
                </Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.items.map((session) => (
                <Table.Tr key={session.id}>
                  <Table.Td>
                    <Group gap="xs">
                      {session.username}
                      {session.current && (
                        <Badge size="xs" variant="light">
                          {t('admin.sessions.current')}
                        </Badge>
                      )}
                    </Group>
                  </Table.Td>
                  <Table.Td>{session.ip ?? '—'}</Table.Td>
                  <Table.Td>
                    <Text size="xs" lineClamp={1} title={session.user_agent ?? undefined}>
                      {session.user_agent ?? '—'}
                    </Text>
                  </Table.Td>
                  <Table.Td>{formatDateTime(session.created_at)}</Table.Td>
                  <Table.Td>{formatDateTime(session.last_seen_at)}</Table.Td>
                  <Table.Td>{formatDateTime(session.expires_at)}</Table.Td>
                  <Table.Td>
                    <Button
                      size="xs"
                      color="red"
                      variant="light"
                      onClick={() => setRevoking(session)}
                      aria-label={t('admin.sessions.revokeLabel', { username: session.username })}
                    >
                      {t('admin.sessions.revoke')}
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {data && <PageControls state={list.paging} total={data.total} label={t('paging.label')} />}
      <Modal opened={revoking !== null} onClose={close} title={t('admin.sessions.confirmTitle')}>
        {revoking && (
          <Stack>
            <Text>
              {t('admin.sessions.confirmBody', { username: revoking.username, ip: revoking.ip ?? '—' })}
            </Text>
            {revoking.current && (
              <Text c="orange" fw={500}>
                {t('admin.sessions.confirmCurrent')}
              </Text>
            )}
            {revoke.isError && <ErrorAlert error={revoke.error} />}
            <Group justify="flex-end">
              <Button variant="default" onClick={close}>
                {t('common.cancel')}
              </Button>
              <Button
                color="red"
                loading={revoke.isPending}
                onClick={() => revoke.mutate(revoking, { onSuccess: close })}
              >
                {t('admin.sessions.revoke')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
