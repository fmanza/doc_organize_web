import type { components } from '../../api/schema';

export type GoldSource = 'xlsx' | 'decisions';

/** Informe de evaluación (`EvaluationReport` de doc_organize) de `context_evaluate` y `context_dry_run`. */
export type Report = components['schemas']['EvaluationReport'];

export const pct = (value: number | null | undefined) =>
  typeof value === 'number' ? `${Math.round(value * 100)} %` : '—';
