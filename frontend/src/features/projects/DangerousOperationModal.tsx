import {
  Alert,
  Button,
  Checkbox,
  Group,
  Input,
  Loader,
  Modal,
  Select,
  Stack,
  Text,
  TextInput,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { FolderBrowser } from '../../components/FolderBrowser';
import { useLocations } from '../locations/useLocations';
import { RunResult } from '../runs/RunResult';
import { isActive, useRun } from '../runs/useRuns';
import { DEFAULT_SCAN_OPTIONS, type ScanOptions } from '../scan/useScan';
import { type ProjectOut, type RunRequest, useEnqueueRun } from './useProjects';

export type DangerousOperation = 'history_clear' | 'project_move' | 'project_delete' | 'scan_force';

interface DangerousOperationModalProps {
  project: ProjectOut;
  operation: DangerousOperation;
  /** Opciones del escaneo para `scan_force` (siempre con todas las carpetas). */
  scanOptions?: ScanOptions;
  onClose: () => void;
}

function lastSegment(path: string): string {
  return path.split('/').pop() ?? path;
}

/**
 * Operación que mueve o borra ficheros (regla 7): primero una **vista previa** (run `dry_run`, sin cambios) con lo que
 * se tocará; después, escribiendo el nombre del proyecto, la operación real con la vista previa como prueba. Cambiar
 * las opciones obliga a repetir la vista previa.
 */
export function DangerousOperationModal({
  project,
  operation,
  scanOptions,
  onClose,
}: DangerousOperationModalProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const enqueue = useEnqueueRun(project.id);
  const { data: locations } = useLocations();
  const [deleteOutputs, setDeleteOutputs] = useState(false);
  const [destinationId, setDestinationId] = useState<string | null>(null);
  const [parent, setParent] = useState('');
  const [newFolder, setNewFolder] = useState(lastSegment(project.destination_subpath));
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [confirmName, setConfirmName] = useState('');
  const preview = useRun(previewId, 1_000);

  const destinations = (locations?.items ?? [])
    .filter((l) => l.usage !== 'source' && l.access === 'rw')
    .map((l) => ({ value: String(l.id), label: l.name }));
  const destinationName = destinations.find((d) => d.value === destinationId)?.label ?? '';

  // Vista previa: `dry_run`. Real: con la vista previa y el nombre tecleado como prueba de confirmación.
  const params = (dryRun: boolean): RunRequest => {
    const common = dryRun
      ? { dry_run: true }
      : { dry_run: false, preview_run_id: previewId, confirm_name: confirmName };
    if (operation === 'project_delete') {
      return { operation, delete_outputs: deleteOutputs, ...common };
    }
    if (operation === 'scan_force') {
      // «Forzar» vacía toda la caché: siempre todas las carpetas (`folders` vacío).
      return {
        operation: 'scan',
        folders: [],
        ...(scanOptions ?? DEFAULT_SCAN_OPTIONS),
        force: true,
        ...common,
      };
    }
    if (operation === 'project_move') {
      return {
        operation,
        destination_location_id: Number(destinationId),
        destination_parent: parent,
        new_folder: newFolder.trim(),
        ...common,
      };
    }
    return { operation, ...common };
  };
  const canPreview = operation !== 'project_move' || (destinationId !== null && newFolder.trim().length > 0);
  const resetPreview = () => {
    setPreviewId(null);
    setConfirmName('');
    enqueue.reset();
  };
  const launchPreview = () => enqueue.mutate(params(true), { onSuccess: (run) => setPreviewId(run.id) });
  const confirm = () =>
    enqueue.mutate(params(false), {
      onSuccess: (run) => {
        onClose();
        void navigate(`/runs/${run.id}`);
      },
    });

  const locked = previewId !== null;
  const previewDone = preview.data?.status === 'succeeded';

  return (
    <Modal
      opened
      onClose={onClose}
      size="lg"
      title={t(`projects.danger.${operation}.title`, { name: project.name })}
    >
      <Stack>
        <Text>{t(`projects.danger.${operation}.body`)}</Text>
        {operation === 'project_delete' && (
          <Checkbox
            label={t('projects.danger.project_delete.outputs')}
            description={t('projects.danger.project_delete.outputsHint')}
            checked={deleteOutputs}
            disabled={locked}
            onChange={(event) => setDeleteOutputs(event.currentTarget.checked)}
          />
        )}
        {operation === 'project_move' && (
          <>
            <Select
              label={t('projects.fields.destinationLocation')}
              data={destinations}
              value={destinationId}
              disabled={locked}
              onChange={(value) => {
                setDestinationId(value);
                setParent('');
              }}
            />
            {destinationId && !locked && (
              <Input.Wrapper
                label={t('projects.form.parentFolder')}
                description={t('projects.form.parentHint')}
              >
                <FolderBrowser
                  key={destinationId}
                  locationId={Number(destinationId)}
                  rootLabel={destinationName}
                  selected={parent}
                  onSelect={setParent}
                />
              </Input.Wrapper>
            )}
            <TextInput
              label={t('projects.form.newFolder')}
              value={newFolder}
              disabled={locked}
              onChange={(event) => setNewFolder(event.currentTarget.value)}
            />
          </>
        )}
        <VisuallyHidden aria-live="polite" aria-atomic="true">
          {locked && preview.data
            ? t(
                isActive(preview.data)
                  ? 'projects.danger.previewRunning'
                  : previewDone
                    ? 'projects.danger.previewReady'
                    : 'projects.danger.previewFailed',
              )
            : ''}
        </VisuallyHidden>
        {enqueue.isError && <ErrorAlert error={enqueue.error} />}
        {!locked && (
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button onClick={launchPreview} disabled={!canPreview} loading={enqueue.isPending}>
              {t('projects.danger.preview')}
            </Button>
          </Group>
        )}
        {locked && preview.data && isActive(preview.data) && (
          <Group>
            <Loader size="sm" />
            <Text>{t('projects.danger.previewRunning')}</Text>
          </Group>
        )}
        {locked && preview.isError && <ErrorAlert error={preview.error} />}
        {locked && preview.data && !isActive(preview.data) && !previewDone && (
          <Alert color="red" title={t('projects.danger.previewFailed')} role="alert">
            {preview.data.error_message ?? t(`runs.status.${preview.data.status}`)}
          </Alert>
        )}
        {previewDone && preview.data?.result && (
          <Stack>
            <Text fw={500}>{t('projects.danger.previewResult')}</Text>
            <RunResult result={preview.data.result} />
            <TextInput
              label={t('projects.danger.confirmName', { name: project.name })}
              value={confirmName}
              onChange={(event) => setConfirmName(event.currentTarget.value)}
              autoComplete="off"
            />
          </Stack>
        )}
        {locked && (
          <Group justify="flex-end">
            <Button variant="default" onClick={resetPreview}>
              {t('projects.danger.change')}
            </Button>
            <Button
              color="red"
              disabled={!previewDone || confirmName !== project.name}
              loading={enqueue.isPending}
              onClick={confirm}
            >
              {t(`projects.danger.${operation}.confirm`)}
            </Button>
          </Group>
        )}
      </Stack>
    </Modal>
  );
}
