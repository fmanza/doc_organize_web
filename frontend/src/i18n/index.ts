import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import core from './es/core.json';

// Español por defecto; un idioma nuevo es otra carpeta con los mismos ficheros y claves.
// `core.json` (menú, salud, textos comunes) va en el bundle inicial; `features.json` (el resto de pantallas) se carga
// una vez con la primera ruta lazy (`loadFeatureMessages`, desde el router, a partir de la Fase 1).
void i18n.use(initReactI18next).init({
  resources: { es: { translation: core } },
  lng: 'es',
  fallbackLng: 'es',
  interpolation: { escapeValue: false },
});

let featureMessages: Promise<void> | null = null;

/** Añade las traducciones de las pantallas (idempotente: se descargan una sola vez). */
export function loadFeatureMessages(): Promise<void> {
  featureMessages ??= import('./es/features.json').then(({ default: messages }) => {
    i18n.addResourceBundle('es', 'translation', messages, true, true);
  });
  return featureMessages;
}

export default i18n;
