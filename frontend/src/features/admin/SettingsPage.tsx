import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  NumberInput,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import {
  type InstanceCapabilities,
  type SettingOut,
  useAdminSettings,
  useCapabilities,
  useRefreshCapabilities,
  useUpdateSettings,
} from './useSettings';

function SettingRow({ setting }: { setting: SettingOut }) {
  const { t } = useTranslation();
  const update = useUpdateSettings();
  const [value, setValue] = useState<string | number>(setting.value);
  const label = t(`settings.keys.${setting.key}.label`);
  const dirty = Number(value) !== setting.value;

  return (
    <Table.Tr>
      <Table.Td>
        <Text fw={500}>{label}</Text>
        <Text size="xs" c="dimmed">
          {t(`settings.keys.${setting.key}.hint`)}
        </Text>
        {update.isError && <ErrorAlert error={update.error} mt="xs" />}
      </Table.Td>
      <Table.Td>
        <NumberInput
          aria-label={label}
          value={value}
          onChange={setValue}
          allowDecimal={false}
          min={0}
          w={130}
        />
      </Table.Td>
      <Table.Td>
        <Badge variant="light" color={setting.source === 'db' ? 'blue' : 'gray'}>
          {t(`settings.source.${setting.source}`)}
        </Badge>
        {setting.source === 'db' && (
          <Text size="xs" c="dimmed">
            {t('settings.defaultIs', { value: setting.default })}
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        <Group gap="xs" wrap="nowrap">
          <Button
            size="xs"
            disabled={!dirty || value === ''}
            loading={update.isPending}
            onClick={() => update.mutate({ [setting.key]: Number(value) })}
            aria-label={t('settings.saveLabel', { label })}
          >
            {t('common.save')}
          </Button>
          {setting.source === 'db' && (
            <Button
              size="xs"
              variant="default"
              loading={update.isPending}
              onClick={() =>
                update.mutate({ [setting.key]: null }, { onSuccess: () => setValue(setting.default) })
              }
              aria-label={t('settings.resetLabel', { label })}
            >
              {t('settings.reset')}
            </Button>
          )}
        </Group>
      </Table.Td>
    </Table.Tr>
  );
}

function YesNo({ ok, label }: { ok: boolean; label: string }) {
  const { t } = useTranslation();
  return (
    <Group justify="space-between">
      <Text size="sm">{label}</Text>
      <Badge color={ok ? 'green' : 'gray'} variant="light">
        {ok ? t('capabilities.yes') : t('capabilities.no')}
      </Badge>
    </Group>
  );
}

function CapabilitiesCard({ data }: { data: InstanceCapabilities }) {
  const { t } = useTranslation();
  const caps = data.capabilities;
  return (
    <Stack gap="xs">
      {data.status === 'pending' && (
        <Group>
          <Loader size="xs" />
          <Text size="sm">{t('capabilities.pending')}</Text>
        </Group>
      )}
      {data.status === 'error' && (
        <Alert color="orange" title={t('capabilities.error')}>
          {t('capabilities.errorBody')}
        </Alert>
      )}
      {caps && (
        <>
          <YesNo ok={caps.gpu_active} label={t('capabilities.gpu')} />
          <YesNo ok={caps.av_ready} label={t('capabilities.av')} />
          <YesNo ok={caps.ffmpeg_installed} label={t('capabilities.ffmpeg')} />
          <YesNo ok={caps.libreoffice_installed} label={t('capabilities.libreoffice')} />
          <Text size="xs" c="dimmed">
            {t('capabilities.checkedAt', { date: formatDateTime(data.checked_at) })} ·{' '}
            {t('capabilities.library', { version: data.doc_organize_version ?? '—' })}
          </Text>
        </>
      )}
    </Stack>
  );
}

/** Ajustes administrables (ADR-012) y ficha de capacidades de la instancia. */
export function SettingsPage() {
  const { t } = useTranslation();
  const settings = useAdminSettings();
  const capabilities = useCapabilities();
  const refresh = useRefreshCapabilities();

  return (
    <Stack>
      <Title order={2}>{t('settings.title')}</Title>
      <Text c="dimmed">{t('settings.intro')}</Text>
      {settings.isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {settings.isError && <ErrorAlert error={settings.error} />}
      {settings.data && (
        <Table.ScrollContainer minWidth={720}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('settings.setting')}</Table.Th>
                <Table.Th>{t('settings.value')}</Table.Th>
                <Table.Th>{t('settings.origin')}</Table.Th>
                <Table.Th>{t('common.actions')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {settings.data.items.map((setting) => (
                <SettingRow key={`${setting.key}-${setting.value}`} setting={setting} />
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Card withBorder maw={520}>
        <Group justify="space-between" mb="sm">
          <Title order={3} size="h4">
            {t('capabilities.title')}
          </Title>
          <Button size="xs" variant="light" loading={refresh.isPending} onClick={() => refresh.mutate()}>
            {t('capabilities.refresh')}
          </Button>
        </Group>
        {capabilities.isPending && <Loader size="sm" aria-label={t('common.loading')} />}
        {capabilities.isError && <ErrorAlert error={capabilities.error} />}
        {capabilities.data && <CapabilitiesCard data={capabilities.data} />}
      </Card>
    </Stack>
  );
}
