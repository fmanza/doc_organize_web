import { Alert, Button, Group, Modal, Radio, Stack, Text, TextInput } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { type RunRequest, useEnqueueRun } from '../projects/useProjects';
import { RunResult } from '../runs/RunResult';
import { useRun } from '../runs/useRuns';
import {
  choices,
  type DedupChoice,
  type DedupMode,
  fetchAllGroups,
  type GroupOverride,
  type KeepPolicy,
  MAX_APPLY_GROUPS,
} from './useDuplicates';

interface ApplyModalProps {
  projectId: number;
  projectName: string;
  groupsRunId: string;
  policy: KeepPolicy;
  overrides: Record<string, GroupOverride>;
  /** Mover saca ficheros del origen: solo propietarios y con el origen de lectura y escritura. */
  canMove: boolean;
  onClose: () => void;
}

function applyRequest(
  groupsRunId: string,
  mode: DedupMode,
  groups: DedupChoice[],
  confirm: { previewRunId: string; name: string } | null,
): RunRequest {
  return {
    operation: 'dedup_apply',
    groups_run_id: groupsRunId,
    mode,
    groups,
    dry_run: confirm === null,
    preview_run_id: confirm?.previewRunId ?? null,
    confirm_name: confirm?.name ?? null,
  };
}

/**
 * Aplicar los grupos confirmados en dos pasos (regla 7): primero una vista previa (`dry_run`: cuántos ficheros, qué
 * ocupan y qué grupos cambiaron desde la búsqueda) y después escribir el nombre del proyecto.
 */
export function ApplyModal({
  projectId,
  projectName,
  groupsRunId,
  policy,
  overrides,
  canMove,
  onClose,
}: ApplyModalProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const enqueue = useEnqueueRun(projectId);
  const [mode, setMode] = useState<DedupMode>('copy');
  const [selected, setSelected] = useState<DedupChoice[] | null>(null);
  const [collecting, setCollecting] = useState(false);
  const [collectError, setCollectError] = useState<unknown>(null);
  const [dryRunId, setDryRunId] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [tooMany, setTooMany] = useState(false);
  const dryRun = useRun(dryRunId, 1_500);
  const preview = dryRun.data;
  const previewDone = preview !== undefined && preview.status !== 'queued' && preview.status !== 'running';
  // El modo no se cambia mientras se calcula: la vista previa sería de otro modo y el servidor la rechazaría.
  const busy = collecting || enqueue.isPending || (dryRunId !== null && !previewDone);
  const nothingLeft =
    preview?.status === 'succeeded' &&
    typeof preview.result?.files === 'number' &&
    preview.result.files === 0;

  const reset = () => {
    setDryRunId(null);
    setSelected(null);
    setTooMany(false);
    setCollectError(null);
    enqueue.reset();
  };

  const calculate = async () => {
    reset();
    setCollecting(true);
    try {
      const { groups: all, total } = await fetchAllGroups(groupsRunId);
      if (total > MAX_APPLY_GROUPS) {
        setTooMany(true);
        return;
      }
      const groups = choices(all, policy, overrides);
      setSelected(groups);
      if (groups.length > 0) {
        enqueue.mutate(applyRequest(groupsRunId, mode, groups, null), {
          onSuccess: (run) => setDryRunId(run.id),
        });
      }
    } catch (error) {
      setCollectError(error);
    } finally {
      setCollecting(false);
    }
  };

  const apply = () => {
    if (!selected || !dryRunId) return;
    enqueue.mutate(applyRequest(groupsRunId, mode, selected, { previewRunId: dryRunId, name }), {
      onSuccess: (run) => void navigate(`/runs/${run.id}`),
    });
  };

  return (
    <Modal opened onClose={onClose} title={t('duplicates.apply.title')} size="lg">
      <Stack>
        <Radio.Group
          label={t('duplicates.apply.mode')}
          value={mode}
          onChange={(value) => {
            setMode(value as DedupMode);
            reset();
          }}
        >
          <Stack gap="xs" mt="xs">
            <Radio value="copy" disabled={busy} label={t('duplicates.apply.modes.copy')} />
            <Radio
              value="move"
              disabled={busy || !canMove}
              label={t('duplicates.apply.modes.move')}
              description={canMove ? undefined : t('duplicates.apply.moveUnavailable')}
            />
            <Radio value="report_only" disabled={busy} label={t('duplicates.apply.modes.report_only')} />
          </Stack>
        </Radio.Group>

        {dryRunId === null ? (
          <Button onClick={() => void calculate()} loading={collecting || enqueue.isPending}>
            {t('duplicates.apply.calculate')}
          </Button>
        ) : !previewDone ? (
          <Text c="dimmed" role="status">
            {t('duplicates.apply.calculating')}
          </Text>
        ) : preview.status !== 'succeeded' ? (
          <>
            <Alert color="red" role="alert">
              {preview.error_message ?? t('common.errorBody')}
            </Alert>
            <Button variant="default" onClick={() => void calculate()}>
              {t('duplicates.apply.recalculate')}
            </Button>
          </>
        ) : (
          <>
            {preview.result && <RunResult result={preview.result} />}
            {typeof preview.result?.skipped_changed === 'number' && preview.result.skipped_changed > 0 && (
              <Alert color="orange">
                {t('duplicates.apply.changed', { count: preview.result.skipped_changed })}
              </Alert>
            )}
            {mode === 'move' && <Alert color="orange">{t('duplicates.apply.moveWarning')}</Alert>}
            <TextInput
              label={t('duplicates.apply.confirm', { name: projectName })}
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
            />
            <Group justify="flex-end">
              <Button variant="default" onClick={onClose}>
                {t('common.cancel')}
              </Button>
              <Button
                color={mode === 'move' ? 'red' : 'blue'}
                disabled={name.trim() !== projectName || nothingLeft}
                loading={enqueue.isPending}
                onClick={apply}
              >
                {t(`duplicates.apply.run.${mode}`)}
              </Button>
            </Group>
          </>
        )}
        {selected !== null && selected.length === 0 && (
          <Alert color="gray" role="status">
            {t('duplicates.apply.nothing')}
          </Alert>
        )}
        {tooMany && (
          <Alert color="orange" role="alert">
            {t('duplicates.apply.tooMany', { max: MAX_APPLY_GROUPS })}
          </Alert>
        )}
        {collectError !== null && <ErrorAlert error={collectError} />}
        {enqueue.isError && (
          <>
            <ErrorAlert error={enqueue.error} />
            {dryRunId !== null && (
              <Button variant="default" onClick={() => void calculate()}>
                {t('duplicates.apply.recalculate')}
              </Button>
            )}
          </>
        )}
      </Stack>
    </Modal>
  );
}
