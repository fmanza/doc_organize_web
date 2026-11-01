import { SimpleGrid, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { formatBytes, formatCount } from '../../components/format';

const BYTES = new Set(['output_bytes', 'state_bytes', 'bytes', 'free_bytes']);
const COUNTS = new Set(['output_files', 'state_files', 'files', 'leftovers', 'steps']);

/** Resultado de un run (recuentos y rutas relativas) como lista de datos legible. */
export function RunResult({ result }: { result: Record<string, unknown> }) {
  const { t } = useTranslation();
  const entries = Object.entries(result).filter(([, value]) => value !== null && value !== undefined);
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
