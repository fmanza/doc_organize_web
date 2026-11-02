import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  PasswordInput,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { type AiFamily, type AiField, useAiSettings, useUpdateAiFamily } from './useAi';

/**
 * Configuración de IA (sustituye a `ai_settings.html.j2`): una tarjeta por familia. Los secretos nunca llegan al
 * navegador: solo se ve que están configurados y sus 4 últimos caracteres.
 */
export function AiSettingsPage() {
  const { t } = useTranslation();
  const settings = useAiSettings();

  if (settings.isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (settings.isError) {
    return <ErrorAlert error={settings.error} />;
  }
  return (
    <Stack>
      <Title order={2}>{t('ai.settings.title')}</Title>
      <Text c="dimmed">{t('ai.settings.intro')}</Text>
      {!settings.data.encryption_configured && (
        <Alert color="orange" title={t('ai.settings.noEncryptionTitle')}>
          {t('ai.settings.noEncryption')}
        </Alert>
      )}
      {settings.data.families.map((family) => (
        <FamilyCard key={family.key} family={family} encryption={settings.data.encryption_configured} />
      ))}
    </Stack>
  );
}

function sourceBadge(field: AiField, t: (key: string) => string) {
  const color = field.source === 'db' ? 'blue' : field.source === 'env' ? 'gray' : 'yellow';
  return (
    <Badge variant="light" color={color} size="sm">
      {t(`ai.settings.source.${field.source}`)}
    </Badge>
  );
}

function FamilyCard({ family, encryption }: { family: AiFamily; encryption: boolean }) {
  const { t } = useTranslation();
  const update = useUpdateAiFamily();
  const initial = (field: AiField) => (field.secret || field.source !== 'db' ? '' : (field.value ?? ''));
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(family.fields.map((field) => [field.name, initial(field)])),
  );
  const title = t(`ai.families.${family.key}.title`);
  const changes = Object.fromEntries(
    family.fields
      .filter((field) => (values[field.name] ?? '').trim() !== '' && values[field.name] !== initial(field))
      .map((field) => [field.name, (values[field.name] ?? '').trim()]),
  );
  const blockedBySecret = !encryption && family.fields.some((field) => field.secret && field.name in changes);
  const save = () =>
    update.mutate(
      { family: family.key, fields: changes },
      {
        onSuccess: (saved) =>
          setValues(Object.fromEntries(saved.fields.map((field) => [field.name, initial(field)]))),
      },
    );
  const clear = (name: string) =>
    update.mutate(
      { family: family.key, fields: { [name]: null } },
      { onSuccess: () => setValues((current) => ({ ...current, [name]: '' })) },
    );

  return (
    <Card withBorder component="section" aria-label={title}>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {title}
        </Title>
        <Badge color={family.configured ? 'teal' : 'gray'} variant="light">
          {t(family.configured ? 'ai.settings.configured' : 'ai.settings.notConfigured')}
        </Badge>
      </Group>
      <Text size="sm" c="dimmed" mb="sm">
        {t(`ai.families.${family.key}.intro`)}
      </Text>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        {family.fields.map((field) => {
          const label = t(`ai.fields.${field.name}`);
          const description = (
            <Stack gap={2} component="span">
              <Group gap={6} component="span">
                {sourceBadge(field, t)}
                {field.secret && field.hint && (
                  <Text size="xs" component="span">
                    {t('ai.settings.hint', { hint: field.hint })}
                  </Text>
                )}
                {!field.secret && field.source === 'env' && field.value && (
                  <Text size="xs" component="span" ff="monospace">
                    {field.value}
                  </Text>
                )}
              </Group>
              <Text size="xs" c="dimmed" component="span">
                {field.env_var}
              </Text>
              {field.undecryptable && (
                <Text size="xs" c="orange" component="span">
                  {t('ai.settings.undecryptable')}
                </Text>
              )}
            </Stack>
          );
          const Input = field.secret ? PasswordInput : TextInput;
          return (
            <Stack key={field.name} gap={4}>
              <Input
                label={label}
                description={description}
                required={field.required}
                value={values[field.name] ?? ''}
                placeholder={field.secret ? t('ai.settings.secretPlaceholder') : undefined}
                autoComplete={field.secret ? 'new-password' : 'off'}
                onChange={(event) => {
                  const next = event.currentTarget.value;
                  setValues((current) => ({ ...current, [field.name]: next }));
                }}
              />
              {field.source === 'db' && (
                <Group justify="flex-end">
                  <Button
                    size="compact-xs"
                    variant="subtle"
                    color="red"
                    onClick={() => clear(field.name)}
                    aria-label={t('ai.settings.clearLabel', { label })}
                  >
                    {t('ai.settings.clear')}
                  </Button>
                </Group>
              )}
            </Stack>
          );
        })}
      </SimpleGrid>
      {blockedBySecret && (
        <Text size="sm" c="orange" mt="xs">
          {t('ai.settings.secretNeedsEncryption')}
        </Text>
      )}
      {update.isError && <ErrorAlert error={update.error} mt="xs" />}
      {update.isSuccess && Object.keys(changes).length === 0 && (
        <Text size="sm" c="teal" role="status" mt="xs">
          {t('ai.settings.saved')}
        </Text>
      )}
      <Group justify="flex-end" mt="sm">
        <Button
          onClick={save}
          loading={update.isPending}
          disabled={Object.keys(changes).length === 0 || blockedBySecret}
          aria-label={t('ai.settings.saveLabel', { label: title })}
        >
          {t('common.save')}
        </Button>
      </Group>
    </Card>
  );
}
