import { Button, CloseButton, Group, Select, Table, TextInput, UnstyledButton } from '@mantine/core';
import { type ReactNode, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { ListState } from './useListState';

/** Cabecera de columna ordenable: botón con flecha y `aria-sort` (accesible con teclado y lector de pantalla). */
export function SortableTh<K extends string>({
  state,
  sortKey,
  children,
}: {
  state: Pick<ListState<K>, 'sort' | 'order' | 'toggleSort'>;
  sortKey: K;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const active = state.sort === sortKey;
  const arrow = active ? (state.order === 'asc' ? '↑' : '↓') : '↕';
  return (
    <Table.Th aria-sort={active ? (state.order === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <UnstyledButton
        onClick={() => state.toggleSort(sortKey)}
        fw={600}
        fz="sm"
        title={t('listing.sortBy')}
        style={{ whiteSpace: 'nowrap' }}
      >
        {children}{' '}
        <span aria-hidden="true" style={{ opacity: active ? 1 : 0.35 }}>
          {arrow}
        </span>
      </UnstyledButton>
    </Table.Th>
  );
}

/**
 * Aspa que vacía un campo de texto, para `rightSection`. Va con `rightSectionPointerEvents="auto"`: Mantine pone
 * `pointer-events: none` en esa sección y, sin ello, el clic atraviesa el botón y llega al campo.
 */
export function ClearSection({ text, onClear }: { text: string; onClear: () => void }) {
  const { t } = useTranslation();
  if (!text) {
    return null;
  }
  return (
    <CloseButton
      aria-label={t('listing.clear')}
      size="sm"
      onMouseDown={(event) => event.preventDefault()} // el foco se queda en el campo
      onClick={onClear}
    />
  );
}

/**
 * Buscador de un listado: etiqueta visible «Buscar», espera 300 ms tras teclear antes de pedir nada y se limpia con
 * el aspa. `label` es el nombre accesible (empieza por «Buscar», WCAG 2.5.3) y el texto de ayuda del campo.
 */
export function SearchBox({
  value,
  onChange,
  label,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder?: string;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState(value);
  // Si el valor cambia desde fuera (URL, «Atrás»), el campo lo sigue: ajuste durante el render, sin efecto.
  const [seen, setSeen] = useState(value);
  if (value !== seen) {
    setSeen(value);
    setText(value);
  }
  useEffect(() => {
    if (text === value) {
      return undefined;
    }
    const timer = window.setTimeout(() => onChange(text), 300);
    return () => window.clearTimeout(timer);
  }, [text, value, onChange]);
  return (
    <TextInput
      label={t('listing.searchLabel')}
      aria-label={label}
      placeholder={placeholder ?? label}
      value={text}
      onChange={(event) => setText(event.currentTarget.value)}
      maxLength={100}
      maw={360}
      rightSectionPointerEvents="auto"
      rightSection={
        <ClearSection
          text={text}
          onClear={() => {
            setText('');
            onChange('');
          }}
        />
      }
    />
  );
}

/** «Ordenar por» para listados sin cabeceras (p. ej. tarjetas): columna y botón de sentido. */
export function SortSelect<K extends string>({
  state,
  options,
  label,
}: {
  state: Pick<ListState<K>, 'sort' | 'order' | 'toggleSort'>;
  options: { value: K; label: string }[];
  label: string;
}) {
  const { t } = useTranslation();
  const current = state.sort ?? options[0]?.value ?? null;
  return (
    <Group gap="xs" align="flex-end">
      <Select
        label={label}
        size="sm"
        w={220}
        allowDeselect={false}
        data={options}
        value={current}
        onChange={(value) => {
          if (value && value !== state.sort) {
            state.toggleSort(value as K);
          }
        }}
      />
      <Button
        variant="default"
        size="sm"
        onClick={() => current && state.toggleSort(current as K)}
        aria-label={t(state.order === 'asc' ? 'listing.ascending' : 'listing.descending')}
        title={t(state.order === 'asc' ? 'listing.ascending' : 'listing.descending')}
      >
        <span aria-hidden="true">{state.order === 'asc' ? '↑' : '↓'}</span>
      </Button>
    </Group>
  );
}
