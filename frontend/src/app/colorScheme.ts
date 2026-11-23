import {
  localStorageColorSchemeManager,
  type MantineColorScheme,
  type MantineColorSchemeManager,
} from '@mantine/core';

/**
 * Clave de `localStorage` con la copia local del tema (2.3). Es la de Mantine por defecto y la misma que lee
 * `public/color-scheme.js` antes de que arranque React, para no pintar un instante con el tema equivocado: si cambia
 * aquí, hay que cambiarla allí (lo comprueba `colorScheme.test.ts`).
 */
export const COLOR_SCHEME_STORAGE_KEY = 'mantine-color-scheme-value';

/** Opciones del menú de usuario, en orden; `auto` sigue al sistema operativo. */
export const COLOR_SCHEMES = ['auto', 'light', 'dark'] as const satisfies readonly MantineColorScheme[];

/**
 * Gestor del tema de Mantine: la copia local en `localStorage` (y entre pestañas, con el evento `storage`). La verdad
 * es la preferencia del usuario en el servidor (`Me.color_scheme`), que aplica `ColorSchemeSync` al llegar `/me`.
 */
export function colorSchemeManager(env: 'default' | 'test'): MantineColorSchemeManager {
  return env === 'test'
    ? memoryColorSchemeManager()
    : localStorageColorSchemeManager({ key: COLOR_SCHEME_STORAGE_KEY });
}

/** En los tests, en memoria: jsdom comparte `localStorage` y el tema de un test pasaría al siguiente. */
function memoryColorSchemeManager(): MantineColorSchemeManager {
  let value: MantineColorScheme | null = null;
  return {
    get: (defaultValue) => value ?? defaultValue,
    set: (next) => {
      value = next;
    },
    subscribe: () => undefined,
    unsubscribe: () => undefined,
    clear: () => {
      value = null;
    },
  };
}
