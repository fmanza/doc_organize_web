import { Alert, Button, Group, Modal, PasswordInput, Select, Stack, Switch, TextInput } from '@mantine/core';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { zodResolver } from '../../components/forms';
import { PASSWORD_MIN_LENGTH, useMe } from '../auth/useAuth';
import { type User, type UserUpdate, useCreateUser, useUpdateUser } from './useAdmin';
import { useRoles, useTenants } from './useTenancy';

const USERNAME_PATTERN = /^[A-Za-z0-9._-]{3,64}$/;

function buildSchema(editing: boolean) {
  return z.object({
    username: editing ? z.string() : z.string().regex(USERNAME_PATTERN, 'admin.users.usernameRule'),
    displayName: z.string().trim().min(1, 'auth.required'),
    roleId: z.string().nullable(),
    instanceAdmin: z.boolean(),
    tenantId: z.string().nullable(),
    isActive: z.boolean(),
    unlock: z.boolean(),
    // Al editar, vacía significa «no cambiarla».
    password: editing
      ? z
          .string()
          .refine((value) => value === '' || value.length >= PASSWORD_MIN_LENGTH, 'auth.passwordTooShort')
      : z.string().min(PASSWORD_MIN_LENGTH, 'auth.passwordTooShort'),
  });
}
type UserForm = z.infer<ReturnType<typeof buildSchema>>;

interface UserFormModalProps {
  /** Usuario a editar; `null` para crear uno nuevo. */
  user: User | null;
  opened: boolean;
  onClose: () => void;
}

/** Alta y edición de usuario. Se monta con `key` distinta por usuario para reiniciar el estado. */
export function UserFormModal({ user, opened, onClose }: UserFormModalProps) {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const instance = !!me?.is_instance_admin;
  const roles = useRoles();
  const tenants = useTenants(instance && user !== null);
  const create = useCreateUser();
  const update = useUpdateUser();
  const mutation = user ? update : create;
  const locked = user?.locked_until != null && new Date(user.locked_until) > new Date();
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<UserForm>({
    resolver: zodResolver(buildSchema(user !== null)),
    defaultValues: {
      username: '',
      displayName: user?.display_name ?? '',
      roleId: user ? String(user.role.id) : null,
      instanceAdmin: user?.is_instance_admin ?? false,
      tenantId: user ? String(user.tenant_id) : null,
      isActive: user?.is_active ?? true,
      unlock: false,
      password: '',
    },
  });
  const message = (key: string | undefined) => key && t(key, { min: PASSWORD_MIN_LENGTH });

  const onSubmit = handleSubmit((values) => {
    if (user) {
      const body: UserUpdate = { unlock: values.unlock };
      if (values.displayName !== user.display_name) body.display_name = values.displayName;
      const moving = values.tenantId !== null && Number(values.tenantId) !== user.tenant_id;
      if (moving) body.tenant_id = Number(values.tenantId);
      else if (values.roleId !== null && Number(values.roleId) !== user.role.id)
        body.role_id = Number(values.roleId);
      if (values.instanceAdmin !== user.is_instance_admin) body.is_instance_admin = values.instanceAdmin;
      if (values.isActive !== user.is_active) body.is_active = values.isActive;
      if (values.password) body.password = values.password;
      update.mutate({ id: user.id, body }, { onSuccess: onClose });
    } else {
      create.mutate(
        {
          username: values.username,
          display_name: values.displayName,
          password: values.password,
          role_id: values.roleId === null ? null : Number(values.roleId),
          is_instance_admin: values.instanceAdmin,
        },
        { onSuccess: onClose },
      );
    }
  });

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={user ? t('admin.users.editTitle', { username: user.username }) : t('admin.users.createTitle')}
    >
      <form onSubmit={(event) => void onSubmit(event)} noValidate>
        <Stack>
          {mutation.isError && <ErrorAlert error={mutation.error} />}
          {!user && (
            <TextInput
              label={t('auth.username')}
              description={t('admin.users.usernameRule')}
              autoComplete="off"
              required
              error={message(errors.username?.message)}
              data-autofocus
              {...register('username')}
            />
          )}
          <TextInput
            label={t('admin.users.displayName')}
            required
            error={message(errors.displayName?.message)}
            {...register('displayName')}
          />
          <Controller
            control={control}
            name="roleId"
            render={({ field }) => (
              <Select
                label={t('admin.users.role')}
                description={t('admin.users.roleHint')}
                data={(roles.data ?? []).map((role) => ({
                  value: String(role.id),
                  label: role.builtin ? t(`roles.builtin.${role.builtin}`) : role.name,
                }))}
                value={field.value}
                onChange={field.onChange}
                placeholder={t('roles.builtin.user')}
                allowDeselect={false}
              />
            )}
          />
          {roles.isError && <ErrorAlert error={roles.error} />}
          {instance && (
            <Controller
              control={control}
              name="instanceAdmin"
              render={({ field }) => (
                <Switch
                  label={t('admin.users.instanceAdmin')}
                  description={t('admin.users.instanceAdminHint')}
                  checked={field.value}
                  onChange={(event) => field.onChange(event.currentTarget.checked)}
                />
              )}
            />
          )}
          {instance && user && (
            <Controller
              control={control}
              name="tenantId"
              render={({ field }) => (
                <Select
                  label={t('admin.users.tenant')}
                  description={t('admin.users.tenantHint')}
                  data={(tenants.data?.items ?? []).map((tenant) => ({
                    value: String(tenant.id),
                    label: tenant.name,
                  }))}
                  value={field.value}
                  onChange={field.onChange}
                  allowDeselect={false}
                />
              )}
            />
          )}
          {user && (
            <Controller
              control={control}
              name="isActive"
              render={({ field }) => (
                <Switch
                  label={t('admin.users.active')}
                  description={t('admin.users.activeHint')}
                  checked={field.value}
                  onChange={(event) => field.onChange(event.currentTarget.checked)}
                />
              )}
            />
          )}
          {user && locked && (
            <Alert color="orange" title={t('admin.users.lockedTitle')}>
              <Stack gap="xs">
                {t('admin.users.lockedBody', { until: formatDateTime(user.locked_until) })}
                <Controller
                  control={control}
                  name="unlock"
                  render={({ field }) => (
                    <Switch
                      label={t('admin.users.unlock')}
                      checked={field.value}
                      onChange={(event) => field.onChange(event.currentTarget.checked)}
                    />
                  )}
                />
              </Stack>
            </Alert>
          )}
          <PasswordInput
            label={user ? t('admin.users.resetPassword') : t('auth.password')}
            description={
              user ? t('admin.users.resetPasswordHint') : t('auth.passwordHint', { min: PASSWORD_MIN_LENGTH })
            }
            autoComplete="new-password"
            required={!user}
            error={message(errors.password?.message)}
            {...register('password')}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              {user ? t('common.save') : t('admin.users.create')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
