import { useCallback, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';

import { PAGE_SIZE, type PageState, usePageState } from './usePageState';

export type SortOrder = 'asc' | 'desc';

/** Estado de un listado (web 1.2.0): página, búsqueda y orden en la URL, para compartirlo y volver con «Atrás». */
export interface ListState<K extends string = string> {
  paging: PageState;
  q: string;
  setQ: (q: string) => void;
  sort: K | null;
  order: SortOrder;
  /** Ordena por `key`; si ya era esa columna, cambia el sentido. Vuelve a la página 1. */
  toggleSort: (key: K) => void;
  /** Parámetros de la API: `limit`, `offset` y, si los hay, `q`, `sort` y `order`. */
  query: { limit: number; offset: number; q?: string; sort?: K; order?: SortOrder };
}

/**
 * Página, búsqueda (`?q=`) y orden (`?sort=&order=`) de un listado. Con `prefix` caben varios en la misma pantalla.
 * `sortKeys` limita el orden a las columnas que admite la API: un `?sort=` a mano con otra cosa se ignora.
 * `pageSize` (como mucho 25) solo para listados que pesan más por fila.
 */
export function useListState<K extends string>(
  sortKeys: readonly K[],
  prefix = '',
  pageSize: number = PAGE_SIZE,
): ListState<K> {
  // Nunca más de 25 filas (web 1.2.0); un listado pesado (tarjetas de duplicados) puede pedir menos.
  const paging = usePageState(Math.min(pageSize, PAGE_SIZE), prefix);
  const [params, setParams] = useSearchParams();
  const qKey = `${prefix}q`;
  const sortKey = `${prefix}sort`;
  const orderKey = `${prefix}order`;
  const q = params.get(qKey) ?? '';
  const rawSort = params.get(sortKey);
  const sort = rawSort && (sortKeys as readonly string[]).includes(rawSort) ? (rawSort as K) : null;
  const order: SortOrder = params.get(orderKey) === 'desc' ? 'desc' : 'asc';

  const update = useCallback(
    (values: Record<string, string | null>) => {
      const next = new URLSearchParams(params);
      for (const [key, value] of Object.entries(values)) {
        if (value === null || value === '') {
          next.delete(key);
        } else {
          next.set(key, value);
        }
      }
      next.delete(`${prefix}page`); // otra búsqueda u otro orden: de vuelta a la página 1
      if (next.toString() !== params.toString()) {
        setParams(next, { preventScrollReset: true, replace: true });
      }
    },
    [params, setParams, prefix],
  );

  const trimmed = q.trim();
  return {
    paging,
    q,
    setQ: (value) => update({ [qKey]: value }),
    sort,
    order,
    toggleSort: (key) =>
      update({ [sortKey]: key, [orderKey]: sort === key && order === 'asc' ? 'desc' : null }),
    query: {
      limit: paging.pageSize,
      offset: paging.offset,
      ...(trimmed ? { q: trimmed } : {}),
      ...(sort ? { sort, order } : {}),
    },
  };
}

/** Texto comparable para ordenar y buscar en cliente: sin mayúsculas ni tildes. */
function normalize(value: unknown): string {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

/**
 * Lo mismo que un listado del servidor para una lista corta que ya está entera en el cliente: busca en `text(row)`,
 * ordena por `columns[sort](row)` (los vacíos al final) y devuelve la página de 25.
 */
export function useClientTable<T, K extends string>(
  rows: readonly T[] | undefined,
  columns: Record<K, (row: T) => string | number | boolean | null | undefined>,
  text: (row: T) => string,
  prefix = '',
): ListState<K> & { pageRows: T[]; total: number } {
  const keys = useMemo(() => Object.keys(columns) as K[], [columns]);
  const state = useListState<K>(keys, prefix);
  const { q, sort, order } = state;
  const filtered = useMemo(() => {
    const needle = normalize(q.trim());
    const found = needle ? (rows ?? []).filter((row) => normalize(text(row)).includes(needle)) : (rows ?? []);
    return sortRows(found, { sort, order }, (row, key) => columns[key](row));
  }, [rows, q, sort, order, columns, text]);
  const start = state.paging.offset;
  return { ...state, pageRows: filtered.slice(start, start + state.paging.pageSize), total: filtered.length };
}

/** Orden local de una tabla pequeña dentro de otra vista (no va a la URL): la misma interfaz que `useListState`. */
export function useLocalSort<K extends string>(): Pick<ListState<K>, 'sort' | 'order' | 'toggleSort'> {
  const [sort, setSort] = useState<K | null>(null);
  const [order, setOrder] = useState<SortOrder>('asc');
  return {
    sort,
    order,
    toggleSort: (key) => {
      setOrder(sort === key && order === 'asc' ? 'desc' : 'asc');
      setSort(key);
    },
  };
}

function isEmpty(value: unknown): boolean {
  return value === null || value === undefined || value === '';
}

/** Ordena `rows` por `value` en el sentido de `state`, con los vacíos siempre al final; sin columna, tal cual. */
export function sortRows<T, K extends string>(
  rows: readonly T[],
  state: Pick<ListState<K>, 'sort' | 'order'>,
  value: (row: T, key: K) => string | number | boolean | null | undefined,
): T[] {
  const { sort, order } = state;
  if (!sort) {
    return [...rows];
  }
  const direction = order === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const left = value(a, sort);
    const right = value(b, sort);
    if (isEmpty(left) || isEmpty(right)) {
      return isEmpty(left) === isEmpty(right) ? 0 : isEmpty(left) ? 1 : -1;
    }
    if (typeof left === 'number' && typeof right === 'number') {
      return (left - right) * direction;
    }
    return normalize(left).localeCompare(normalize(right), 'es') * direction;
  });
}
