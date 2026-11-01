const dateTime = new Intl.DateTimeFormat('es-ES', { dateStyle: 'short', timeStyle: 'medium' });

/** Fecha ISO 8601 de la API en hora local. */
export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : '—';
}

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const;
const decimal = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 });
const integer = new Intl.NumberFormat('es-ES');

/** Tamaño en bytes con unidad binaria (1 KB = 1024 B). */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) {
    return '—';
  }
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit === 0 ? integer.format(value) : decimal.format(value)} ${UNITS[unit]}`;
}

/** Número con separador de miles. */
export function formatCount(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : integer.format(value);
}

/** Duración entre dos instantes ISO (o hasta ahora) como `1 h 2 min`, `3 min 4 s` o `5 s`. */
export function formatDuration(startIso: string | null | undefined, endIso?: string | null): string {
  if (!startIso) {
    return '—';
  }
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - new Date(startIso).getTime()) / 1000));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${h} h ${m} min`;
  }
  return m > 0 ? `${m} min ${s} s` : `${s} s`;
}
