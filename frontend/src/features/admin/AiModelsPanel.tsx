import {
  Alert,
  Badge,
  Button,
  Card,
  Drawer,
  Group,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { formatDateTime } from '../../components/format';
import { FieldInput, SaveBar } from './AiFamilyCard';
import { OWN_MODEL_TASKS, type PushToast, aliasFor, errorToast, toastFor } from './aiSettingsShared';
import { type AiFamily, type AiField, type AiTask, type AiTestResult, useTestAiFamily } from './useAi';
import { useFamilyForm } from './useFamilyForm';

export function ModelsPanel({
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
