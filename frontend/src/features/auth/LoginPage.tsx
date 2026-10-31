import { Button, Center, Paper, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Navigate, useNavigate, useSearchParams } from 'react-router';
import { z } from 'zod';

import { ErrorAlert } from '../../components/ErrorAlert';
import { zodResolver } from '../../components/forms';
import { safeNext, useLogin, useMe } from './useAuth';

const schema = z.object({
  username: z.string().trim().min(1, 'auth.required'),
  password: z.string().min(1, 'auth.required'),
});
type LoginForm = z.infer<typeof schema>;

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = safeNext(searchParams.get('next'));
  const { data: me } = useMe();
  const login = useLogin();
  const {
    register,
    handleSubmit,
    resetField,
    formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(schema), defaultValues: { username: '', password: '' } });

  if (me) {
    return <Navigate to={next} replace />;
  }

  const onSubmit = handleSubmit((values) => {
    login.mutate(values, {
      onSuccess: () => void navigate(next, { replace: true }),
      onError: () => resetField('password'),
    });
  });

  return (
    <Center mih="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" w="100%" maw={400}>
        <form onSubmit={(event) => void onSubmit(event)} noValidate aria-labelledby="login-title">
          <Stack>
            <Title order={1} size="h3" id="login-title">
              {t('app.title')}
            </Title>
            <Text c="dimmed" size="sm">
              {t('auth.loginIntro')}
            </Text>
            {login.isError && <ErrorAlert error={login.error} />}
            <TextInput
              label={t('auth.username')}
              autoComplete="username"
              required
              error={errors.username?.message && t(errors.username.message)}
              data-autofocus
              {...register('username')}
            />
            <PasswordInput
              label={t('auth.password')}
              autoComplete="current-password"
              required
              error={errors.password?.message && t(errors.password.message)}
              {...register('password')}
            />
            <Button type="submit" loading={login.isPending}>
              {t('auth.login')}
            </Button>
          </Stack>
        </form>
      </Paper>
    </Center>
  );
}
