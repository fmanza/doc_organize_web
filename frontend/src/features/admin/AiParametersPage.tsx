import { Anchor, Center, Loader, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { SettingsTable } from './SettingsTable';
import type { AiTask } from './useAi';
import { useAdminSettings } from './useSettings';

/** Qué funcionalidades usan cada parámetro (2.2): las tareas largas tienen su plazo y sus reintentos. */
const USED_IN: Readonly<Record<string, readonly AiTask[]>> = {
  ai_timeout_seconds: ['classify', 'enrich', 'embed', 'dedup'],
  ai_retries: ['classify', 'enrich', 'embed', 'dedup'],
  ai_max_documents_per_run: ['classify', 'enrich'],
  ai_draft_timeout_seconds: ['taxonomy_design', 'agent'],
  ai_draft_retries: ['taxonomy_design', 'agent'],
};

/**
 * Parámetros de la IA (W1): tiempos, reintentos y tope de documentos por ejecución. Son ajustes administrables como los
 * de «Ajustes» (mismo `PATCH /admin/settings`); aquí solo se muestran los de la sección `ai`.
 */
export function AiParametersPage() {
  const { t } = useTranslation();
  const settings = useAdminSettings();
  const items = settings.data?.items.filter((setting) => setting.group === 'ai') ?? [];
  const usedIn = Object.fromEntries(
    Object.entries(USED_IN).map(([key, tasks]) => [key, tasks.map((task) => t(`ai.tasksShort.${task}`))]),
  );

  return (
    <Stack>
      <Title order={2}>{t('ai.parameters.title')}</Title>
      <Text c="dimmed">
        {t('ai.parameters.intro')}{' '}
        <Anchor component={Link} to="/admin/ai/settings">
          {t('ai.parameters.configure')}
        </Anchor>
      </Text>
      {settings.isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {settings.isError && <ErrorAlert error={settings.error} />}
      {settings.data && <SettingsTable settings={items} usedIn={usedIn} />}
    </Stack>
  );
}
