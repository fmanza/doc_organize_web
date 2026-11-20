import {
  Anchor,
  Button,
  Card,
  Center,
  Checkbox,
  Group,
  Loader,
  Modal,
  NumberInput,
  SimpleGrid,
  Select,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { BackLink } from '../../components/BackLink';
import { ErrorAlert } from '../../components/ErrorAlert';
import { StatusLight } from '../../components/StatusLight';
import { useAiStatus } from '../admin/useAi';
import { useMe } from '../auth/useAuth';
import { RunsTable } from '../runs/RunsTable';
import { useRuns } from '../runs/useRuns';
import { type DangerousOperation, DangerousOperationModal } from './DangerousOperationModal';
import { MembersPanel } from './MembersPanel';
import {
  canDo,
  NOOP_RUN,
  type ProjectOut,
  useEnqueueRun,
  useProject,
  useUpdateProject,
  useUpdateProjectAi,
} from './useProjects';

const RECENT_RUNS = 10;

function EditProjectModal({ project, onClose }: { project: ProjectOut; onClose: () => void }) {
  const { t } = useTranslation();
  const update = useUpdateProject(project.id);
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? '');
  const [captureOwner, setCaptureOwner] = useState(project.capture_owner);
  return (
    <Modal opened onClose={onClose} title={t('projects.edit.title')}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          update.mutate(
            { name: name.trim(), description, capture_owner: captureOwner },
            { onSuccess: onClose },
          );
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
          {/* web 1.5.0 (doc_organize 1.5.0): el modal solo lo abre el owner (y el admin, que entra como owner). */}
          <Checkbox
            label={t('projects.edit.captureOwner')}
            description={t('projects.edit.captureOwnerHint')}
            checked={captureOwner}
            onChange={(event) => setCaptureOwner(event.currentTarget.checked)}
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
/**
 * IA del proyecto (W4, D7): redactar las credenciales de lo que sale hacia la IA y del sitio publicado. Activado por
 * defecto; desactivarlo pide confirmación porque envía las credenciales tal cual.
 */
function AiSettingsCard({ project }: { project: ProjectOut }) {
  const { t } = useTranslation();
  const update = useUpdateProjectAi(project.id);
  const status = useAiStatus();
  const embedReady = status.data ? status.data.embed === true : undefined;
  const [confirming, setConfirming] = useState(false);
  const writable = project.destination_location.access === 'rw';
  const set = (value: boolean) =>
    update.mutate({ ai_redact_credentials: value }, { onSuccess: () => setConfirming(false) });
  return (
    <Card withBorder component="section" aria-label={t('projects.ai.title')}>
      <Title order={3} size="h4" mb="xs">
        {t('projects.ai.title')}
      </Title>
      <Switch
        label={t('projects.ai.redact')}
        description={t('projects.ai.redactHelp')}
        checked={project.ai_redact_credentials}
        disabled={!writable || update.isPending}
        onChange={(event) => (event.currentTarget.checked ? set(true) : setConfirming(true))}
      />
      {!project.ai_redact_credentials && (
        <Text size="sm" c="orange" mt="xs">
          {t('projects.ai.redactOff')}
        </Text>
      )}
      <Select
        mt="md"
        label={t('projects.ai.versions')}
        description={t('projects.ai.versionsHelp')}
        value={project.context_versions}
        allowDeselect={false}
        disabled={!writable || update.isPending}
        data={(['mark', 'current_only', 'all'] as const).map((value) => ({
          value,
          label: t(`projects.ai.versionModes.${value}`),
        }))}
        onChange={(value) =>
          value && update.mutate({ context_versions: value as ProjectOut['context_versions'] })
        }
      />
      <Switch
        mt="md"
        label={t('projects.ai.semantic')}
        description={t('projects.ai.semanticHelp')}
        checked={project.context_semantic}
        disabled={!writable || update.isPending}
        onChange={(event) => update.mutate({ context_semantic: event.currentTarget.checked })}
      />
      {project.context_semantic && (
        <>
          <NumberInput
            mt="xs"
            w={220}
            label={t('projects.ai.threshold')}
            description={t('projects.ai.thresholdHelp')}
            min={0}
            max={1}
            step={0.05}
            decimalScale={2}
            defaultValue={project.context_semantic_threshold}
            disabled={!writable || update.isPending}
            onBlur={(event) => {
              const value = Number(event.currentTarget.value.replace(',', '.'));
              if (
                !Number.isNaN(value) &&
                value >= 0 &&
                value <= 1 &&
                value !== project.context_semantic_threshold
              ) {
                update.mutate({ context_semantic_threshold: value });
              }
            }}
          />
          {embedReady === false && (
            <Text size="sm" c="orange" mt="xs">
              {t('projects.ai.semanticNotConfigured')}
            </Text>
          )}
        </>
      )}
      {!writable && (
        <Text size="xs" c="dimmed" mt="xs">
          {t('projects.ai.readOnly')}
        </Text>
      )}
      {update.isError && <ErrorAlert error={update.error} mt="xs" />}
      <Modal opened={confirming} onClose={() => setConfirming(false)} title={t('projects.ai.confirmTitle')}>
        <Stack>
          <Text>{t('projects.ai.confirm')}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirming(false)}>
              {t('common.cancel')}
            </Button>
            <Button color="red" loading={update.isPending} onClick={() => set(false)}>
              {t('projects.ai.confirmButton')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Card>
  );
}

export function ProjectDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const id = Number(useParams().projectId);
  const { data: project, isPending, isError, error } = useProject(id);
  const { data: me } = useMe();
  const runs = useRuns({ project_id: id }, { limit: RECENT_RUNS, offset: 0 });
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
      <BackLink to="/projects">{t('projects.back')}</BackLink>
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
            <Button component={Link} to={`/projects/${project.id}/duplicates`} variant="light">
              {t('projects.duplicates')}
            </Button>
            <Button component={Link} to={`/projects/${project.id}/scan`}>
              {canDo(project, 'editor') ? t('projects.scan') : t('projects.scanView')}
            </Button>
            <Button component={Link} to={`/projects/${project.id}/documents`} variant="light">
              {t('projects.documents')}
            </Button>
            <Button component={Link} to={`/projects/${project.id}/context`} variant="light">
              {t('projects.context')}
            </Button>
            {me?.is_instance_admin && (
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

      {canDo(project, 'editor') && <AiSettingsCard project={project} />}

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
