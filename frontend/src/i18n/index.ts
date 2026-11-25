import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import enCore from './en/core.json';
import esCore from './es/core.json';

/** Idiomas de la interfaz (2.6), en el orden del menú; el primero es el de por defecto. */
export const LANGUAGES = ['es', 'en'] as const;
export type Language = (typeof LANGUAGES)[number];
export const DEFAULT_LANGUAGE: Language = 'es';

/** Locale de `Intl` (fechas y números) de cada idioma: `en-GB` para día/mes y 24 h, como en español. */
const INTL_LOCALES: Readonly<Record<Language, string>> = { es: 'es-ES', en: 'en-GB' };

/**
 * Clave de `localStorage` con la copia local del idioma: decide el idioma antes de pintar (también en el inicio de
 * sesión). La verdad es `Me.language`, que aplica `LanguageSync` al llegar `/me`.
 */
export const LANGUAGE_STORAGE_KEY = 'dow-language';

export const isLanguage = (value: unknown): value is Language => LANGUAGES.includes(value as Language);

/** Copia local → idiomas del navegador (`en-US` → `en`) → español. */
export function initialLanguage(): Language {
  try {
    const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (isLanguage(stored)) {
      return stored;
    }
  } catch {
    // Sin localStorage (ventana privada, almacenamiento bloqueado): se sigue con el navegador.
  }
  for (const tag of globalThis.navigator?.languages ?? []) {
    const base = tag.toLowerCase().split('-')[0];
    if (isLanguage(base)) {
      return base;
    }
  }
  return DEFAULT_LANGUAGE;
}

/** Idioma activo de la interfaz. */
export const currentLanguage = (): Language => (isLanguage(i18n.language) ? i18n.language : DEFAULT_LANGUAGE);

/** Locale de `Intl` del idioma activo. */
export const intlLocale = (): string => INTL_LOCALES[currentLanguage()];

// `core.json` de cada idioma (menú, salud, textos comunes; pequeño) va en el bundle inicial; `features.json` (el resto
// de pantallas) se descarga del idioma activo con la primera ruta lazy (`loadFeatureMessages`, desde el router).
const language = initialLanguage();
void i18n.use(initReactI18next).init({
  resources: { es: { translation: esCore }, en: { translation: enCore } },
  lng: language,
  fallbackLng: DEFAULT_LANGUAGE,
  interpolation: { escapeValue: false },
});
document.documentElement.lang = language;

const FEATURES: Record<Language, () => Promise<{ default: object }>> = {
  es: () => import('./es/features.json'),
  en: () => import('./en/features.json'),
};
const featureMessages = new Map<Language, Promise<void>>();

function loadFeatures(lng: Language): Promise<void> {
  let pending = featureMessages.get(lng);
  if (!pending) {
    pending = FEATURES[lng]().then(({ default: messages }) => {
      i18n.addResourceBundle(lng, 'translation', messages, true, true);
    });
    featureMessages.set(lng, pending);
  }
  return pending;
}

/** Añade las traducciones de las pantallas del idioma activo (idempotente: cada idioma se descarga una sola vez). */
export function loadFeatureMessages(): Promise<void> {
  return loadFeatures(currentLanguage());
}

/**
 * Cambia el idioma de la interfaz: descarga antes sus pantallas (si ya se cargaron las de otro, para no ver claves),
 * cambia i18next y `lang` del documento y guarda la copia local.
 */
export async function setLanguage(lng: Language): Promise<void> {
  if (featureMessages.size > 0) {
    await loadFeatures(lng);
  }
  await i18n.changeLanguage(lng);
  document.documentElement.lang = lng;
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, lng);
  } catch {
    // Sin localStorage: el idioma se aplica igual; en la próxima carga lo dirá `Me.language`.
  }
}

export default i18n;
