import {
  ActionIcon,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Menu,
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
import { ICON_STROKE, MoreActionsIcon, NAV_ICON_SIZE } from '../../components/icons';
import { useMe } from '../auth/useAuth';
import {
  type User,
  type UserFilters,
  type UserSort,
  type UserStatusFilter,
  useUpdateUser,
  useUsers,
} from './useAdmin';
import { UserBlockModal } from './UserBlockModal';
import { UserDeleteModal } from './UserDeleteModal';
import { UserFormModal } from './UserFormModal';
import { useRoles } from './useTenancy';

type Editing = { user: User | null } | null;
/** Acción del menú de una fila que abre un diálogo (2.7). */
type RowAction = { kind: 'block' | 'delete'; user: User } | null;

/** Bloqueado por intentos fallidos y todavía vigente (la misma regla que el filtro `locked` de la API). */
const isLockedOut = (user: User) => user.locked_until !== null && new Date(user.locked_until) > new Date();

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
  if (isLockedOut(user)) {
    return <Badge color="orange">{t('admin.users.locked')}</Badge>;
  }
  return <Badge color="green">{t('admin.users.activeBadge')}</Badge>;
}

export function UsersPage() {
  const { t } = useTranslation();
  const list = useListState(USER_SORT);
  const [editing, setEditing] = useState<Editing>(null);
  const [action, setAction] = useState<RowAction>(null);
  const unlock = useUpdateUser();
  const { filters, set, clear } = useUserFilters();
  const { data: me } = useMe();
  const roles = useRoles();
  const { data, isPending, isError, error } = useUsers({ ...list.query, ...filters });
  const filtered = Object.keys(filters).length > 0 || list.q.trim() !== '';
  // F0 (2.7): el último admin de instancia activo no se bloquea, ni se borra (el backend lo vuelve a comprobar).
  const isLastAdmin = (user: User) =>
    user.is_instance_admin && user.is_active && data?.active_instance_admins === 1;

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
      {unlock.isError && <ErrorAlert error={unlock.error} />}
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
                    <Group gap="xs" wrap="nowrap">
                      <Button
                        size="xs"
                        variant="light"
                        onClick={() => setEditing({ user })}
                        aria-label={t('admin.users.editLabel', { username: user.username })}
                      >
                        {t('common.edit')}
                      </Button>
                      <Menu position="bottom-end" withinPortal>
                        <Menu.Target>
                          <ActionIcon
                            variant="subtle"
                            aria-label={t('admin.users.actionsLabel', { username: user.username })}
                          >
                            <MoreActionsIcon size={NAV_ICON_SIZE} stroke={ICON_STROKE} aria-hidden />
                          </ActionIcon>
                        </Menu.Target>
                        <Menu.Dropdown>
                          {isLastAdmin(user) && <Menu.Label>{t('admin.users.lastAdmin')}</Menu.Label>}
                          <Menu.Item
                            disabled={isLastAdmin(user) && user.is_active}
                            onClick={() => setAction({ kind: 'block', user })}
                          >
                            {t(user.is_active ? 'admin.users.block.action' : 'admin.users.unblock.action')}
                          </Menu.Item>
                          {isLockedOut(user) && (
                            <Menu.Item onClick={() => unlock.mutate({ id: user.id, body: { unlock: true } })}>
                              {t('admin.users.unlock')}
                            </Menu.Item>
                          )}
                          <Menu.Divider />
                          <Menu.Item
                            color="red"
                            disabled={isLastAdmin(user)}
                            onClick={() => setAction({ kind: 'delete', user })}
                          >
                            {t('admin.users.delete.action')}
                          </Menu.Item>
                        </Menu.Dropdown>
                      </Menu>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {data && <PageControls state={list.paging} total={data.total} label={t('paging.label')} />}
      {action?.kind === 'block' && <UserBlockModal user={action.user} onClose={() => setAction(null)} />}
      {action?.kind === 'delete' && <UserDeleteModal user={action.user} onClose={() => setAction(null)} />}
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
