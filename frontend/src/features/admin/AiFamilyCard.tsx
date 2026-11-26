import {
  Badge,
  Button,
  Card,
  Group,
  PasswordInput,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import {
  OWN_MODEL_TASKS,
  type PushToast,
  type Translate,
  aliasFor,
  errorToast,
  toastFor,
} from './aiSettingsShared';
import { type AiFamily, type AiField, useTestAiFamily } from './useAi';
import { type FamilyForm, useFamilyForm } from './useFamilyForm';

function sourceBadge(field: AiField, t: Translate) {
  const color = field.source === 'db' ? 'blue' : field.source === 'env' ? 'gray' : 'yellow';
  return (
    <Badge variant="light" color={color} size="sm">
      {t(`ai.settings.source.${field.source}`)}
    </Badge>
  );
}

/** Un campo con su origen (guardado, variable del servidor o sin valor), la pista del secreto y «Borrar». */
export function FieldInput({ field, form }: { field: AiField; form: FamilyForm }) {
  const { t } = useTranslation();
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
  const placeholder = field.secret
    ? t('ai.settings.secretPlaceholder')
    : field.task && field.name.startsWith('model')
      ? OWN_MODEL_TASKS.has(field.task)
        ? t('ai.settings.ownModelPlaceholder')
        : aliasFor(field.task) // alias recomendado (sin modelo propio)
      : field.name.startsWith('budget')
        ? t('ai.settings.budgetPlaceholder')
        : undefined;
  const Input = field.secret ? PasswordInput : TextInput;
  return (
    <Stack gap={4}>
      <Input
        label={label}
        description={description}
        required={field.required}
        value={form.values[field.name] ?? ''}
        placeholder={placeholder}
        autoComplete={field.secret ? 'new-password' : 'off'}
        onChange={(event) => form.setValue(field.name, event.currentTarget.value)}
      />
      {field.source === 'db' && (
        <Group justify="flex-end">
          <Button
            size="compact-xs"
            variant="subtle"
            color="red"
            onClick={() => form.clear(field.name)}
            aria-label={t('ai.settings.clearLabel', { label })}
          >
            {t('ai.settings.clear')}
          </Button>
        </Group>
      )}
    </Stack>
  );
}

/** Guardar, con el aviso de cifrado y los errores; `children` son los botones de prueba. */
export function SaveBar({
  form,
  label,
  children,
}: {
  form: FamilyForm;
  label: string;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <>
      {form.blockedBySecret && (
        <Text size="sm" c="orange" mt="xs">
          {t('ai.settings.secretNeedsEncryption')}
        </Text>
      )}
      {form.update.isError && <ErrorAlert error={form.update.error} mt="xs" />}
      {form.update.isSuccess && Object.keys(form.changes).length === 0 && (
        <Text size="sm" c="teal" role="status" mt="xs">
          {t('ai.settings.saved')}
        </Text>
      )}
      <Group justify="flex-end" mt="sm">
        {children}
        <Button
          onClick={form.save}
          loading={form.update.isPending}
          disabled={Object.keys(form.changes).length === 0 || form.blockedBySecret}
          aria-label={t('ai.settings.saveLabel', { label })}
        >
          {t('common.save')}
        </Button>
      </Group>
    </>
  );
}

// --- familia sin tareas (uso de LiteLLM) ----------------------------------------------------------------------------

export function FamilyCard({
  family,
  encryption,
  push,
}: {
  family: AiFamily;
  encryption: boolean;
  push: PushToast;
}) {
  const { t } = useTranslation();
  const form = useFamilyForm(family, encryption);
  const probe = useTestAiFamily();
  const title = t(`ai.families.${family.key}.title`);
  const test = async () => {
    try {
      const result = await probe.mutateAsync({ family: family.key, fields: form.changes, modelCheck: false });
      push(toastFor(result, title, t));
    } catch (error) {
      push(errorToast(error, title, t));
    }
  };

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
        {family.fields.map((field) => (
          <FieldInput key={field.name} field={field} form={form} />
        ))}
      </SimpleGrid>
      <SaveBar form={form} label={title}>
        <Button
          variant="default"
          onClick={() => void test()}
          loading={probe.isPending}
          disabled={!form.testable || probe.isPending}
          aria-label={t('ai.settings.testLabel', { label: title })}
        >
          {t('ai.settings.test')}
        </Button>
      </SaveBar>
    </Card>
  );
}
