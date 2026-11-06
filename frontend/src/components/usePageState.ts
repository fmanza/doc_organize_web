import { useCallback } from 'react';
import { useSearchParams } from 'react-router';

/** Filas por página de todos los listados (web 1.2.0: 25 fijo, sin selector). */
export const PAGE_SIZE = 25;
/** Tamaños que se pueden pedir en la URL: solo el fijo (un `?size=` antiguo se ignora). */
export const PAGE_SIZES = [PAGE_SIZE] as const;

function positive(value: string | null, fallback: number): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export interface PageState {
  page: number;
  pageSize: number;
  offset: number;
  /** `replace`: sin entrada nueva en el historial (vuelta a la 1 al cambiar un filtro). */
  setPage: (page: number, replace?: boolean) => void;
  setPageSize: (size: number) => void;
}

/**
 * Página y tamaño de un listado en la URL (`?page=3&size=50`, o con `prefix` si hay varios en la misma pantalla):
 * se pueden compartir, sobreviven a recargar y «Atrás» vuelve a la página anterior. Cambiar el tamaño vuelve a la 1.
 */
export function usePageState(defaultSize: number = PAGE_SIZE, prefix = ''): PageState {
  const [params, setParams] = useSearchParams();
  const pageKey = `${prefix}page`;
  const sizeKey = `${prefix}size`;
  const page = positive(params.get(pageKey), 1);
  // Solo los tamaños que se ofrecen: un `?size=` a mano no pide más de lo que la API admite.
  const size = positive(params.get(sizeKey), defaultSize);
  const pageSize =
    size === defaultSize || (PAGE_SIZES as readonly number[]).includes(size) ? size : defaultSize;

  const update = useCallback(
    (values: Record<string, number | null>, replace = false) => {
      const next = new URLSearchParams(params);
      for (const [key, value] of Object.entries(values)) {
        if (value === null) {
          next.delete(key);
        } else {
          next.set(key, String(value));
        }
      }
      if (next.toString() !== params.toString()) {
        setParams(next, { preventScrollReset: true, replace });
      }
    },
    [params, setParams],
  );

  return {
    page,
    pageSize,
    offset: (page - 1) * pageSize,
    setPage: (value, replace) => update({ [pageKey]: value > 1 ? value : null }, replace),
    setPageSize: (value) => update({ [sizeKey]: value === defaultSize ? null : value, [pageKey]: null }),
  };
}
