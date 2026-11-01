import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Checkbox,
  Group,
  Input,
  Loader,
  Modal,
  Popover,
  Stack,
  Switch,
  Table,
  Text,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { FolderBrowser } from '../../components/FolderBrowser';
import { formatDateTime } from '../../components/format';
import { useCapabilities } from '../admin/useSettings';
import { DangerousOperationModal } from '../projects/DangerousOperationModal';
import { canDo, type ProjectOut, useEnqueueRun, useProject } from '../projects/useProjects';
import {
  DEFAULT_SCAN_OPTIONS,
  SCAN_OPTION_KEYS,
  type ScanOptionKey,
  type ScanOptions,
  scanRequest,
  type ScannedFolderOut,
  useAddFolder,
  useRemoveFolder,
  useScannedFolders,
} from './useScan';

/** Opciones que dependen de la instancia (las demás siempre se pueden elegir). */
const NEEDS_CAPABILITY = new Set<ScanOptionKey>([
  'use_gpu',
  'include_audio_video',
  'use_picture_description',
]);

function folderLabel(subpath: string): string {
  return subpath ? `/${subpath}` : '/';
}

/** Ayuda contextual de una opción con un ejemplo (sustituye a `_example_modal_macros`). */
function OptionHelp({ option }: { option: ScanOptionKey }) {
  const { t } = useTranslation();
  return (
    <Popover width={320} position="bottom-start" withArrow shadow="md">
      <Popover.Target>
        <ActionIcon
          variant="subtle"
          size="sm"
          aria-label={t('scan.help', { option: t(`scan.options.${option}.label`) })}
        >
          ?
        </ActionIcon>
      </Popover.Target>
      <Popover.Dropdown>
        <Text size="sm">{t(`scan.options.${option}.help`)}</Text>
        <Text size="sm" c="dimmed" mt="xs">
          {t(`scan.options.${option}.example`)}
        </Text>
      </Popover.Dropdown>
    </Popover>
  );
}

function AddFolderModal({ project, onClose }: { project: ProjectOut; onClose: () => void }) {
  const { t } = useTranslation();
  const add = useAddFolder(project.id);
  const [selected, setSelected] = useState<string | undefined>(undefined);
  return (
    <Modal opened onClose={onClose} size="lg" title={t('scan.folders.addTitle')}>
      <Stack>
        <Text size="sm" c="dimmed">
          {t('scan.folders.addHint')}
        </Text>
        <Input.Wrapper label={t('scan.folders.browse', { location: project.source_location.name })}>
          <FolderBrowser
            locationId={project.source_location.id}
            rootLabel={project.source_location.name}
            selected={selected}
            onSelect={setSelected}
          />
        </Input.Wrapper>
        {selected !== undefined && (
          <Text size="sm">
            {t('scan.folders.selected')}{' '}
            <Text span ff="monospace">
              {folderLabel(selected)}
            </Text>
          </Text>
        )}
        {add.isError && <ErrorAlert error={add.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            disabled={selected === undefined}
            loading={add.isPending}
            onClick={() => selected !== undefined && add.mutate(selected, { onSuccess: onClose })}
          >
            {t('scan.folders.add')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function RemoveFolderModal({
  project,
  folder,
  onClose,
}: {
  project: ProjectOut;
  folder: ScannedFolderOut;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const remove = useRemoveFolder(project.id);
  return (
    <Modal
      opened
      onClose={onClose}
      title={t('scan.folders.removeTitle', { folder: folderLabel(folder.subpath) })}
    >
      <Stack>
        <Text>{t('scan.folders.removeBody')}</Text>
        {folder.used && (
          <Alert color="yellow" title={t('scan.folders.usedTitle')}>
            {t('scan.folders.usedBody')}
          </Alert>
        )}
        {remove.isError && <ErrorAlert error={remove.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            color="red"
            loading={remove.isPending}
            onClick={() => remove.mutate(folder.subpath, { onSuccess: onClose })}
          >
            {t('scan.folders.remove')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/**
 * Pantalla de escaneo (sustituye a `folder_selector.html.j2`): elegir carpetas de origen del proyecto, opciones con
 * ayuda contextual (desactivadas si la instancia no puede atenderlas) y lanzar el run; «forzar reconversión» va por la
 * vista previa y la confirmación de las operaciones que borran.
 */
export function ScanPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const id = Number(useParams().projectId);
  const project = useProject(id);
  const folders = useScannedFolders(id);
  const capabilities = useCapabilities();
  const enqueue = useEnqueueRun(id);
  const [unchecked, setUnchecked] = useState<Set<string>>(new Set());
  const [options, setOptions] = useState<ScanOptions>(DEFAULT_SCAN_OPTIONS);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<ScannedFolderOut | null>(null);
  const [forcing, setForcing] = useState(false);

  if (project.isPending || folders.isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (project.isError) {
    return <ErrorAlert error={project.error} />;
  }
  if (folders.isError) {
    return <ErrorAlert error={folders.error} />;
  }

  const data = project.data;
  const items = folders.data.items;
  const isOwner = canDo(data, 'owner');
  const canScan = canDo(data, 'editor');
  // Una carpeta que ya no existe no se puede escanear (el worker fallaría con `folder_missing`).
  const included = (folder: ScannedFolderOut) => folder.available && !unchecked.has(folder.subpath);
  const chosen = items.filter(included).map((f) => f.subpath);
  const available = capabilities.data?.scan_options;
  const optionDisabled = (option: ScanOptionKey): boolean =>
    NEEDS_CAPABILITY.has(option) && !(available?.[option as keyof typeof available] ?? false);
  /** Motivo visible de una opción desactivada: solo si las capacidades se han podido comprobar. */
  const optionHint = (option: ScanOptionKey): string | undefined =>
    optionDisabled(option) && capabilities.isSuccess ? t(`scan.options.${option}.unavailable`) : undefined;
  /** Opciones que se envían: las desactivadas nunca, aunque se marcaran antes de cambiar las capacidades. */
  const effectiveOptions = (): ScanOptions =>
    Object.fromEntries(SCAN_OPTION_KEYS.map((k) => [k, options[k] && !optionDisabled(k)])) as ScanOptions;
  const toggleFolder = (subpath: string, checked: boolean) =>
    setUnchecked((current) => {
      const next = new Set(current);
      if (checked) {
        next.delete(subpath);
      } else {
        next.add(subpath);
      }
      return next;
    });
  const launch = () =>
    enqueue.mutate(scanRequest(chosen.length === items.length ? [] : chosen, effectiveOptions()), {
      onSuccess: (run) => void navigate(`/runs/${run.id}`),
    });

  return (
    <Stack>
      <Anchor component={Link} to={`/projects/${data.id}`} size="sm">
        {t('runs.backToProject', { name: data.name })}
      </Anchor>
      <Group justify="space-between">
        <Title order={2}>{t('scan.title', { name: data.name })}</Title>
        <Anchor component={Link} to={`/projects/${data.id}/scan-errors`} size="sm">
          {t('scan.errorsLink')}
        </Anchor>
      </Group>
      <Text c="dimmed">{t('scan.intro')}</Text>
      {!canScan && <Alert color="gray">{t('scan.readOnly')}</Alert>}

      <Card withBorder>
        <Group justify="space-between" mb="sm">
          <Title order={3} size="h4">
            {t('scan.folders.title', { location: folders.data.location.name })}
          </Title>
          {isOwner && (
            <Button variant="light" size="xs" disabled={data.active_run} onClick={() => setAdding(true)}>
              {t('scan.folders.add')}
            </Button>
          )}
        </Group>
        <Table.ScrollContainer minWidth={560}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('scan.folders.scan')}</Table.Th>
                <Table.Th>{t('scan.folders.folder')}</Table.Th>
                <Table.Th>{t('scan.folders.lastScan')}</Table.Th>
                {isOwner && (
                  <Table.Th>
                    <VisuallyHidden>{t('common.actions')}</VisuallyHidden>
                  </Table.Th>
                )}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {items.map((folder) => (
                <Table.Tr key={folder.subpath}>
                  <Table.Td>
                    <Checkbox
                      aria-label={t('scan.folders.include', { folder: folderLabel(folder.subpath) })}
                      checked={included(folder)}
                      disabled={!canScan || !folder.available}
                      onChange={(event) => toggleFolder(folder.subpath, event.currentTarget.checked)}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <Text ff="monospace" size="sm">
                        {folderLabel(folder.subpath)}
                      </Text>
                      {folder.used && <Badge variant="light">{t('scan.folders.used')}</Badge>}
                      {!folder.available && (
                        <Badge color="red" variant="light">
                          {t('scan.folders.missing')}
                        </Badge>
                      )}
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    {folder.last_run_id ? (
                      <Anchor component={Link} to={`/runs/${folder.last_run_id}`} size="sm">
                        {formatDateTime(folder.last_scanned_at)}
                      </Anchor>
                    ) : (
                      <Text size="sm" c="dimmed">
                        {t('scan.folders.never')}
                      </Text>
                    )}
                  </Table.Td>
                  {isOwner && (
                    <Table.Td>
                      <Button
                        variant="subtle"
                        color="red"
                        size="xs"
                        disabled={data.active_run || items.length === 1}
                        onClick={() => setRemoving(folder)}
                        aria-label={t('scan.folders.removeLabel', { folder: folderLabel(folder.subpath) })}
                      >
                        {t('scan.folders.remove')}
                      </Button>
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Card>

      <Card withBorder>
        <Title order={3} size="h4" mb="sm">
          {t('scan.optionsTitle')}
        </Title>
        {capabilities.isError && (
          <Text size="sm" c="red" mb="sm" role="alert">
            {t('scan.capabilitiesError')}
          </Text>
        )}
        {capabilities.isPending && (
          <Text size="sm" c="dimmed" mb="sm">
            {t('scan.capabilitiesLoading')}
          </Text>
        )}
        <Stack gap="sm">
          {SCAN_OPTION_KEYS.map((option) => (
            <Group key={option} gap="xs" wrap="nowrap" align="flex-start">
              <Switch
                label={t(`scan.options.${option}.label`)}
                description={optionHint(option)}
                checked={options[option] && !optionDisabled(option)}
                disabled={!canScan || optionDisabled(option)}
                onChange={(event) => {
                  const checked = event.currentTarget.checked;
                  setOptions((current) => ({ ...current, [option]: checked }));
                }}
              />
              <OptionHelp option={option} />
            </Group>
          ))}
        </Stack>
      </Card>

      {enqueue.isError && <ErrorAlert error={enqueue.error} />}
      {data.active_run && <Alert color="gray">{t('scan.busy')}</Alert>}
      {canScan && (
        <Group justify="flex-end">
          <Button
            size="md"
            disabled={chosen.length === 0 || data.active_run}
            loading={enqueue.isPending}
            onClick={launch}
          >
            {chosen.length === items.length
              ? t('scan.launchAll')
              : t('scan.launchSome', { count: chosen.length })}
          </Button>
        </Group>
      )}

      {isOwner && (
        <Card withBorder style={{ borderColor: 'var(--mantine-color-red-6)' }}>
          <Title order={3} size="h4" mb="xs">
            {t('scan.force.title')}
          </Title>
          <Text size="sm" c="dimmed" mb="sm">
            {t('scan.force.intro')}
          </Text>
          <Button color="red" variant="light" disabled={data.active_run} onClick={() => setForcing(true)}>
            {t('projects.danger.scan_force.button')}
          </Button>
        </Card>
      )}

      {adding && <AddFolderModal project={data} onClose={() => setAdding(false)} />}
      {removing && <RemoveFolderModal project={data} folder={removing} onClose={() => setRemoving(null)} />}
      {forcing && (
        <DangerousOperationModal
          project={data}
          operation="scan_force"
          scanOptions={effectiveOptions()}
          onClose={() => setForcing(false)}
        />
      )}
    </Stack>
  );
}
