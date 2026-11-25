# TRACEABILITY

## Session metadata
- id: 2026-11-25-idioma-ingles
- fecha: 2026-11-25
- rama: `refactor/i18n-requisito` (PR #122), `feat/idioma-ingles` (PR #123), `release/v2.6.0` → `main`
- skill: refactor + new_feature + version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (en ambos flujos)

## Prompt issued
«Revisa si se está usando en toda la WEB frontend\src\i18n como requisito necesario» → `/refactor` con PLAN y
AUDIT_PLAN; «Se puede seleccionar el idioma en la WEB, lo tenemos en inglés» → `/new-feature` (D1 = A solo interfaz,
D2 = `es` por defecto, `en-GB`); «haz el commit, abre el PR y publica la 2.6.0».

## Context supplied
- `frontend/src/i18n/`, `.github/instructions/frontend.instructions.md`, precedente del tema por usuario (2.3:
  `users.color_scheme`, `PUT /auth/me/preferences`, `ColorSchemeSync`, `colorScheme.test.tsx`, `theme.spec.ts`),
  `backend/app/core/errors.py` (65 `code` de error).

## AI output summary
- Auditoría de i18n con el compilador de TypeScript: sin texto JSX fuera de `t()` ni claves inexistentes; un texto
  visible fijo (ejemplo del perfil), `'es-ES'` fijo en 6 formateadores, 13 claves sin uso, «Error» de reserva.
- Refactor (PLAN en `2026-11-25-i18n-requisito/PLAN.md`, GO): `src/i18n/i18n.test.ts` (texto visible fuera de `t()`,
  claves inexistentes, dinámicas sin claves, claves sin uso, excepciones con motivo), comprobado que falla con
  violaciones; PR #122 fusionado (`226ea3e`).
- Funcionalidad (PLAN en esta carpeta, GO): migración `0031` `users.language`; `Me.language`; `Preferences` con
  `language`/`color_scheme` opcionales (al menos uno); selector en el menú de usuario; `LanguageSync`; `src/i18n` con
  copia local `dow-language` → navegador → `es`, `features.json` por idioma bajo demanda, `lang` del documento;
  `cachedFormat` por locale (`en-GB`); `problemTitle` (título por `code`/estado fuera del español);
  `Accept-Language`; traducción `src/i18n/en/` con 4 subagentes en paralelo y glosario común; test de paridad es/en;
  tests y E2E fijados en español (`setup.ts`, Playwright `locale: 'es-ES'`); `language.test.tsx` y
  `language.spec.ts`. PR #123 con CI en verde (E2E incluidos) fusionado (`053f7ea`).
- VERSION: 2.6.0 sincronizada (CHANGELOG, `pyproject.toml`, `app/__init__.py`, `package.json` y lock, `uv.lock`,
  `openapi.json`, `DOW_TAG`), `.ai/product.md` e `INDEX.md`.
- PR #124 `release: v2.6.0` con CI en verde fusionado con squash en `develop` (`54f239d`); CI de `develop` en verde;
  `main` por fast-forward de `37a7e34` a `54f239d`; etiqueta `v2.6.0`; release de GitHub «Latest» con las notas del
  CHANGELOG y la sección «Actualizar» (copia de seguridad, migración `0031` aditiva con todos en español, volver atrás
  con `alembic downgrade 0030` y `DOW_TAG=2.5.0`).
- Sin despliegue local en esta sesión.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN refactor | `.ai/sessions/2026-11-25-i18n-requisito/PLAN.md` | GO, implementado (#122) |
| PLAN funcionalidad | `.ai/sessions/2026-11-25-idioma-ingles/PLAN.md` | GO, implementado (#123) |
| PR de release | https://github.com/fmanza/doc_organize_web/pull/124 | fusionado (`54f239d`) |
| Release | https://github.com/fmanza/doc_organize_web/releases/tag/v2.6.0 | publicada |
| Etiqueta | `v2.6.0` sobre `54f239d` | subida |

## Directrices para Futuras IAs
- **[i18n]**: un texto nuevo va en `src/i18n/es/` y `src/i18n/en/` con la misma clave y marcadores; lo exige
  `src/i18n/i18n.test.ts`, que también falla con claves sin uso (una clave guardada como valor, p. ej. un `message` de
  zod, cuenta como usada si aparece escrita en el código).
- **[i18n]**: jsdom anuncia `en-US` y Chromium de Playwright también: sin `setLanguage('es')` en `src/test/setup.ts` y
  `locale: 'es-ES'` en `playwright.config.ts` los tests verían la interfaz en inglés.
- **[i18n]**: formateadores de `Intl` con `cachedFormat` (`src/components/format.ts`), nunca constantes de módulo: el
  idioma cambia en caliente.
- **[errores]**: un `code` nuevo en `AppError` → su título en `errors.code` de ambos `core.json` (en español solo se
  usa el título del backend).
- **[backend]**: `test_swapped_output_folder_is_not_touched` falla en Windows sin privilegio de symlinks (WinError
  1314); en el CI (Linux) pasa.
- **[git]**: no deshacer una prueba con `git checkout -- <fichero>` si el fichero tiene cambios propios sin commit:
  se pierden (pasó con `features.json`; se recuperó de una copia).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Despliegue local 2.5.0 → 2.6.0 (copia de seguridad, `DOW_TAG=2.6.0`, migración `0031`).
- Revisión humana del tono y la terminología del inglés (dudas: «Submitted», «Built-in», «In / Out / Changed» del
  historial, «Batches»).
- Mensajes del backend en inglés (`Accept-Language`, D1-B) como funcionalidad aparte con ADR si se necesita.
