import {
  Badge,
  Button,
  Center,
  Group,
  Loader,
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
import { type User, type UserSort, useUsers } from './useAdmin';
import { UserFormModal } from './UserFormModal';

type Editing = { user: User | null } | null;

const USER_SORT: readonly UserSort[] = ['username', 'display_name', 'role', 'status', 'created_at'];

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
  const list = useListState(USER_SORT);
  const [editing, setEditing] = useState<Editing>(null);
  const { data, isPending, isError, error } = useUsers(list.query);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('admin.users.title')}</Title>
        <Button onClick={() => setEditing({ user: null })}>{t('admin.users.new')}</Button>
      </Group>
      <SearchBox value={list.q} onChange={list.setQ} label={t('admin.users.search')} />
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
                <SortableTh state={list} sortKey="username">
                  {t('auth.username')}
                </SortableTh>
                <SortableTh state={list} sortKey="display_name">
                  {t('admin.users.displayName')}
                </SortableTh>
                <SortableTh state={list} sortKey="role">
                  {t('admin.users.role')}
                </SortableTh>
                <SortableTh state={list} sortKey="status">
                  {t('admin.users.status')}
                </SortableTh>
                <SortableTh state={list} sortKey="created_at">
                  {t('admin.users.createdAt')}
                </SortableTh>
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
                  <Table.Td>
                    {user.role.builtin ? t(`roles.builtin.${user.role.builtin}`) : user.role.name}
                    {user.is_instance_admin && (
                      <Badge ml="xs" size="xs" variant="light">
                        {t('roles.instanceAdmin')}
                      </Badge>
                    )}
                  </Table.Td>
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
      {data && <PageControls state={list.paging} total={data.total} label={t('paging.label')} />}
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
