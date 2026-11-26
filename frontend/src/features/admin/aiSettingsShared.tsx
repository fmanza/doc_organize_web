import { Stack, Text } from '@mantine/core';
import type { TFunction } from 'i18next';
import { ApiError } from '../../api/client';
import { problemTitle } from '../../components/problem';
import { type Toast } from '../../components/useToasts';
import { type AiTask, type AiTestResult } from './useAi';

export type Translate = TFunction;

export type PushToast = (toast: Omit<Toast, 'id'>) => number;

/** Tareas que solo se usan con un modelo propio (2.2): sin él, su funcionalidad queda desactivada. */
export const OWN_MODEL_TASKS: ReadonlySet<AiTask> = new Set<AiTask>(['dedup']);

export function aliasFor(task: AiTask): string {
  return `doc-organize-${task.replace('_', '-')}`;
}

/** Qué modelo respondió: el alias probado y, si el proxy dice otro detrás, ese. */
function modelLine(result: AiTestResult, t: Translate): string | null {
  if (!result.model) {
    return null;
  }
  return result.served_model && result.served_model !== result.model
    ? t('ai.settings.toast.modelServed', { model: result.model, served: result.served_model })
    : t('ai.settings.toast.model', { model: result.model });
}

export function toastFor(result: AiTestResult, label: string, t: Translate): Omit<Toast, 'id'> {
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

export function errorToast(error: unknown, label: string, t: Translate): Omit<Toast, 'id'> {
  return {
    color: 'red',
    title: t('ai.settings.toast.failed', { label }),
    message:
      error instanceof ApiError
        ? error.problem.detail || problemTitle(error.problem, t)
        : t('common.errorBody'),
  };
}
