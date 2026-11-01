import {
  Anchor,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { StatusLight } from '../../components/StatusLight';
import { useMe } from '../auth/useAuth';
import { RunsTable } from '../runs/RunsTable';
import { useRuns } from '../runs/useRuns';
import { type DangerousOperation, DangerousOperationModal } from './DangerousOperationModal';
import { MembersPanel } from './MembersPanel';
import { canDo, NOOP_RUN, type ProjectOut, useEnqueueRun, useProject, useUpdateProject } from './useProjects';

const RECENT_RUNS = 10;

function EditProjectModal({ project, onClose }: { project: ProjectOut; onClose: () => void }) {
  const { t } = useTranslation();
  const update = useUpdateProject(project.id);
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? '');
  return (
    <Modal opened onClose={onClose} title={t('projects.edit.title')}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          update.mutate({ name: name.trim(), description }, { onSuccess: onClose });
        }}
      >
        <Stack>
          {update.isError && <ErrorAlert error={update.error} />}
          <TextInput
            label={t('projects.fields.name')}
            description={t('projects.edit.renameHint')}
            required
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            data-autofocus
          />
          <Textarea
            label={t('projects.fields.description')}
            rows={3}
            value={description}
            onChange={(event) => setDescription(event.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={update.isPending} disabled={!name.trim()}>
              {t('common.save')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

/** Dashboard del proyecto (sustituye a `dashboard.html.j2`): origen y destino, acceso al escaneo, últimas ejecuciones,
 * miembros y zona de peligro. «Probar el motor» queda para administradores desde que existe el escaneo (Fase 4). */
export function ProjectDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const id = Number(useParams().projectId);
  const { data: project, isPending, isError, error } = useProject(id);
  const { data: me } = useMe();
  const runs = useRuns({ project_id: id }, 1, RECENT_RUNS);
  const enqueue = useEnqueueRun(id);
  const [editing, setEditing] = useState(false);
  const [danger, setDanger] = useState<DangerousOperation | null>(null);

  if (isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (isError) {
    return <ErrorAlert error={error} />;
  }

  const isOwner = canDo(project, 'owner');
  return (
    <Stack>
      <Anchor component={Link} to="/projects" size="sm">
        {t('projects.back')}
      </Anchor>
      <Group justify="space-between">
        <div>
          <Title order={2}>{project.name}</Title>
          {project.description && <Text c="dimmed">{project.description}</Text>}
        </div>
        <Group>
          <Text size="sm" c="dimmed">
            {t('projects.yourRole', { role: t(`projects.roles.${project.role}`) })}
          </Text>
          {isOwner && (
            <Button variant="default" onClick={() => setEditing(true)}>
              {t('common.edit')}
            </Button>
          )}
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Card withBorder>
          <Group justify="space-between" mb="xs">
            <Title order={3} size="h4">
              {t('projects.fields.source')}
            </Title>
            <StatusLight status={project.source_location.status} />
          </Group>
          <Text>{project.source_location.name}</Text>
          {project.source_subpaths.map((path) => (
            <Text key={path} size="sm" ff="monospace">
              /{path}
            </Text>
          ))}
        </Card>
        <Card withBorder>
          <Group justify="space-between" mb="xs">
            <Title order={3} size="h4">
              {t('projects.fields.destination')}
            </Title>
            <StatusLight status={project.destination_location.status} />
          </Group>
          <Text>{project.destination_location.name}</Text>
          <Text size="sm" ff="monospace">
            /{project.destination_subpath}
          </Text>
        </Card>
      </SimpleGrid>

      <Card withBorder>
        <Group justify="space-between" mb="sm">
          <Title order={3} size="h4">
            {t('projects.recentRuns')}
          </Title>
          <Group>
            <Button component={Link} to={`/projects/${project.id}/scan`}>
              {canDo(project, 'editor') ? t('projects.scan') : t('projects.scanView')}
            </Button>
            {me?.role === 'admin' && (
              <Button
                variant="default"
                loading={enqueue.isPending}
                onClick={() =>
                  enqueue.mutate(NOOP_RUN, { onSuccess: (run) => void navigate(`/runs/${run.id}`) })
                }
              >
                {t('projects.testEngine')}
              </Button>
            )}
            <Anchor component={Link} to={`/runs?project_id=${project.id}`} size="sm">
              {t('projects.allRuns')}
            </Anchor>
          </Group>
        </Group>
        {enqueue.isError && <ErrorAlert error={enqueue.error} mb="sm" />}
        {runs.isPending && <Loader size="sm" aria-label={t('common.loading')} />}
        {runs.isError && <ErrorAlert error={runs.error} />}
        {runs.data?.items.length === 0 && <Text c="dimmed">{t('projects.noRuns')}</Text>}
        {runs.data && runs.data.items.length > 0 && <RunsTable runs={runs.data.items} />}
      </Card>

      <Card withBorder>
        <MembersPanel project={project} />
      </Card>

      {isOwner && (
        <Card withBorder style={{ borderColor: 'var(--mantine-color-red-6)' }}>
          <Title order={3} size="h4" mb="xs">
            {t('projects.danger.title')}
          </Title>
          <Text size="sm" c="dimmed" mb="sm">
            {t('projects.danger.intro')}
          </Text>
          <Group>
            {(['project_move', 'history_clear', 'project_delete'] as const).map((operation) => (
              <Button
                key={operation}
                color="red"
                variant="light"
                disabled={project.active_run}
                onClick={() => setDanger(operation)}
              >
                {t(`projects.danger.${operation}.button`)}
              </Button>
            ))}
          </Group>
          {project.active_run && (
            <Text size="sm" c="dimmed" mt="xs">
              {t('projects.danger.busy')}
            </Text>
          )}
        </Card>
      )}

      {editing && <EditProjectModal project={project} onClose={() => setEditing(false)} />}
      {danger && (
        <DangerousOperationModal project={project} operation={danger} onClose={() => setDanger(null)} />
      )}
    </Stack>
  );
}
