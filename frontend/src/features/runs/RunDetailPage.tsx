import {
  Alert,
  Anchor,
  Button,
  Card,
  Center,
  Group,
  List,
  Loader,
  Modal,
  Progress,
  SimpleGrid,
  Stack,
  Text,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatBytes, formatCount, formatDateTime, formatDuration } from '../../components/format';
import { canDo, type RunRequest, useEnqueueRun, useProject } from '../projects/useProjects';
import { RunResult } from './RunResult';
import { RunStatusBadge } from './RunStatusBadge';
import {
  artifactUrl,
  isActive,
  type RunOut as Run,
  type RunLogEntry,
  type RunProgress,
  useCancelRun,
  useRun,
  useRunEvents,
} from './useRuns';

/** Líneas del log que se ven sin pedir «ver todo» (un escaneo grande deja miles de avisos). */
const LOG_VISIBLE = 200;
/** Fallos de un escaneo tras los que tiene sentido seguir donde se quedó (la caché guarda lo convertido). */
const CONTINUABLE = new Set(['out_of_memory', 'crashed', 'timeout', 'interrupted', 'scan_failed']);

/** Texto del anuncio para lectores de pantalla: solo cambia con la fase o cada 10 % (no en cada evento). */
function useProgressAnnouncement(progress: RunProgress | null): string {
  const { t } = useTranslation();
  const [message, setMessage] = useState('');
  const last = useRef<{ phase: string; decile: number } | null>(null);
  useEffect(() => {
    if (!progress) {
      return;
    }
    const decile = progress.total ? Math.floor((progress.processed / progress.total) * 10) : -1;
    if (last.current?.phase === progress.phase && last.current.decile === decile) {
      return;
    }
    last.current = { phase: progress.phase, decile };
    const phase = t(`runs.phases.${progress.phase}`, { defaultValue: progress.phase });
    setMessage(
      progress.total
        ? t('runs.announce', { phase, percent: Math.min(100, decile * 10) })
        : t('runs.announceNoTotal', { phase, processed: progress.processed }),
    );
  }, [progress, t]);
  return message;
}

/** Detalle de una ejecución: estado, progreso en vivo (SSE), avisos, resultado, artefactos y cancelación. */
export function RunDetailPage() {
  const { t } = useTranslation();
  const runId = useParams().runId ?? '';
  const { data: run, isPending, isError, error } = useRun(runId);
  const active = run ? isActive(run) : false;
  const live = useRunEvents(runId, run !== undefined, active);
  const cancel = useCancelRun();
  const [confirming, setConfirming] = useState(false);
  const progress = live.progress ?? run?.progress ?? null;
  const announcement = useProgressAnnouncement(active ? progress : null);

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

  const percent = progress?.total ? Math.min(100, (progress.processed / progress.total) * 100) : null;
  const facts: [string, string][] = [
    [t('runs.fields.createdBy'), run.created_by_username ?? '—'],
    [t('runs.fields.createdAt'), formatDateTime(run.created_at)],
    [t('runs.fields.startedAt'), formatDateTime(run.started_at)],
    [t('runs.fields.finishedAt'), formatDateTime(run.finished_at)],
    [t('runs.fields.duration'), run.started_at ? formatDuration(run.started_at, run.finished_at) : '—'],
    [t('runs.fields.queue'), run.queue],
  ];

  return (
    <Stack>
      {run.project_id !== null && (
        <Anchor component={Link} to={`/projects/${run.project_id}`} size="sm">
          {t('runs.backToProject', { name: run.project_name })}
        </Anchor>
      )}
      <Group justify="space-between">
        <Title order={2}>
          {t(`runs.operations.${run.operation}`)}
          {run.params.dry_run === true && <> {t('runs.preview')}</>}
        </Title>
        <Group>
          <RunStatusBadge status={run.status} />
          {run.can_cancel && (
            <Button
              color="red"
              variant="light"
              onClick={() => setConfirming(true)}
              disabled={run.cancel_requested}
            >
              {run.cancel_requested ? t('runs.cancelRequested') : t('runs.cancel')}
            </Button>
          )}
        </Group>
      </Group>
      <VisuallyHidden aria-live="polite" aria-atomic="true">
        {announcement}
      </VisuallyHidden>
      {run.status === 'queued' && <Alert color="gray">{t('runs.queuedHint')}</Alert>}
      {active && progress && (
        <Card withBorder>
          <Stack gap="xs">
            <Group justify="space-between">
              <Text fw={500}>{t(`runs.phases.${progress.phase}`, { defaultValue: progress.phase })}</Text>
              <Text size="sm" c="dimmed">
                {progress.total
                  ? t('runs.progressOf', {
                      processed: formatCount(progress.processed),
                      total: formatCount(progress.total),
                    })
                  : t('runs.progressCount', { processed: formatCount(progress.processed) })}
              </Text>
            </Group>
            {percent !== null ? (
              <Progress value={percent} aria-label={t('runs.progressLabel')} animated />
            ) : (
              <Loader size="sm" type="dots" aria-label={t('runs.progressLabel')} />
            )}
            {progress.current && (
              <Text size="xs" c="dimmed" truncate>
                {progress.current}
              </Text>
            )}
          </Stack>
        </Card>
      )}
      {run.status === 'failed' && (
        <Alert color="red" title={t('runs.failed')}>
          {run.error_message ??
            t(`runs.errors.${run.error_code ?? 'internal'}`, { defaultValue: run.error_code })}
        </Alert>
      )}
      {continuable(run) && <ContinueScan run={run} />}
      {typeof run.result?.segments === 'number' && run.result.segments > 1 && (
        <Text size="sm" c="dimmed">
          {t('runs.segments', { count: run.result.segments })}
        </Text>
      )}
      <SimpleGrid cols={{ base: 1, sm: 3 }} component="dl">
        {facts.map(([label, value]) => (
          <div key={label}>
            <Text size="xs" c="dimmed" component="dt">
              {label}
            </Text>
            <Text component="dd" m={0}>
              {value}
            </Text>
          </div>
        ))}
      </SimpleGrid>
      {run.result && (
        <Card withBorder>
          <Title order={3} size="h4" mb="sm">
            {t('runs.resultTitle')}
          </Title>
          <RunResult result={run.result} />
          {run.operation === 'scan' && typeof run.result.errors === 'number' && run.result.errors > 0 && (
            <Anchor component={Link} to={`/runs/${run.id}/errors`} mt="sm" display="inline-block">
              {t('runs.scanErrorsLink', { count: run.result.errors })}
            </Anchor>
          )}
          {run.operation === 'dedup_preview' && run.project_id !== null && (
            <Anchor
              component={Link}
              to={`/projects/${run.project_id}/duplicates?run=${run.id}`}
              mt="sm"
              display="inline-block"
            >
              {t('runs.duplicatesLink')}
            </Anchor>
          )}
          {run.operation === 'context_build' && run.project_id !== null && (
            <Anchor
              component={Link}
              to={`/projects/${run.project_id}/context`}
              mt="sm"
              display="inline-block"
            >
              {t('runs.contextLink')}
            </Anchor>
          )}
        </Card>
      )}
      {live.log.length > 0 && <RunLog log={live.log} />}
      <Card withBorder>
        <Title order={3} size="h4" mb="sm">
          {t('runs.artifactsTitle')}
        </Title>
        {run.workspace_purged && <Text c="dimmed">{t('runs.purged')}</Text>}
        {!run.workspace_purged && run.artifacts.length === 0 && (
          <Text c="dimmed">{t('runs.noArtifacts')}</Text>
        )}
        {!run.workspace_purged && run.artifacts.length > 0 && (
          <List>
            {run.artifacts.map((artifact) => (
              <List.Item key={artifact.id}>
                <Anchor href={artifactUrl(run.id, artifact.id)} download>
                  {artifact.name}
                </Anchor>{' '}
                <Text span size="sm" c="dimmed">
                  ({t(`runs.artifactKinds.${artifact.kind}`)}, {formatBytes(artifact.size_bytes)})
                </Text>
              </List.Item>
            ))}
          </List>
        )}
      </Card>
      <Modal opened={confirming} onClose={() => setConfirming(false)} title={t('runs.cancelTitle')}>
        <Stack>
          <Text>{t('runs.cancelBody')}</Text>
          {cancel.isError && <ErrorAlert error={cancel.error} />}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirming(false)}>
              {t('common.back')}
            </Button>
            <Button
              color="red"
              loading={cancel.isPending}
              onClick={() => cancel.mutate(run.id, { onSuccess: () => setConfirming(false) })}
            >
              {t('runs.cancel')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

function continuable(run: Run): boolean {
  return (
    run.operation === 'scan' &&
    run.project_id !== null &&
    run.params.dry_run !== true &&
    (run.status === 'cancelled' || (run.status === 'failed' && CONTINUABLE.has(run.error_code ?? '')))
  );
}

/**
 * Relanza un escaneo que no terminó con sus mismas opciones (M1, Fase 10): la caché conserva lo convertido y el nuevo
 * solo convierte lo que falta. Sin «forzar»: ya vació la caché la primera vez y repetirlo empezaría de cero.
 */
function ContinueScan({ run }: { run: Run }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const projectId = run.project_id ?? 0;
  const project = useProject(projectId);
  const enqueue = useEnqueueRun(projectId);
  if (!project.data || !canDo(project.data, 'editor')) {
    return null;
  }
  const { force: _force, dry_run: _dryRun, ...params } = run.params;
  return (
    <Alert color="blue" title={t('runs.continue.title')}>
      <Stack gap="xs">
        <Text size="sm">{t('runs.continue.body')}</Text>
        {enqueue.isError && <ErrorAlert error={enqueue.error} />}
        <Group>
          <Button
            size="xs"
            loading={enqueue.isPending}
            disabled={project.data.active_run}
            onClick={() =>
              enqueue.mutate({ ...params, operation: 'scan' } as RunRequest, {
                onSuccess: (next) => void navigate(`/runs/${next.id}`),
              })
            }
          >
            {t('runs.continue.button')}
          </Button>
          {project.data.active_run && (
            <Text size="xs" c="dimmed">
              {t('runs.continue.busy')}
            </Text>
          )}
        </Group>
      </Stack>
    </Alert>
  );
}

/** Avisos del run: los últimos `LOG_VISIBLE` y, a petición, todos. */
function RunLog({ log }: { log: RunLogEntry[] }) {
  const { t } = useTranslation();
  const [all, setAll] = useState(false);
  const hidden = all ? 0 : Math.max(0, log.length - LOG_VISIBLE);
  return (
    <Card withBorder>
      <Title order={3} size="h4" mb="sm">
        {t('runs.logTitle')}
      </Title>
      {hidden > 0 && (
        <Button variant="subtle" size="xs" mb="xs" onClick={() => setAll(true)}>
          {t('runs.logShowAll', { count: hidden })}
        </Button>
      )}
      <List size="sm">
        {log.slice(hidden).map((entry) => (
          <List.Item key={entry.id}>
            {formatDateTime(entry.ts)} — {entry.message}
          </List.Item>
        ))}
      </List>
    </Card>
  );
}
