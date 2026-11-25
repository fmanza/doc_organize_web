import {
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { PageControls } from '../../components/Paging';
import { SearchBox, SortableTh } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { useMe } from '../auth/useAuth';
import { type User, type UserFilters, type UserSort, type UserStatusFilter, useUsers } from './useAdmin';
import { UserFormModal } from './UserFormModal';
import { useRoles } from './useTenancy';

type Editing = { user: User | null } | null;

const USER_SORT: readonly UserSort[] = ['username', 'display_name', 'role', 'status', 'created_at'];
const USER_STATUSES: readonly UserStatusFilter[] = ['active', 'inactive', 'locked'];
const STATUS_LABELS: Readonly<Record<UserStatusFilter, string>> = {
  active: 'admin.users.activeBadge',
  inactive: 'admin.users.inactive',
  locked: 'admin.users.locked',
};

/** Filtros de la lista (2.7) en la URL (`?role=&status=&instance_admin=1`), como la búsqueda y el orden. */
function useUserFilters() {
  const [params, setParams] = useSearchParams();
  const role = Number(params.get('role'));
  const status = params.get('status');
  const filters: UserFilters = {
    ...(Number.isInteger(role) && role > 0 ? { role_id: role } : {}),
    ...(USER_STATUSES.find((s) => s === status) ? { status: status as UserStatusFilter } : {}),
    ...(params.get('instance_admin') === '1' ? { instance_admin: true } : {}),
  };
  const set = (key: 'role' | 'status' | 'instance_admin', value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.delete('page'); // otro filtro: de vuelta a la página 1
    setParams(next, { preventScrollReset: true, replace: true });
  };
  const clear = () => {
    const next = new URLSearchParams(params);
    for (const key of ['role', 'status', 'instance_admin', 'q', 'page']) {
      next.delete(key);
    }
    setParams(next, { preventScrollReset: true, replace: true });
  };
  return { filters, set, clear };
}

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
  const { filters, set, clear } = useUserFilters();
  const { data: me } = useMe();
  const roles = useRoles();
  const { data, isPending, isError, error } = useUsers({ ...list.query, ...filters });
  const filtered = Object.keys(filters).length > 0 || list.q.trim() !== '';

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('admin.users.title')}</Title>
        <Button onClick={() => setEditing({ user: null })}>{t('admin.users.new')}</Button>
      </Group>
      <Group align="flex-end" wrap="wrap">
        <SearchBox value={list.q} onChange={list.setQ} label={t('admin.users.search')} />
        <Select
          label={t('admin.users.filter.role')}
          data={[
            { value: '', label: t('admin.users.filter.all') },
            ...(roles.data ?? []).map((role) => ({
              value: String(role.id),
              label: role.builtin ? t(`roles.builtin.${role.builtin}`) : role.name,
            })),
          ]}
          value={filters.role_id ? String(filters.role_id) : ''}
          onChange={(value) => set('role', value)}
          allowDeselect={false}
          w={200}
        />
        <Select
          label={t('admin.users.filter.status')}
          data={[
            { value: '', label: t('admin.users.filter.all') },
            ...USER_STATUSES.map((value) => ({ value, label: t(STATUS_LABELS[value]) })),
          ]}
          value={filters.status ?? ''}
          onChange={(value) => set('status', value)}
          allowDeselect={false}
          w={180}
        />
        {me?.is_instance_admin && (
          <Switch
            label={t('admin.users.filter.instanceAdmin')}
            checked={filters.instance_admin === true}
            onChange={(event) => set('instance_admin', event.currentTarget.checked ? '1' : null)}
            mb={8}
          />
        )}
      </Group>
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && data.items.length === 0 && (
        <Group>
          <Text c="dimmed">{t(filtered ? 'admin.users.filter.empty' : 'admin.users.empty')}</Text>
          {filtered && (
            <Button size="xs" variant="subtle" onClick={clear}>
              {t('admin.users.filter.clear')}
            </Button>
          )}
        </Group>
      )}
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
