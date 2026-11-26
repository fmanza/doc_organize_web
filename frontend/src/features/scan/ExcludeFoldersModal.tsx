import { Alert, Anchor, Badge, Button, Group, Input, Modal, Stack, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { ErrorAlert } from '../../components/ErrorAlert';
import { FolderBrowser } from '../../components/FolderBrowser';
import { useExclusionSet } from '../../components/useExclusionSet';
import { type ProjectOut, useProjectExclusions } from '../projects/useProjects';
import { folderLabel } from './scanFolders';
import { type ScannedFolderOut, useSetExclusions } from './useScan';

/**
 * Exclusiones de todo el proyecto (2.7, ADR-017), en solo lectura: se suman a las de cada carpeta al escanear. Se
 * cambian en la página del proyecto.
 */
export function InheritedExclusions({ projectId }: { projectId: number }) {
  const { t } = useTranslation();
  const { data } = useProjectExclusions(projectId);
  if (!data) {
    return null;
  }
  const patterns = [
    ...data.location_patterns,
    ...data.ignore_patterns,
    ...(data.exclude_system_folders ? data.system_patterns : []),
  ];
  if (data.excluded.length === 0 && patterns.length === 0) {
    return null;
  }
  return (
    <Alert color="gray" variant="light" mt="sm" title={t('scan.inherited.title')}>
      <Stack gap={4}>
        {data.excluded.length > 0 && (
          <Text size="sm">
            {t('scan.inherited.folders', { folders: data.excluded.map((e) => `/${e.path}`).join(', ') })}
          </Text>
        )}
        {patterns.length > 0 && (
          <Text size="sm">
            {t('scan.inherited.patterns', { patterns: [...new Set(patterns)].join(', ') })}
          </Text>
        )}
        <Anchor component={Link} to={`/projects/${projectId}#exclusions`} size="sm">
          {t('scan.inherited.link')}
        </Anchor>
      </Stack>
    </Alert>
  );
}

/**
 * Subcarpetas que el escaneo no recorre en una carpeta guardada (1.4.0): explorador limitado a ella, con casillas, y la
 * lista de las excluidas (también las que ya no existen) para quitarlas. Se puede cambiar con un escaneo en marcha.
 */
export function ExcludeFoldersModal({
  project,
  folder,
  onClose,
}: {
  project: ProjectOut;
  folder: ScannedFolderOut;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const save = useSetExclusions(project.id);
  const saved = folder.excluded ?? [];
  const { excluded, toggle, known, list } = useExclusionSet(
    saved.map((e) => ({ path: e.subpath, exists: e.exists })),
  );
  const removedSaved = saved.some((e) => !excluded.has(e.subpath));
  return (
    <Modal
      opened
      onClose={onClose}
      size="lg"
      title={t('scan.exclusions.title', { folder: folderLabel(folder.subpath) })}
    >
      <Stack>
        <Text size="sm" c="dimmed">
          {t('scan.exclusions.hint')}
        </Text>
        <Input.Wrapper label={t('scan.exclusions.browse')}>
          <FolderBrowser
            locationId={project.source_location.id}
            rootLabel={folderLabel(folder.subpath)}
            basePath={folder.subpath}
            checkable={{
              checked: excluded,
              onChange: toggle,
              label: (name) => t('scan.exclusions.toggle', { name }),
              checkedTag: t('scan.exclusions.tag'),
            }}
          />
        </Input.Wrapper>
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            {t('scan.exclusions.listTitle')}
          </Text>
          {list.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t('scan.exclusions.none')}
            </Text>
          ) : (
            <Stack gap={4} component="ul" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {list.map((path) => (
                <Group key={path} component="li" gap="xs" wrap="nowrap">
                  <Text size="sm" ff="monospace" td="line-through">
                    {folderLabel(path)}
                  </Text>
                  <Badge size="sm" color="gray" variant="light">
                    {t('scan.exclusions.tag')}
                  </Badge>
                  {known.get(path) === false && (
                    <Badge size="sm" color="red" variant="light">
                      {t('scan.folders.missing')}
                    </Badge>
                  )}
                  <Button
                    size="compact-xs"
                    variant="subtle"
                    onClick={() => toggle(path, false)}
                    aria-label={t('scan.exclusions.removeLabel', { folder: folderLabel(path) })}
                  >
                    {t('scan.exclusions.remove')}
                  </Button>
                </Group>
              ))}
            </Stack>
          )}
        </Stack>
        {removedSaved && (
          <Alert color="yellow" title={t('scan.exclusions.reconvertTitle')}>
            {t('scan.exclusions.reconvertBody')}
          </Alert>
        )}
        {save.isError && <ErrorAlert error={save.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            loading={save.isPending}
            onClick={() => save.mutate({ subpath: folder.subpath, excluded: list }, { onSuccess: onClose })}
          >
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
