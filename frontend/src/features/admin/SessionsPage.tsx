import {
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Pagination,
  Stack,
  Table,
  Text,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { useMe } from '../auth/useAuth';
import { PAGE_SIZE, type SessionInfo, useRevokeSession, useSessions } from './useAdmin';

export function SessionsPage() {
  const { t } = useTranslation();
  // Un admin ve las sesiones de todos; un usuario, solo las suyas (la API filtra igualmente).
  const { data: me } = useMe();
  const scope = me?.role === 'admin' ? 'all' : 'own';
  const [page, setPage] = useState(1);
  const [revoking, setRevoking] = useState<SessionInfo | null>(null);
  const { data, isPending, isError, error } = useSessions(page);
  const revoke = useRevokeSession();

  const close = () => {
    setRevoking(null);
    revoke.reset();
  };

  return (
    <Stack>
      <Title order={2}>{t(`admin.sessions.title.${scope}`)}</Title>
      <Text c="dimmed">{t(`admin.sessions.intro.${scope}`)}</Text>
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
                <Table.Th>{t('auth.username')}</Table.Th>
                <Table.Th>{t('admin.sessions.ip')}</Table.Th>
                <Table.Th>{t('admin.sessions.userAgent')}</Table.Th>
                <Table.Th>{t('admin.sessions.createdAt')}</Table.Th>
                <Table.Th>{t('admin.sessions.lastSeen')}</Table.Th>
                <Table.Th>{t('admin.sessions.expiresAt')}</Table.Th>
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
      {data && data.total > PAGE_SIZE && (
        <Pagination total={Math.ceil(data.total / PAGE_SIZE)} value={page} onChange={setPage} />
      )}
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
