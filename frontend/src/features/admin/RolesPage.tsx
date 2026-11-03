import {
  Badge,
  Button,
  Card,
  Center,
  Checkbox,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
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

/** Roles del tenant activo con sus permisos (sustituye a `admin_roles.html.j2`). Los base son de solo lectura. */
export function RolesPage() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const roles = useRoles();

  return (
    <Stack>
      <Title order={2}>{t('roles.title', { tenant: me?.acting_tenant.name ?? '' })}</Title>
      <Text c="dimmed">{t('roles.intro')}</Text>
      <NewRole />
      {roles.isPending ? (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      ) : roles.isError ? (
        <ErrorAlert error={roles.error} />
      ) : (
        roles.data.map((role) => <RoleCard key={`${role.id}-${role.updated_at}`} role={role} />)
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

function NewRole() {
  const { t } = useTranslation();
  const create = useCreateRole();
  const [name, setName] = useState('');
  const [permissions, setPermissions] = useState<Permission[]>([]);
  return (
    <Card withBorder component="section" aria-label={t('roles.new')}>
      <Title order={3} size="h4" mb="xs">
        {t('roles.new')}
      </Title>
      <Stack>
        <TextInput
          label={t('roles.name')}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
          maxLength={64}
          maw={320}
        />
        <PermissionBoxes label={t('roles.permissions')} value={permissions} onChange={setPermissions} />
        {create.isError && <ErrorAlert error={create.error} />}
        <Group justify="flex-end">
          <Button
            disabled={!name.trim()}
            loading={create.isPending}
            onClick={() =>
              create.mutate(
                { name: name.trim(), permissions },
                {
                  onSuccess: () => {
                    setName('');
                    setPermissions([]);
                  },
                },
              )
            }
          >
            {t('roles.create')}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}

function RoleCard({ role }: { role: TenantRole }) {
  const { t } = useTranslation();
  const update = useUpdateRole();
  const remove = useDeleteRole();
  const builtin = role.builtin !== null;
  const [name, setName] = useState(role.name);
  const [permissions, setPermissions] = useState<Permission[]>(role.permissions);
  const dirty =
    name.trim() !== role.name ||
    permissions.length !== role.permissions.length ||
    permissions.some((p) => !role.permissions.includes(p));
  const title = builtin ? t(`roles.builtin.${role.builtin}`) : role.name;

  return (
    <Card withBorder component="section" aria-label={title}>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {title}
        </Title>
        <Group gap="xs">
          {builtin && (
            <Badge variant="light" color="gray">
              {t('roles.builtinBadge')}
            </Badge>
          )}
          <Badge variant="light">{t('roles.users', { count: role.users })}</Badge>
        </Group>
      </Group>
      <Stack>
        {!builtin && (
          <TextInput
            label={t('roles.name')}
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            maxLength={64}
            maw={320}
          />
        )}
        <PermissionBoxes
          label={t('roles.permissions')}
          value={permissions}
          onChange={setPermissions}
          disabled={builtin}
        />
        {update.isError && <ErrorAlert error={update.error} />}
        {remove.isError && <ErrorAlert error={remove.error} />}
        {!builtin && (
          <Group justify="flex-end">
            <Button
              color="red"
              variant="light"
              disabled={role.users > 0}
              loading={remove.isPending}
              onClick={() => remove.mutate(role.id)}
              aria-label={t('roles.deleteLabel', { name: role.name })}
              title={role.users > 0 ? t('roles.inUse') : undefined}
            >
              {t('common.delete')}
            </Button>
            <Button
              disabled={!dirty || !name.trim()}
              loading={update.isPending}
              onClick={() => update.mutate({ id: role.id, name: name.trim(), permissions })}
              aria-label={t('roles.saveLabel', { name: role.name })}
            >
              {t('common.save')}
            </Button>
          </Group>
        )}
      </Stack>
    </Card>
  );
}
