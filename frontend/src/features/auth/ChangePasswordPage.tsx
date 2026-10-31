import { Alert, Button, PasswordInput, Stack, Text, Title } from '@mantine/core';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { ErrorAlert } from '../../components/ErrorAlert';
import { zodResolver } from '../../components/forms';
import { PASSWORD_MIN_LENGTH, useChangePassword } from './useAuth';

const schema = z
  .object({
    current: z.string().min(1, 'auth.required'),
    next: z.string().min(PASSWORD_MIN_LENGTH, 'auth.passwordTooShort'),
    confirm: z.string(),
  })
  .refine((values) => values.confirm === values.next, {
    path: ['confirm'],
    message: 'auth.passwordMismatch',
  });
type PasswordForm = z.infer<typeof schema>;

export function ChangePasswordPage() {
  const { t } = useTranslation();
  const change = useChangePassword();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PasswordForm>({
    resolver: zodResolver(schema),
    defaultValues: { current: '', next: '', confirm: '' },
  });
  const message = (key: string | undefined) => key && t(key, { min: PASSWORD_MIN_LENGTH });

  const onSubmit = handleSubmit((values) => {
    change.mutate(
      { current_password: values.current, new_password: values.next },
      { onSuccess: () => reset() },
    );
  });

  return (
    <Stack maw={480}>
      <Title order={2}>{t('auth.changePassword')}</Title>
      <Text c="dimmed">{t('auth.changePasswordIntro')}</Text>
      {change.isSuccess && (
        <Alert color="green" role="status" title={t('auth.passwordChanged')}>
          {t('auth.passwordChangedBody')}
        </Alert>
      )}
      {change.isError && <ErrorAlert error={change.error} />}
      <form onSubmit={(event) => void onSubmit(event)} noValidate>
        <Stack>
          <PasswordInput
            label={t('auth.currentPassword')}
            autoComplete="current-password"
            required
            error={message(errors.current?.message)}
            {...register('current')}
          />
          <PasswordInput
            label={t('auth.newPassword')}
            description={t('auth.passwordHint', { min: PASSWORD_MIN_LENGTH })}
            autoComplete="new-password"
            required
            error={message(errors.next?.message)}
            {...register('next')}
          />
          <PasswordInput
            label={t('auth.confirmPassword')}
            autoComplete="new-password"
            required
            error={message(errors.confirm?.message)}
            {...register('confirm')}
          />
          <Button type="submit" loading={change.isPending} w="fit-content">
            {t('auth.changePassword')}
          </Button>
        </Stack>
      </form>
    </Stack>
  );
}
