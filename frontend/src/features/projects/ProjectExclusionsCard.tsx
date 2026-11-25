import {
  Alert,
  Badge,
  Button,
  Card,
  Code,
  Group,
  Input,
  Loader,
  Modal,
  Stack,
  Switch,
  TagsInput,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { FolderBrowser } from '../../components/FolderBrowser';
import {
  canDo,
  type ProjectExclusions,
  type ProjectOut,
  useProjectExclusions,
  useSetProjectExclusions,
} from './useProjects';

function pathLabel(path: string): string {
  return `/${path}`;
}

function PatternList({ patterns }: { patterns: string[] }) {
  return (
    <Group gap={4}>
      {patterns.map((pattern) => (
        <Code key={pattern}>{pattern}</Code>
      ))}
    </Group>
  );
}

/**
 * Edición de las exclusiones del proyecto (2.7): explorador de la ubicación de origen con casillas, patrones de nombre
 * y el preset de carpetas de sistema con su lista visible.
 */
function EditExclusionsModal({
  project,
  value,
  onClose,
}: {
  project: ProjectOut;
  value: ProjectExclusions;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const save = useSetProjectExclusions(project.id);
  const [excluded, setExcluded] = useState<Set<string>>(() => new Set(value.excluded.map((e) => e.path)));
  const [patterns, setPatterns] = useState<string[]>(value.ignore_patterns);
  const [system, setSystem] = useState(value.exclude_system_folders);
  const known = new Map(value.excluded.map((e) => [e.path, e.exists]));
  const toggle = (path: string, checked: boolean) =>
    setExcluded((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(path);
      } else {
        next.delete(path);
      }
      return next;
    });
  const list = [...excluded].sort((a, b) => a.localeCompare(b));
  return (
    <Modal opened onClose={onClose} size="lg" title={t('projects.exclusions.editTitle')}>
      <Stack>
        <Text size="sm" c="dimmed">
          {t('projects.exclusions.editHint')}
        </Text>
        <Input.Wrapper label={t('projects.exclusions.browse')}>
          <FolderBrowser
            locationId={project.source_location.id}
            rootLabel="/"
            basePath=""
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
            {t('projects.exclusions.folders')}
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
                    {pathLabel(path)}
                  </Text>
                  {known.get(path) === false && (
                    <Badge size="sm" color="red" variant="light">
                      {t('scan.folders.missing')}
                    </Badge>
                  )}
                  <Button
                    size="compact-xs"
                    variant="subtle"
                    onClick={() => toggle(path, false)}
                    aria-label={t('scan.exclusions.removeLabel', { folder: pathLabel(path) })}
                  >
                    {t('scan.exclusions.remove')}
                  </Button>
                </Group>
              ))}
            </Stack>
          )}
        </Stack>
        <TagsInput
          label={t('projects.exclusions.patterns')}
          description={t('projects.exclusions.patternsHint')}
          value={patterns}
          onChange={setPatterns}
          clearable
        />
        <Switch
          label={t('projects.exclusions.system')}
          description={t('projects.exclusions.systemHint')}
          checked={system}
          onChange={(event) => setSystem(event.currentTarget.checked)}
        />
        <PatternList patterns={value.system_patterns} />
        {save.isError && <ErrorAlert error={save.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            loading={save.isPending}
            onClick={() =>
              save.mutate(
                { excluded: list, ignore_patterns: patterns, exclude_system_folders: system },
                { onSuccess: onClose },
              )
            }
          >
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/**
 * Exclusiones de todo el proyecto (2.7, ADR-017): valen en escaneo, duplicados, contexto y exportaciones de la caché,
 * junto con las de cada carpeta guardada y los patrones de la ubicación. Las ve cualquier miembro; las cambia el
 * propietario.
 */
export function ProjectExclusionsCard({ project }: { project: ProjectOut }) {
  const { t } = useTranslation();
  const exclusions = useProjectExclusions(project.id);
  const [editing, setEditing] = useState(false);
  const value = exclusions.data;
  return (
    <Card withBorder id="exclusions">
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {t('projects.exclusions.title')}
        </Title>
        {canDo(project, 'owner') && value && (
          <Button
            size="xs"
            variant="light"
            onClick={() => setEditing(true)}
            aria-label={t('projects.exclusions.editLabel')}
          >
            {t('common.edit')}
          </Button>
        )}
      </Group>
      <Text size="sm" c="dimmed" mb="sm">
        {t('projects.exclusions.intro')}
      </Text>
      {exclusions.isPending && <Loader size="sm" aria-label={t('common.loading')} />}
      {exclusions.isError && <ErrorAlert error={exclusions.error} />}
      {value && (
        <Stack gap="xs">
          <Group gap="xs">
            <Text size="sm" fw={500}>
              {t('projects.exclusions.folders')}:
            </Text>
            {value.excluded.length === 0 ? (
              <Text size="sm" c="dimmed">
                {t('scan.exclusions.none')}
              </Text>
            ) : (
              value.excluded.map((item) => (
                <Badge key={item.path} variant="light" color={item.exists === false ? 'red' : 'gray'}>
                  {pathLabel(item.path)}
                </Badge>
              ))
            )}
          </Group>
          <Group gap="xs">
            <Text size="sm" fw={500}>
              {t('projects.exclusions.patterns')}:
            </Text>
            {value.ignore_patterns.length === 0 ? (
              <Text size="sm" c="dimmed">
                {t('projects.exclusions.noPatterns')}
              </Text>
            ) : (
              <PatternList patterns={value.ignore_patterns} />
            )}
          </Group>
          <Text size="sm">
            {value.exclude_system_folders
              ? t('projects.exclusions.systemOn')
              : t('projects.exclusions.systemOff')}
          </Text>
          {value.location_patterns.length > 0 && (
            <Alert color="blue" variant="light" title={t('projects.exclusions.locationTitle')}>
              <PatternList patterns={value.location_patterns} />
            </Alert>
          )}
        </Stack>
      )}
      {editing && value && (
        <EditExclusionsModal project={project} value={value} onClose={() => setEditing(false)} />
      )}
    </Card>
  );
}
