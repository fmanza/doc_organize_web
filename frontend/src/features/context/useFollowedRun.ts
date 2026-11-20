import { useState } from 'react';

import { type RunRequest, useEnqueueRun } from '../projects/useProjects';
import { useRun } from '../runs/useRuns';

/** Lanza un run y lo sigue (cada 2 s); `result` es su resultado al terminar bien. */
export function useFollowedRun<T>(projectId: number) {
  const enqueue = useEnqueueRun(projectId);
  const [runId, setRunId] = useState<string | null>(null);
  const run = useRun(runId, 2_000);
  const status = run.data?.status;
  return {
    running: enqueue.isPending || status === 'queued' || status === 'running',
    error: enqueue.error ?? run.error,
    failure: status === 'failed' || status === 'cancelled' ? (run.data?.error_message ?? status) : null,
    result: status === 'succeeded' ? (run.data?.result as T | undefined) : undefined,
    start: (body: RunRequest) => enqueue.mutate(body, { onSuccess: (created) => setRunId(created.id) }),
  };
}
