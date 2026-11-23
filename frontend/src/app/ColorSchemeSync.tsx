import { useMantineColorScheme } from '@mantine/core';
import { useEffect } from 'react';

import { useMe } from '../features/auth/useAuth';

/**
 * Aplica el tema del usuario (`Me.color_scheme`, 2.3) en cuanto llega `/me` o cambia: gana el del servidor sobre la
 * copia local (otro navegador, otro usuario en este). Elegirlo en el menú cambia `me` al momento (mutación optimista),
 * y si el guardado falla `me` vuelve al anterior y el tema con él.
 */
export function ColorSchemeSync() {
  const { data: me } = useMe();
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  const wanted = me?.color_scheme;

  useEffect(() => {
    if (wanted && wanted !== colorScheme) {
      setColorScheme(wanted);
    }
    // Solo cuando cambia el del servidor: `colorScheme` cambia también por otra pestaña, y eso no se deshace aquí.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wanted]);

  return null;
}
