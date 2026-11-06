import {
  Badge,
  Button,
  Center,
  Checkbox,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { formatDateTime } from '../../components/format';
import { SearchBox, SortableTh } from '../../components/listing';
import { useClientTable } from '../../components/useListState';
import { can, useMe } from '../auth/useAuth';
import {
  type Permission,
  PERMISSIONS,
  type TenantRole,
  useCreateRole,
  useDeleteRole,
  useRoles,
  useUpdateRole,
} from './useTenancy';

type RoleSort = 'name' | 'type' | 'permissions' | 'users' | 'updated_at';
type Editing = { role: TenantRole | null } | null;

/**
 * Roles del tenant activo (web 1.2.0: como Usuarios): listado con búsqueda, orden y 25 filas, «Nuevo rol» y, en cada
 * fila, «Editar» (o «Ver» en los predeterminados, que son de solo lectura).
 */
export function RolesPage() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const roles = useRoles();
  const [editing, setEditing] = useState<Editing>(null);
  const roleName = (role: TenantRole) => (role.builtin ? t(`roles.builtin.${role.builtin}`) : role.name);
  const table = useClientTable<TenantRole, RoleSort>(
    roles.data,
    {
      name: roleName,
      // Primero los predeterminados en orden ascendente.
      type: (role) => (role.builtin ? 0 : 1),
      permissions: (role) => role.permissions.length,
      users: (role) => role.users,
      updated_at: (role) => role.updated_at,
    },
    (role) => `${roleName(role)} ${role.permissions.map((p) => t(`permissions.${p}.label`)).join(' ')}`,
  );

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('roles.title', { tenant: me?.acting_tenant.name ?? '' })}</Title>
        <Button onClick={() => setEditing({ role: null })}>{t('roles.new')}</Button>
      </Group>
      <Text c="dimmed">{t('roles.intro')}</Text>
      <SearchBox value={table.q} onChange={table.setQ} label={t('roles.search')} />
      {roles.isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {roles.isError && <ErrorAlert error={roles.error} />}
      {roles.data && table.total === 0 && <Text c="dimmed">{t('listing.empty')}</Text>}
      {roles.data && table.total > 0 && (
        <Table.ScrollContainer minWidth={720}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <SortableTh state={table} sortKey="name">
                  {t('roles.name')}
                </SortableTh>
                <SortableTh state={table} sortKey="type">
                  {t('roles.type')}
                </SortableTh>
                <SortableTh state={table} sortKey="permissions">
                  {t('roles.permissions')}
                </SortableTh>
                <SortableTh state={table} sortKey="users">
                  {t('roles.usersColumn')}
                </SortableTh>
                <SortableTh state={table} sortKey="updated_at">
                  {t('roles.updatedAt')}
                </SortableTh>
                <Table.Th>
                  <VisuallyHidden>{t('common.actions')}</VisuallyHidden>
                </Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {table.pageRows.map((role) => (
                <Table.Tr key={role.id}>
                  <Table.Td>{roleName(role)}</Table.Td>
                  <Table.Td>
                    {role.builtin ? (
                      <Badge variant="light" color="gray">
                        {t('roles.builtinBadge')}
                      </Badge>
                    ) : (
                      <Badge variant="outline" color="blue">
                        {t('roles.custom')}
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Tooltip
                      multiline
                      w={300}
                      label={
                        role.permissions.length
                          ? role.permissions.map((p) => t(`permissions.${p}.label`)).join(' · ')
                          : t('roles.noPermissions')
                      }
                    >
                      <Text size="sm" span>
                        {t('roles.permissionCount', { count: role.permissions.length })}
                      </Text>
                    </Tooltip>
                  </Table.Td>
                  <Table.Td>{role.users}</Table.Td>
                  <Table.Td>{formatDateTime(role.updated_at)}</Table.Td>
                  <Table.Td>
                    <Button
                      size="xs"
                      variant="light"
                      onClick={() => setEditing({ role })}
                      aria-label={t(role.builtin ? 'roles.viewLabel' : 'roles.editLabel', {
                        name: roleName(role),
                      })}
                    >
                      {t(role.builtin ? 'common.view' : 'common.edit')}
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {roles.data && <PageControls state={table.paging} total={table.total} label={t('paging.label')} />}
      {editing && (
        <RoleFormModal key={editing.role?.id ?? 'new'} role={editing.role} onClose={() => setEditing(null)} />
      )}
    </Stack>
  );
}

function PermissionBoxes({
  value,
  onChange,
  disabled,
  label,
}: {
  value: Permission[];
  onChange: (next: Permission[]) => void;
  disabled?: boolean;
  label: string;
}) {
  const { t } = useTranslation();
  const { data: me } = useMe();
  return (
    <Checkbox.Group label={label} value={value} onChange={(next) => onChange(next as Permission[])}>
      <SimpleGrid cols={{ base: 1, sm: 2 }} mt="xs">
        {PERMISSIONS.map((permission) => (
          <Checkbox
            key={permission}
            value={permission}
            label={t(`permissions.${permission}.label`)}
            description={t(`permissions.${permission}.hint`)}
            // Nadie da un permiso que no tiene (la API devuelve 403 igualmente).
            disabled={disabled || !can(me, permission)}
          />
        ))}
      </SimpleGrid>
    </Checkbox.Group>
  );
}

/** Crear (`role` nulo), editar o ver (predeterminado: solo lectura) un rol; borrar uno personalizado sin usuarios. */
function RoleFormModal({ role, onClose }: { role: TenantRole | null; onClose: () => void }) {
  const { t } = useTranslation();
  const create = useCreateRole();
  const update = useUpdateRole();
  const remove = useDeleteRole();
  const builtin = role?.builtin != null;
  const [name, setName] = useState(role?.name ?? '');
  const [permissions, setPermissions] = useState<Permission[]>(role?.permissions ?? []);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const modalTitle = () => {
    if (!role) {
      return t('roles.new');
    }
    return role.builtin ? t(`roles.builtin.${role.builtin}`) : t('roles.editTitle', { name: role.name });
  };
  const title = modalTitle();
  const dirty =
    !role ||
    name.trim() !== role.name ||
    permissions.length !== role.permissions.length ||
    permissions.some((p) => !role.permissions.includes(p));
  const save = () => {
    const body = { name: name.trim(), permissions };
    if (role) {
      update.mutate({ id: role.id, ...body }, { onSuccess: onClose });
    } else {
      create.mutate(body, { onSuccess: onClose });
    }
  };
  const error = create.error ?? update.error ?? remove.error;

  return (
    <Modal opened onClose={onClose} title={title} size="lg">
      <Stack>
        {builtin && <Text size="sm">{t('roles.builtinReadOnly')}</Text>}
        {!builtin && (
          <TextInput
            label={t('roles.name')}
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            maxLength={64}
            data-autofocus
          />
        )}
        <PermissionBoxes
          label={t('roles.permissions')}
          value={permissions}
          onChange={setPermissions}
          disabled={builtin}
        />
        {role && <Text size="sm">{t('roles.users', { count: role.users })}</Text>}
        {error && <ErrorAlert error={error} />}
        {confirmDelete && role ? (
          <Stack gap="xs">
            <Text c="red" fw={500}>
              {t('roles.confirmDelete', { name: role.name })}
            </Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setConfirmDelete(false)}>
                {t('common.cancel')}
              </Button>
              <Button
                color="red"
                loading={remove.isPending}
                onClick={() => remove.mutate(role.id, { onSuccess: onClose })}
              >
                {t('common.delete')}
              </Button>
            </Group>
          </Stack>
        ) : (
          <Group justify="space-between">
            {role && !builtin ? (
              <Button
                color="red"
                variant="light"
                disabled={role.users > 0}
                title={role.users > 0 ? t('roles.inUse') : undefined}
                onClick={() => setConfirmDelete(true)}
                aria-label={t('roles.deleteLabel', { name: role.name })}
              >
                {t('common.delete')}
              </Button>
            ) : (
              <span />
            )}
            <Group>
              <Button variant="default" onClick={onClose}>
                {builtin ? t('common.close') : t('common.cancel')}
              </Button>
              {!builtin && (
                <Button
                  disabled={!dirty || !name.trim()}
                  loading={create.isPending || update.isPending}
                  onClick={save}
                >
                  {role ? t('common.save') : t('roles.create')}
                </Button>
              )}
            </Group>
          </Group>
        )}
        {role && !builtin && role.users > 0 && (
          <Text size="xs" c="dimmed">
            {t('roles.inUse')}
          </Text>
        )}
      </Stack>
    </Modal>
  );
}
