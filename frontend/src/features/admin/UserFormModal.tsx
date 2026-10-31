import {
  Alert,
  Button,
  Group,
  Input,
  Modal,
  PasswordInput,
  SegmentedControl,
  Stack,
  Switch,
  TextInput,
} from '@mantine/core';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { zodResolver } from '../../components/forms';
import { PASSWORD_MIN_LENGTH } from '../auth/useAuth';
import { type User, type UserUpdate, useCreateUser, useUpdateUser } from './useAdmin';

const USERNAME_PATTERN = /^[A-Za-z0-9._-]{3,64}$/;

function buildSchema(editing: boolean) {
  return z.object({
    username: editing ? z.string() : z.string().regex(USERNAME_PATTERN, 'admin.users.usernameRule'),
    displayName: z.string().trim().min(1, 'auth.required'),
    role: z.enum(['admin', 'user']),
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
      role: user?.role ?? 'user',
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
      if (values.role !== user.role) body.role = values.role;
      if (values.isActive !== user.is_active) body.is_active = values.isActive;
      if (values.password) body.password = values.password;
      update.mutate({ id: user.id, body }, { onSuccess: onClose });
    } else {
      create.mutate(
        {
          username: values.username,
          display_name: values.displayName,
          password: values.password,
          role: values.role,
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
          <Input.Wrapper label={t('admin.users.role')} id="user-role">
            <Controller
              control={control}
              name="role"
              render={({ field }) => (
                <SegmentedControl
                  fullWidth
                  aria-labelledby="user-role-label"
                  data={[
                    { value: 'user', label: t('roles.user') },
                    { value: 'admin', label: t('roles.admin') },
                  ]}
                  value={field.value}
                  onChange={(value) => field.onChange(value === 'admin' ? 'admin' : 'user')}
                />
              )}
            />
          </Input.Wrapper>
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
