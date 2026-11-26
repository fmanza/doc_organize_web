import { useState } from 'react';

import { type RunRequest, useEnqueueRun } from '../projects/useProjects';
import { isOperation, type Operation, type RunOf, useRun } from '../runs/useRuns';

/**
 * Lanza un run de la operación `operation` y lo sigue (cada 2 s); `result` es su resultado tipado al terminar bien
 * (`undefined` mientras tanto, o si el resultado guardado no tenía una forma válida).
 */
export function useFollowedRun<Op extends Operation>(projectId: number, operation: Op) {
  const enqueue = useEnqueueRun(projectId);
  const [runId, setRunId] = useState<string | null>(null);
  const run = useRun(runId, 2_000);
  const data = run.data && isOperation(run.data, operation) ? run.data : undefined;
  const status = run.data?.status;
  const result: NonNullable<RunOf<Op>['result']> | undefined =
    status === 'succeeded' ? (data?.result ?? undefined) : undefined;
  return {
    running: enqueue.isPending || status === 'queued' || status === 'running',
    error: enqueue.error ?? run.error,
    failure: status === 'failed' || status === 'cancelled' ? (run.data?.error_message ?? status) : null,
    result,
    start: (body: Extract<RunRequest, { operation?: Op }>) =>
      enqueue.mutate(body, { onSuccess: (created) => setRunId(created.id) }),
  };
}
