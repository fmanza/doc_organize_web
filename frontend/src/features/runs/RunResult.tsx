import { SimpleGrid, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { formatBytes, formatCount, formatSeconds } from '../../components/format';

const BYTES = new Set(['output_bytes', 'state_bytes', 'bytes', 'free_bytes']);
const COUNTS = new Set([
  'output_files',
  'state_files',
  'files',
  'leftovers',
  'steps',
  'folders',
  'scanned',
  'new',
  'modified',
  'unchanged',
  'converted',
  'conversion_errors',
  'ocr_required',
  'ocr_processed',
  'error_retries',
  'error_retries_capped',
  'errors',
  'warnings',
  'cached',
  'orphaned',
]);
const SECONDS = new Set(['duration_seconds', 'discovery_duration_seconds', 'total_conversion_seconds']);
/** Datos técnicos que no aportan al usuario. */
const HIDDEN = new Set(['event_schema_version']);

/** Resultado de un run (recuentos y rutas relativas) como lista de datos legible. */
export function RunResult({ result }: { result: Record<string, unknown> }) {
  const { t } = useTranslation();
  const entries = Object.entries(result).filter(
    ([key, value]) => value !== null && value !== undefined && !HIDDEN.has(key),
  );
  if (entries.length === 0) {
    return null;
  }
  const show = (key: string, value: unknown): string => {
    if (BYTES.has(key) && typeof value === 'number') {
      return formatBytes(value);
    }
    if (COUNTS.has(key) && typeof value === 'number') {
      return formatCount(value);
    }
    if (SECONDS.has(key) && typeof value === 'number') {
      return formatSeconds(value);
    }
    if (typeof value === 'boolean') {
      return t(value ? 'common.yes' : 'common.no');
    }
    return String(value);
  };
  return (
    <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xs" component="dl">
      {entries.map(([key, value]) => (
        <div key={key}>
          <Text size="xs" c="dimmed" component="dt">
            {t(`runs.result.${key}`, { defaultValue: key })}
          </Text>
          <Text component="dd" m={0}>
            {show(key, value)}
          </Text>
        </div>
      ))}
    </SimpleGrid>
  );
}
