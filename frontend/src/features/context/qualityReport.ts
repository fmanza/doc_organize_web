export type GoldSource = 'xlsx' | 'decisions';

interface AxisReport {
  axis: string;
  labelled: number;
  accuracy: number | null;
  coverage: number | null;
  precision: number | null;
  recall: number | null;
  accuracy_by_classified_by: Record<string, number>;
  labelled_by_classified_by: Record<string, number>;
  confusions: { label: string; assigned: string; count: number }[];
}

export interface Report {
  axes: Record<string, AxisReport>;
  documents: number;
  matched: number;
  missing_documents: string[];
  missing_total?: number;
}

export const pct = (value: number | null | undefined) =>
  typeof value === 'number' ? `${Math.round(value * 100)} %` : '—';
