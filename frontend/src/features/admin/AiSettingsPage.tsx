import { Alert, Center, Loader, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { ToastStack } from '../../components/Toasts';
import { useToasts } from '../../components/useToasts';
import { FamilyCard } from './AiFamilyCard';
import { ModelsPanel } from './AiModelsPanel';
import { useAiSettings } from './useAi';

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
