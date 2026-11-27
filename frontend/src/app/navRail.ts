import { useState } from 'react';

/** Clave de `localStorage` con la preferencia del menú lateral contraído a una barra de iconos (solo en este navegador). */
export const NAV_RAIL_STORAGE_KEY = 'dow-nav-rail';

function readRail(): boolean {
  try {
    return window.localStorage.getItem(NAV_RAIL_STORAGE_KEY) === '1';
  } catch {
    // Ventana privada o almacenamiento bloqueado: el menú empieza desplegado.
    return false;
  }
}

/**
 * Si el menú lateral está contraído a una barra de iconos y cómo cambiarlo. Es una comodidad de este navegador, no una
 * preferencia del usuario en el servidor: sin `localStorage` funciona igual, solo que no se recuerda.
 */
export function useNavRail(): [boolean, (next: boolean) => void] {
  const [rail, setRail] = useState(readRail);
  const update = (next: boolean) => {
    setRail(next);
    try {
      if (next) {
        window.localStorage.setItem(NAV_RAIL_STORAGE_KEY, '1');
      } else {
        window.localStorage.removeItem(NAV_RAIL_STORAGE_KEY);
      }
    } catch {
      // Sin almacenamiento: el cambio vale para esta visita.
    }
  };
  return [rail, update];
}
