import { Group, Stack, Table, Text, useComputedColorScheme } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { INTL_LOCALE } from '../../i18n';

/** Un día del consumo: tokens de entrada y de salida. */
export interface DayTokens {
  day: string;
  prompt_tokens: number;
  completion_tokens: number;
}

/**
 * Colores de las dos series (entrada y salida): huecos 1 y 2 de la paleta categórica de referencia, validados con
 * `validate_palette.js` en claro (sobre #fcfcfb) y en oscuro (sobre #1a1a19): todo PASS, contraste ≥ 3:1.
 */
const SERIES = {
  light: { prompt: '#2a78d6', completion: '#eb6834' },
  dark: { prompt: '#3987e5', completion: '#d95926' },
} as const;

const WIDTH = 720;
const HEIGHT = 220;
const PAD = { top: 12, right: 8, bottom: 28, left: 52 };
const GAP = 2; // hueco de superficie entre segmentos y entre columnas
const MAX_BAR = 24;

const compact = new Intl.NumberFormat(INTL_LOCALE, { notation: 'compact', maximumFractionDigits: 1 });
const full = new Intl.NumberFormat(INTL_LOCALE);

/** Escala «limpia» para el eje: 4 marcas redondas hasta cubrir `max`. */
function ticks(max: number): number[] {
  if (max <= 0) {
    return [0];
  }
  const raw = max / 4;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  return Array.from({ length: Math.ceil(max / step) + 1 }, (_, i) => i * step);
}

/** Barra con el extremo de datos redondeado (4 px) y la base recta. */
function topRounded(x: number, y: number, w: number, h: number): string {
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}

/**
 * Tokens por día (IA › Uso, 2.1): columnas apiladas entrada + salida, un solo eje, leyenda, tooltip al pasar por
 * cada día y la misma información como tabla. Los días van en la hora local que dice `timezone`.
 */
export function TokensByDayChart({ days, timezone }: { days: DayTokens[]; timezone: string }) {
  const { t } = useTranslation();
  const scheme = useComputedColorScheme('light');
  const colors = SERIES[scheme === 'dark' ? 'dark' : 'light'];
  const [hover, setHover] = useState<number | null>(null);

  const max = Math.max(0, ...days.map((d) => d.prompt_tokens + d.completion_tokens));
  const marks = ticks(max);
  const top = marks.at(-1) || 1;
  const plotW = WIDTH - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const band = plotW / Math.max(days.length, 1);
  const barW = Math.max(2, Math.min(MAX_BAR, band - GAP));
  const y = (value: number) => PAD.top + plotH - (value / top) * plotH;
  const labelEvery = Math.ceil(days.length / 8);
  const active = hover !== null ? days[hover] : undefined;
  const legend = [
    { key: 'prompt', label: t('ai.usage.local.prompt'), color: colors.prompt },
    { key: 'completion', label: t('ai.usage.local.completion'), color: colors.completion },
  ];

  return (
    <Stack gap="xs">
      <Group gap="md" aria-hidden>
        {legend.map((item) => (
          <Group key={item.key} gap={6}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                background: item.color,
                display: 'inline-block',
              }}
            />
            <Text size="xs" c="dimmed">
              {item.label}
            </Text>
          </Group>
        ))}
        <Text size="xs" c="dimmed">
          {t('ai.usage.local.timezone', { timezone })}
        </Text>
      </Group>
      <div style={{ position: 'relative' }}>
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          width="100%"
          role="img"
          aria-label={t('ai.usage.local.chartLabel', { count: days.length })}
          onMouseLeave={() => setHover(null)}
        >
          {marks.map((value) => (
            <g key={value}>
              <line
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={y(value)}
                y2={y(value)}
                stroke="var(--mantine-color-default-border)"
                strokeWidth={1}
              />
              <text
                x={PAD.left - 6}
                y={y(value)}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={11}
                fill="var(--mantine-color-dimmed)"
              >
                {compact.format(value)}
              </text>
            </g>
          ))}
          {days.map((day, index) => {
            const x = PAD.left + index * band + (band - barW) / 2;
            const promptH = (day.prompt_tokens / top) * plotH;
            const completionH = (day.completion_tokens / top) * plotH;
            const base = PAD.top + plotH;
            const both = promptH > 0 && completionH > 0;
            return (
              <g key={day.day}>
                {promptH > 0 && (
                  <path
                    d={
                      completionH > 0
                        ? `M${x},${base} V${base - promptH} H${x + barW} V${base} Z`
                        : topRounded(x, base - promptH, barW, promptH)
                    }
                    fill={colors.prompt}
                  />
                )}
                {completionH > 0 && (
                  <path
                    d={topRounded(
                      x,
                      base - promptH - completionH,
                      barW,
                      Math.max(completionH - (both ? GAP : 0), 1),
                    )}
                    fill={colors.completion}
                  />
                )}
                {index % labelEvery === 0 && (
                  <text
                    x={x + barW / 2}
                    y={HEIGHT - 8}
                    textAnchor="middle"
                    fontSize={11}
                    fill="var(--mantine-color-dimmed)"
                  >
                    {day.day.slice(5)}
                  </text>
                )}
                {/* Zona de hover más ancha que la columna. */}
                <rect
                  x={PAD.left + index * band}
                  y={PAD.top}
                  width={band}
                  height={plotH}
                  fill="transparent"
                  onMouseEnter={() => setHover(index)}
                />
              </g>
            );
          })}
        </svg>
        {active && hover !== null && (
          <div
            role="tooltip"
            style={{
              position: 'absolute',
              top: 0,
              left: `${((PAD.left + hover * band + band / 2) / WIDTH) * 100}%`,
              transform: 'translateX(-50%)',
              pointerEvents: 'none',
              background: 'var(--mantine-color-body)',
              border: '1px solid var(--mantine-color-default-border)',
              borderRadius: 6,
              padding: '4px 8px',
              whiteSpace: 'nowrap',
            }}
          >
            <Text size="xs" fw={500}>
              {active.day}
            </Text>
            {legend.map((item) => (
              <Group key={item.key} gap={6} wrap="nowrap">
                <span style={{ width: 8, height: 8, borderRadius: 2, background: item.color }} />
                <Text size="xs">
                  {item.label}:{' '}
                  {full.format(item.key === 'prompt' ? active.prompt_tokens : active.completion_tokens)}
                </Text>
              </Group>
            ))}
          </div>
        )}
      </div>
      <Text component="details" size="xs">
        <summary style={{ cursor: 'pointer' }}>{t('ai.usage.local.asTable')}</summary>
        <Table.ScrollContainer minWidth={360} mt={4}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('ai.usage.local.day')}</Table.Th>
                <Table.Th>{t('ai.usage.local.prompt')}</Table.Th>
                <Table.Th>{t('ai.usage.local.completion')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {days.map((day) => (
                <Table.Tr key={day.day}>
                  <Table.Td>{day.day}</Table.Td>
                  <Table.Td>{full.format(day.prompt_tokens)}</Table.Td>
                  <Table.Td>{full.format(day.completion_tokens)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Text>
    </Stack>
  );
}
