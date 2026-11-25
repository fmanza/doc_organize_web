import type { TFunction } from 'i18next';

import type { Problem } from '../api/client';
import i18n, { DEFAULT_LANGUAGE, currentLanguage } from '../i18n';

/**
 * Título de un *problem details* en el idioma de la interfaz (2.6). El backend escribe en español: en español se
 * muestra su título tal cual; en otro idioma, el de su `code` (`errors.code.*`) o, sin código, el de su estado HTTP
 * (`errors.http.*`). El `detail` se muestra siempre como llega (en español; decisión D1-A de la 2.6).
 */
export function problemTitle(problem: Problem, t: TFunction): string {
  if (currentLanguage() === DEFAULT_LANGUAGE) {
    return problem.title || t('common.error');
  }
  if (problem.code && i18n.exists(`errors.code.${problem.code}`)) {
    return t(`errors.code.${problem.code}`);
  }
  if (i18n.exists(`errors.http.${problem.status}`)) {
    return t(`errors.http.${problem.status}`);
  }
  return t('common.error');
}
