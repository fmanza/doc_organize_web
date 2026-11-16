import { Anchor, Center, Loader, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { SettingsTable } from './SettingsTable';
import { useAdminSettings } from './useSettings';

/**
 * Parámetros de la IA (W1): tiempos, reintentos y tope de documentos por ejecución. Son ajustes administrables como los
 * de «Ajustes» (mismo `PATCH /admin/settings`); aquí solo se muestran los de la sección `ai`.
 */
export function AiParametersPage() {
  const { t } = useTranslation();
  const settings = useAdminSettings();
  const items = settings.data?.items.filter((setting) => setting.group === 'ai') ?? [];

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
      {settings.data && <SettingsTable settings={items} />}
    </Stack>
  );
}
