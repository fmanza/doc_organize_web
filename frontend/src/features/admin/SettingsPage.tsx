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
import { formatBytes, formatDateTime } from '../../components/format';
import {
  type InstanceCapabilities,
  type SettingOut,
  useAdminSettings,
  useCapabilities,
  useRefreshCapabilities,
  useUpdateSettings,
  useWorkers,
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

/** Sí/No de una capacidad; si solo la tienen los workers de algunas colas, las nombra (1.0.1). */
function YesNo({ ok, label, only }: { ok: boolean; label: string; only?: string[] | undefined }) {
  const { t } = useTranslation();
  return (
    <Group justify="space-between">
      <Text size="sm">{label}</Text>
      <Group gap="xs">
        {ok && only && only.length > 0 && (
          <Text size="xs" c="dimmed">
            {t('capabilities.onlyQueues', { queues: only.join(', '), count: only.length })}
          </Text>
        )}
        <Badge color={ok ? 'green' : 'gray'} variant="light">
          {ok ? t('capabilities.yes') : t('capabilities.no')}
        </Badge>
      </Group>
    </Group>
  );
}

function CapabilitiesCard({ data }: { data: InstanceCapabilities }) {
  const { t } = useTranslation();
  const caps = data.capabilities;
  // Colas que tienen una capacidad, solo si no son todas las atendidas (p. ej. la GPU, solo en «gpu»).
  const only = (key: string): string[] | undefined => {
    const queues = data.capability_queues?.[key];
    return queues && queues.length < data.queues.length ? queues : undefined;
  };
  return (
    <Stack gap="xs">
      {data.status === 'pending' && (
        <Group>
          <Loader size="xs" />
          <Text size="sm">{t('capabilities.pending')}</Text>
        </Group>
      )}
      {data.status === 'no_worker' && (
        <Alert color="orange" title={t('capabilities.noWorker')}>
          {t('capabilities.noWorkerBody')}
        </Alert>
      )}
      {caps && (
        <>
          <YesNo ok={caps.gpu_ready} label={t('capabilities.gpu')} only={only('gpu_ready')} />
          <YesNo ok={caps.av_ready} label={t('capabilities.av')} only={only('av_ready')} />
          <YesNo
            ok={caps.ffmpeg_installed}
            label={t('capabilities.ffmpeg')}
            only={only('ffmpeg_installed')}
          />
          <YesNo
            ok={caps.libreoffice_installed}
            label={t('capabilities.libreoffice')}
            only={only('libreoffice_installed')}
          />
          <YesNo ok={caps.models_ready} label={t('capabilities.models')} only={only('models_ready')} />
          <YesNo
            ok={caps.picture_description_ready}
            label={t('capabilities.pictureDescription')}
            only={only('picture_description_ready')}
          />
          <Text size="xs" c="dimmed">
            {t('capabilities.checkedAt', { date: formatDateTime(data.checked_at) })} ·{' '}
            {t('capabilities.library', { version: data.doc_organize_version ?? '—' })}
          </Text>
          {data.queues.length > 0 && (
            <Text size="xs" c="dimmed">
              {t('capabilities.queues', { queues: data.queues.join(', ') })}
            </Text>
          )}
        </>
      )}
    </Stack>
  );
}

type Resources = NonNullable<
  NonNullable<ReturnType<typeof useWorkers>['data']>['items'][number]['resources']
>;

/** Pico y límite de memoria del contenedor y OOM (M3, Fase 10): si el pico roza el límite, sube DOW_WORKER_MEM_LIMIT. */
function WorkerMemory({ resources }: { resources: Resources | null }) {
  const { t } = useTranslation();
  if (!resources) {
    return <>—</>;
  }
  const peak = resources.memory_peak_bytes ?? resources.memory_current_bytes ?? null;
  const limit = resources.memory_limit_bytes ?? null;
  return (
    <Stack gap={2}>
      <Text size="sm">
        {t('workers.memoryUse', {
          peak: peak === null ? '—' : formatBytes(peak),
          limit: limit === null ? t('workers.noLimit') : formatBytes(limit),
        })}
      </Text>
      {(resources.oom_kills ?? 0) > 0 && (
        <Badge color="red" variant="light">
          {t('workers.oom', { count: resources.oom_kills ?? 0 })}
        </Badge>
      )}
      {resources.scan_recycle_documents ? (
        <Text size="xs" c="dimmed">
          {t('workers.recycle', { count: resources.scan_recycle_documents })}
        </Text>
      ) : null}
    </Stack>
  );
}

function WorkersCard() {
  const { t } = useTranslation();
  const workers = useWorkers();
  return (
    <Card withBorder maw={960}>
      <Title order={3} size="h4" mb="sm">
        {t('workers.title')}
      </Title>
      {workers.isPending && <Loader size="sm" aria-label={t('common.loading')} />}
      {workers.isError && <ErrorAlert error={workers.error} />}
      {workers.data?.items.length === 0 && (
        <Text size="sm" c="dimmed">
          {t('workers.empty')}
        </Text>
      )}
      {workers.data && workers.data.items.length > 0 && (
        <Table.ScrollContainer minWidth={760}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('workers.id')}</Table.Th>
                <Table.Th>{t('workers.queues')}</Table.Th>
                <Table.Th>{t('workers.state')}</Table.Th>
                <Table.Th>{t('workers.heartbeat')}</Table.Th>
                <Table.Th>{t('workers.gpu')}</Table.Th>
                <Table.Th>{t('workers.memory')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {workers.data.items.map((worker) => (
                <Table.Tr key={worker.id}>
                  <Table.Td>
                    <Text size="sm" ff="monospace">
                      {worker.id}
                    </Text>
                  </Table.Td>
                  <Table.Td>{worker.queues.join(', ')}</Table.Td>
                  <Table.Td>
                    <Badge color={worker.alive ? 'green' : 'gray'} variant="light">
                      {t(worker.alive ? 'workers.alive' : 'workers.stale')}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{formatDateTime(worker.heartbeat_at)}</Table.Td>
                  <Table.Td>
                    {worker.gpu_ready === null || worker.gpu_ready === undefined
                      ? '—'
                      : t(worker.gpu_ready ? 'capabilities.yes' : 'capabilities.no')}
                  </Table.Td>
                  <Table.Td>
                    <WorkerMemory resources={worker.resources ?? null} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Card>
  );
}

/** Ajustes administrables (ADR-012), ficha de capacidades de la instancia y workers. */
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
      <WorkersCard />
    </Stack>
  );
}
