import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Drawer,
  Group,
  Loader,
  PasswordInput,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { type ReactNode, useState } from 'react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';

import { ApiError } from '../../api/client';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { ToastStack } from '../../components/Toasts';
import { type Toast, useToasts } from '../../components/useToasts';
import {
  type AiFamily,
  type AiField,
  type AiTask,
  type AiTestResult,
  useAiSettings,
  useTestAiFamily,
  useUpdateAiFamily,
} from './useAi';

type Translate = TFunction;
type PushToast = (toast: Omit<Toast, 'id'>) => number;

/** Tareas que solo se usan con un modelo propio (2.2): sin él, su funcionalidad queda desactivada. */
const OWN_MODEL_TASKS: ReadonlySet<AiTask> = new Set<AiTask>(['dedup']);

/**
 * Configuración de IA (2.2): la conexión con el proxy y, en una tabla, una fila por funcionalidad con su modelo, su
 * clave propia, su presupuesto y su última prueba; cada una se edita en un panel lateral. Los resultados de las pruebas
 * salen en avisos flotantes que dicen qué modelo respondió. Los secretos nunca llegan al navegador: solo se ve que
 * están configurados y sus 4 últimos caracteres.
 */
export function AiSettingsPage() {
  const { t } = useTranslation();
  const settings = useAiSettings();
  const { toasts, push, dismiss } = useToasts();

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
      {(settings.data.legacy_variables ?? []).length > 0 && (
        <Alert color="orange" title={t('ai.settings.legacyTitle')}>
          {t('ai.settings.legacy')}
          <Stack gap={2} mt={4}>
            {(settings.data.legacy_variables ?? []).map((item) => (
              <Text key={item.name} size="sm" ff="monospace">
                {item.name} → {item.replacement ?? t('ai.settings.legacyRemoved')}
              </Text>
            ))}
          </Stack>
        </Alert>
      )}
      {settings.data.families.map((family) =>
        family.fields.some((field) => field.task) ? (
          <ModelsPanel
            key={family.key}
            family={family}
            encryption={settings.data.encryption_configured}
            push={push}
          />
        ) : (
          <FamilyCard
            key={family.key}
            family={family}
            encryption={settings.data.encryption_configured}
            push={push}
          />
        ),
      )}
      <ToastStack toasts={toasts} onClose={dismiss} />
    </Stack>
  );
}

// --- formulario de una familia (compartido) --------------------------------------------------------------------

/** Valores del formulario de una familia, lo que cambia respecto a lo guardado, guardar y borrar. */
function useFamilyForm(family: AiFamily, encryption: boolean) {
  const update = useUpdateAiFamily();
  const initial = (field: AiField) => (field.secret || field.source !== 'db' ? '' : (field.value ?? ''));
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(family.fields.map((field) => [field.name, initial(field)])),
  );
  const changes = Object.fromEntries(
    family.fields
      .filter((field) => (values[field.name] ?? '').trim() !== '' && values[field.name] !== initial(field))
      .map((field) => [field.name, (values[field.name] ?? '').trim()]),
  );
  const blockedBySecret = !encryption && family.fields.some((field) => field.secret && field.name in changes);
  // Se puede probar sin guardar: basta con que cada obligatorio esté escrito o ya tenga valor (guardado o del entorno).
  const testable = family.fields.every(
    (field) => !field.required || field.name in changes || field.source !== 'none',
  );
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
  const setValue = (name: string, value: string) => setValues((current) => ({ ...current, [name]: value }));
  return { values, setValue, changes, blockedBySecret, testable, save, clear, update };
}

type FamilyForm = ReturnType<typeof useFamilyForm>;

function aliasFor(task: AiTask): string {
  return `doc-organize-${task.replace('_', '-')}`;
}

function sourceBadge(field: AiField, t: Translate) {
  const color = field.source === 'db' ? 'blue' : field.source === 'env' ? 'gray' : 'yellow';
  return (
    <Badge variant="light" color={color} size="sm">
      {t(`ai.settings.source.${field.source}`)}
    </Badge>
  );
}

/** Un campo con su origen (guardado, variable del servidor o sin valor), la pista del secreto y «Borrar». */
function FieldInput({ field, form }: { field: AiField; form: FamilyForm }) {
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
function SaveBar({ form, label, children }: { form: FamilyForm; label: string; children?: ReactNode }) {
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

// --- resultado de una prueba en un aviso flotante -------------------------------------------------------------------

/** Qué modelo respondió: el alias probado y, si el proxy dice otro detrás, ese. */
function modelLine(result: AiTestResult, t: Translate): string | null {
  if (!result.model) {
    return null;
  }
  return result.served_model && result.served_model !== result.model
    ? t('ai.settings.toast.modelServed', { model: result.model, served: result.served_model })
    : t('ai.settings.toast.model', { model: result.model });
}

function toastFor(result: AiTestResult, label: string, t: Translate): Omit<Toast, 'id'> {
  const model = result.model_checked ? modelLine(result, t) : null;
  if (!result.ok) {
    return {
      color: 'red',
      title: t('ai.settings.toast.failed', { label }),
      message: (
        <Stack gap={2}>
          {model && (
            <Text size="sm" ff="monospace">
              {model}
            </Text>
          )}
          <Text size="sm">{t(`ai.errors.${result.error ?? 'ai_error'}`)}</Text>
          {result.error === 'ai_auth' && !result.model_checked && (
            <Text size="sm">{t('ai.settings.testAuthHint')}</Text>
          )}
        </Stack>
      ),
    };
  }
  const facts = [
    result.dimension ? t('ai.settings.toast.dimension', { count: result.dimension }) : null,
    t('ai.settings.toast.elapsed', { ms: result.elapsed_ms }),
  ].filter(Boolean);
  return {
    color: result.model_access === 'denied' ? 'orange' : 'teal',
    title: t(result.model_checked ? 'ai.settings.toast.okModel' : 'ai.settings.toast.okKey', { label }),
    message: (
      <Stack gap={2}>
        {model && (
          <Text size="sm" ff="monospace">
            {model}
          </Text>
        )}
        <Text size="sm">{facts.join(' · ')}</Text>
        {result.response_format && <Text size="sm">{t(`ai.settings.format.${result.response_format}`)}</Text>}
        {result.model_access === 'denied' && <Text size="sm">{t('ai.settings.modelDenied')}</Text>}
      </Stack>
    ),
  };
}

function errorToast(error: unknown, label: string, t: Translate): Omit<Toast, 'id'> {
  return {
    color: 'red',
    title: t('ai.settings.toast.failed', { label }),
    message:
      (error instanceof ApiError && (error.problem.detail || error.problem.title)) || t('common.errorBody'),
  };
}

// --- familia con modelos por funcionalidad (litellm) ----------------------------------------------------------------

function ModelsPanel({
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
  const [results, setResults] = useState<Partial<Record<AiTask, AiTestResult>>>({});
  const [editing, setEditing] = useState<AiTask | null>(null);
  const [testingAll, setTestingAll] = useState(false);
  const title = t(`ai.families.${family.key}.title`);
  const general = family.fields.filter((field) => !field.task);
  const byTask = new Map<AiTask, AiField[]>();
  for (const field of family.fields) {
    if (field.task) {
      byTask.set(field.task, [...(byTask.get(field.task) ?? []), field]);
    }
  }
  const tasks = [...byTask.keys()];

  /** El modelo de la tarea: el escrito, el guardado o del entorno, o el alias recomendado (`null` = desactivada). */
  const modelOf = (task: AiTask): { value: string; own: boolean } | null => {
    const field = byTask.get(task)?.find((item) => item.name.startsWith('model'));
    const typed = field ? (form.values[field.name] ?? '').trim() : '';
    const stored = field && !field.secret ? (field.value ?? '') : '';
    if (typed || stored) {
      return { value: typed || stored, own: true };
    }
    return OWN_MODEL_TASKS.has(task) ? null : { value: aliasFor(task), own: false };
  };
  const hasOwnKey = (task: AiTask) =>
    (byTask.get(task) ?? []).some(
      (field) => field.secret && (field.source !== 'none' || (form.values[field.name] ?? '').trim() !== ''),
    );
  const budgetOf = (task: AiTask) => {
    const field = byTask.get(task)?.find((item) => item.name.startsWith('budget'));
    if (!field) {
      return '—';
    }
    return (form.values[field.name] ?? '').trim() || field.value || t('ai.settings.table.generalBudget');
  };
  const testable = (task: AiTask) => form.testable && modelOf(task) !== null;
  const busy = probe.isPending || testingAll;

  const testTask = async (task: AiTask) => {
    const label = t(`ai.tasks.${task}`);
    try {
      const result = await probe.mutateAsync({
        family: family.key,
        fields: form.changes,
        modelCheck: true,
        task,
      });
      setResults((current) => ({ ...current, [task]: result }));
      push(toastFor(result, label, t));
    } catch (error) {
      push(errorToast(error, label, t));
    }
  };
  const testConnection = async () => {
    try {
      const result = await probe.mutateAsync({ family: family.key, fields: form.changes, modelCheck: false });
      push(toastFor(result, t('ai.settings.connection.title'), t));
    } catch (error) {
      push(errorToast(error, t('ai.settings.connection.title'), t));
    }
  };
  const testAll = async () => {
    setTestingAll(true);
    try {
      for (const task of tasks.filter(testable)) {
        await testTask(task); // una tras otra: el servidor limita las pruebas de cada modelo
      }
    } finally {
      setTestingAll(false);
    }
  };

  return (
    <>
      <Card withBorder component="section" aria-label={t('ai.settings.connection.title')}>
        <Group justify="space-between" mb="xs">
          <Title order={3} size="h4">
            {t('ai.settings.connection.title')}
          </Title>
          <Badge color={family.configured ? 'teal' : 'gray'} variant="light">
            {t(family.configured ? 'ai.settings.configured' : 'ai.settings.notConfigured')}
          </Badge>
        </Group>
        <Text size="sm" c="dimmed" mb="sm">
          {t(`ai.families.${family.key}.intro`)}
        </Text>
        <SimpleGrid cols={{ base: 1, md: 2 }}>
          {general.map((field) => (
            <FieldInput key={field.name} field={field} form={form} />
          ))}
        </SimpleGrid>
        <SaveBar form={form} label={title}>
          <Button
            variant="default"
            onClick={() => void testConnection()}
            loading={probe.isPending && probe.variables?.modelCheck === false}
            disabled={!form.testable || busy}
            aria-label={t('ai.settings.testLabel', { label: t('ai.settings.connection.title') })}
          >
            {t('ai.settings.test')}
          </Button>
        </SaveBar>
      </Card>

      <Card withBorder component="section" aria-label={t('ai.settings.table.title')}>
        <Group justify="space-between" mb="xs" wrap="wrap">
          <Title order={3} size="h4">
            {t('ai.settings.table.title')}
          </Title>
          <Button
            variant="light"
            size="xs"
            onClick={() => void testAll()}
            loading={testingAll}
            disabled={!form.testable || busy}
            title={t('ai.settings.testModelHint')}
          >
            {t('ai.settings.table.testAll')}
          </Button>
        </Group>
        <Text size="sm" c="dimmed" mb="sm">
          {t('ai.settings.table.intro')}
        </Text>
        <Table.ScrollContainer minWidth={760}>
          <Table verticalSpacing="sm" striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('ai.settings.table.feature')}</Table.Th>
                <Table.Th>{t('ai.settings.table.model')}</Table.Th>
                <Table.Th>{t('ai.settings.table.ownKey')}</Table.Th>
                <Table.Th>{t('ai.settings.table.budget')}</Table.Th>
                <Table.Th>{t('ai.settings.table.lastTest')}</Table.Th>
                <Table.Th>
                  <VisuallyHidden>{t('common.actions')}</VisuallyHidden>
                </Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {tasks.map((task) => {
                const label = t(`ai.tasks.${task}`);
                const model = modelOf(task);
                const result = results[task];
                return (
                  <Table.Tr key={task}>
                    <Table.Td>
                      <Text fw={500}>{label}</Text>
                      <Text size="xs" c="dimmed">
                        {t('ai.settings.table.usedIn', { features: t(`ai.taskUse.${task}`) })}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {model ? (
                        <Text size="sm" ff="monospace" {...(model.own ? {} : { c: 'dimmed' })}>
                          {model.value}
                          {!model.own && ` ${t('ai.settings.table.alias')}`}
                        </Text>
                      ) : (
                        <Badge color="gray" variant="light">
                          {t('ai.settings.table.disabled')}
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td>{hasOwnKey(task) ? t('common.yes') : '—'}</Table.Td>
                    <Table.Td>{budgetOf(task)}</Table.Td>
                    <Table.Td>
                      {result ? (
                        <Badge
                          color={result.ok ? (result.model_access === 'denied' ? 'orange' : 'teal') : 'red'}
                          variant="light"
                          title={formatDateTime(result.tested_at)}
                        >
                          {result.ok
                            ? t('ai.settings.table.testOk', { ms: result.elapsed_ms })
                            : t('ai.settings.table.testFailed')}
                        </Badge>
                      ) : (
                        <Text size="sm" c="dimmed">
                          —
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4} justify="flex-end" wrap="nowrap">
                        <Button
                          size="compact-sm"
                          variant="default"
                          onClick={() => setEditing(task)}
                          aria-label={t('ai.settings.table.editLabel', { task: label })}
                        >
                          {t('common.edit')}
                        </Button>
                        <Button
                          size="compact-sm"
                          variant="light"
                          onClick={() => void testTask(task)}
                          loading={probe.isPending && probe.variables?.task === task && !testingAll}
                          disabled={!testable(task) || busy}
                          title={
                            model ? t('ai.settings.testModelHint') : t('ai.settings.table.needsOwnModel')
                          }
                          aria-label={t('ai.settings.testTaskLabel', { task: label })}
                        >
                          {t('ai.settings.table.test')}
                        </Button>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Card>

      <Drawer
        opened={editing !== null}
        onClose={() => setEditing(null)}
        position="right"
        size="md"
        title={editing ? t(`ai.tasks.${editing}`) : ''}
      >
        {editing && (
          <Stack>
            <Text size="sm" c="dimmed">
              {t('ai.settings.table.usedIn', { features: t(`ai.taskUse.${editing}`) })}
            </Text>
            {OWN_MODEL_TASKS.has(editing) && (
              <Alert color="blue" title={t('ai.settings.ownModelTitle')}>
                {t(`ai.settings.ownModel.${editing}`)}
              </Alert>
            )}
            {(byTask.get(editing) ?? []).map((field) => (
              <FieldInput key={field.name} field={field} form={form} />
            ))}
            <SaveBar form={form} label={t(`ai.tasks.${editing}`)}>
              <Button
                variant="default"
                onClick={() => void testTask(editing)}
                loading={probe.isPending && probe.variables?.task === editing}
                disabled={!testable(editing) || busy}
                title={t('ai.settings.testModelHint')}
                aria-label={t('ai.settings.testTaskLabel', { task: t(`ai.tasks.${editing}`) })}
              >
                {t('ai.settings.testModel')}
              </Button>
            </SaveBar>
          </Stack>
        )}
      </Drawer>
    </>
  );
}

// --- familia sin tareas (uso de LiteLLM) ----------------------------------------------------------------------------

function FamilyCard({
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
