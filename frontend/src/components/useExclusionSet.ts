import { useState } from 'react';

/** Carpeta excluida ya guardada: ruta y si sigue existiendo en la ubicación. */
export interface SavedExclusion {
  path: string;
  exists: boolean | null;
}

export interface ExclusionSet {
  /** Rutas marcadas ahora (las guardadas al abrir más las que se marcan). */
  excluded: Set<string>;
  /** Marca o desmarca una ruta (firma de `FolderBrowser` `checkable.onChange`). */
  toggle: (path: string, checked: boolean) => void;
  /** Existencia de las rutas guardadas (`null`: sin comprobar); `undefined` para las recién marcadas. */
  known: Map<string, boolean | null>;
  /** `excluded` ordenado alfabéticamente, para la lista y para guardar. */
  list: string[];
}

/** Estado de un editor de carpetas excluidas (2.7): casillas del explorador sobre un `Set` y la lista ordenada. */
export function useExclusionSet(saved: readonly SavedExclusion[]): ExclusionSet {
  const [excluded, setExcluded] = useState<Set<string>>(() => new Set(saved.map((e) => e.path)));
  const known = new Map(saved.map((e) => [e.path, e.exists]));
  const toggle = (path: string, checked: boolean) =>
    setExcluded((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(path);
      } else {
        next.delete(path);
      }
      return next;
    });
  const list = [...excluded].sort((a, b) => a.localeCompare(b));
  return { excluded, toggle, known, list };
}
