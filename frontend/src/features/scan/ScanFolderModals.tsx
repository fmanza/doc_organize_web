import { Alert, Button, Group, Input, Modal, Stack, Text } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { FolderBrowser } from '../../components/FolderBrowser';
import { type ProjectOut } from '../projects/useProjects';
import { folderLabel } from './scanFolders';
import { type ScannedFolderOut, useAddFolder, useRemoveFolder } from './useScan';

export function AddFolderModal({ project, onClose }: { project: ProjectOut; onClose: () => void }) {
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

export function RemoveFolderModal({
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
