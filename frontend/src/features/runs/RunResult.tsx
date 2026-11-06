import { SimpleGrid, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { formatBytes, formatCount, formatSeconds } from '../../components/format';

const BYTES = new Set([
  'output_bytes',
  'state_bytes',
  'bytes',
  'free_bytes',
  'total_size_bytes',
  'size_bytes',
  'reclaimable_bytes',
]);
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
  'io_errors',
  'errors',
  'warnings',
  'cached',
  'orphaned',
  'file_count',
  'rows',
  'indexed',
  'added',
  'updated',
  'removed',
  'search_indexed',
  'documents',
  'groups',
  'exact_groups',
  'version_groups',
  'fuzzy_groups',
  'duplicate_files',
  'stale_cache',
  'skipped_changed',
  'processed',
  'failed',
  'groups_done',
  'domains',
  'unclassified',
  'collisions',
  'missing_originals',
  'calls',
  'classified',
  'sample_documents',
  'total_documents',
]);
/** Datos que se muestran traducidos (`runs.result.values.<clave>.<valor>`). */
const TRANSLATED = new Set(['mode', 'ai.stopped']);
const SECONDS = new Set(['duration_seconds', 'discovery_duration_seconds', 'total_conversion_seconds']);
/** Datos técnicos que no aportan al usuario (o que se muestran en otra pantalla, como el borrador del manifiesto). */
const HIDDEN = new Set(['event_schema_version', 'manifest_markdown', 'segments']);

/** Aplana un nivel de objetos anidados (`ai.calls`) para mostrarlos como datos sueltos. */
function flatten(result: Record<string, unknown>): [string, unknown][] {
  return Object.entries(result).flatMap(([key, value]): [string, unknown][] =>
    typeof value === 'object' && value !== null && !Array.isArray(value)
      ? Object.entries(value).map(([sub, inner]): [string, unknown] => [`${key}.${sub}`, inner])
      : [[key, value]],
  );
}

/** Texto de un elemento de lista: los objetos del catálogo (`{slug, name}`) se muestran por su nombre. */
function itemText(item: unknown): string {
  if (typeof item === 'object' && item !== null && 'name' in item) {
    return String((item as { name: unknown }).name);
  }
  return String(item);
}

/** Resultado de un run (recuentos y rutas relativas) como lista de datos legible. */
export function RunResult({ result }: { result: Record<string, unknown> }) {
  const { t } = useTranslation();
  const entries = flatten(result).filter(
    ([key, value]) => value !== null && value !== undefined && !HIDDEN.has(key),
  );
  if (entries.length === 0) {
    return null;
  }
  const show = (path: string, value: unknown): string => {
    const key = path.split('.').pop() ?? path;
    if (TRANSLATED.has(path) && typeof value === 'string') {
      return t(`runs.result.values.${path}.${value}`, { defaultValue: value });
    }
    if (BYTES.has(key) && typeof value === 'number') {
      return formatBytes(value);
    }
    if (COUNTS.has(key) && typeof value === 'number') {
      return formatCount(value);
    }
    if (SECONDS.has(key) && typeof value === 'number') {
      return formatSeconds(value);
    }
    if (TRANSLATED.has(key) && typeof value === 'string') {
      return t(`runs.result.values.${key}.${value}`, { defaultValue: value });
    }
    if (Array.isArray(value)) {
      return value.length === 0 ? '—' : value.map(itemText).join(', ');
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
