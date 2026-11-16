import { Anchor, Center, Loader, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { SettingsTable } from './SettingsTable';
import { type SettingOut, useAdminSettings } from './useSettings';

/** Secciones de «Ajustes», en orden; los de IA están en «IA › Parámetros». El backend decide la de cada clave. */
const SECTIONS = ['security', 'locations', 'storage'] as const satisfies readonly SettingOut['group'][];

/** Ajustes administrables de la instancia (ADR-012), por secciones. */
export function SettingsPage() {
  const { t } = useTranslation();
  const settings = useAdminSettings();

  return (
    <Stack>
      <Title order={2}>{t('settings.title')}</Title>
      <Text c="dimmed">{t('settings.intro')}</Text>
      <Text size="sm">
        {t('settings.aiMoved')}{' '}
        <Anchor component={Link} to="/admin/ai/parameters">
          {t('settings.aiMovedLink')}
        </Anchor>
      </Text>
      {settings.isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {settings.isError && <ErrorAlert error={settings.error} />}
      {settings.data &&
        SECTIONS.map((section) => {
          const items = settings.data.items.filter((setting) => setting.group === section);
          return (
            items.length > 0 && (
              <Stack key={section} gap="xs">
                <Title order={3} size="h4">
                  {t(`settings.sections.${section}`)}
                </Title>
                <SettingsTable settings={items} />
              </Stack>
            )
          );
        })}
    </Stack>
  );
}
