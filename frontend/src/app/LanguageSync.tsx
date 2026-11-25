import { useEffect } from 'react';

import { useMe } from '../features/auth/useAuth';
import { currentLanguage, setLanguage } from '../i18n';

/**
 * Aplica el idioma del usuario (`Me.language`, 2.6) en cuanto llega `/me` o cambia: gana el del servidor sobre la
 * copia local (otro navegador, otro usuario en este). Elegirlo en el menú cambia `me` al momento (mutación optimista),
 * y si el guardado falla `me` vuelve al anterior y el idioma con él.
 */
export function LanguageSync() {
  const { data: me } = useMe();
  const wanted = me?.language;

  useEffect(() => {
    if (wanted && wanted !== currentLanguage()) {
      void setLanguage(wanted);
    }
  }, [wanted]);

  return null;
}
