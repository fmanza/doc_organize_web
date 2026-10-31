import {
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Pagination,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { PAGE_SIZE, type User, useUsers } from './useAdmin';
import { UserFormModal } from './UserFormModal';

type Editing = { user: User | null } | null;

function UserStatus({ user }: { user: User }) {
  const { t } = useTranslation();
  if (!user.is_active) {
    return <Badge color="gray">{t('admin.users.inactive')}</Badge>;
  }
  if (user.locked_until && new Date(user.locked_until) > new Date()) {
    return <Badge color="orange">{t('admin.users.locked')}</Badge>;
  }
  return <Badge color="green">{t('admin.users.activeBadge')}</Badge>;
}

export function UsersPage() {
  const { t } = useTranslation();
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Editing>(null);
  const { data, isPending, isError, error } = useUsers(q.trim(), page);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('admin.users.title')}</Title>
        <Button onClick={() => setEditing({ user: null })}>{t('admin.users.new')}</Button>
      </Group>
      <TextInput
        label={t('admin.users.search')}
        value={q}
        onChange={(event) => {
          setQ(event.currentTarget.value);
          setPage(1);
        }}
        maw={320}
      />
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && data.items.length === 0 && <Text c="dimmed">{t('admin.users.empty')}</Text>}
      {data && data.items.length > 0 && (
        <Table.ScrollContainer minWidth={720}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('auth.username')}</Table.Th>
                <Table.Th>{t('admin.users.displayName')}</Table.Th>
                <Table.Th>{t('admin.users.role')}</Table.Th>
                <Table.Th>{t('admin.users.status')}</Table.Th>
                <Table.Th>{t('admin.users.createdAt')}</Table.Th>
                <Table.Th>
                  <VisuallyHidden>{t('common.actions')}</VisuallyHidden>
                </Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.items.map((user) => (
                <Table.Tr key={user.id}>
                  <Table.Td>{user.username}</Table.Td>
                  <Table.Td>{user.display_name}</Table.Td>
                  <Table.Td>{t(`roles.${user.role}`)}</Table.Td>
                  <Table.Td>
                    <UserStatus user={user} />
                  </Table.Td>
                  <Table.Td>{formatDateTime(user.created_at)}</Table.Td>
                  <Table.Td>
                    <Button
                      size="xs"
                      variant="light"
                      onClick={() => setEditing({ user })}
                      aria-label={t('admin.users.editLabel', { username: user.username })}
                    >
                      {t('common.edit')}
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
      {editing && (
        <UserFormModal
          key={editing.user?.id ?? 'new'}
          user={editing.user}
          opened
          onClose={() => setEditing(null)}
        />
      )}
    </Stack>
  );
}
