# PLAN — new_feature: idioma de la interfaz (español e inglés) por usuario

- Skill: `new-feature` · Fases: PLAN + AUDIT_PLAN (IMPLEMENT pendiente de aprobación)
- Base: `develop` en `226ea3e` (refactor de i18n, PR #122: `LANGUAGE`/`INTL_LOCALE`, `src/i18n/i18n.test.ts`)
- Decisiones del usuario (2026-11-25): **D1 = A** (solo interfaz), **D2 = `es`** por defecto, formato **`en-GB`**
- Versión prevista: MINOR **2.6.0** (funcionalidad compatible; migración aditiva)

## Objective

Cada usuario elige el idioma de la interfaz (**Español** o **English**) en el menú de usuario, como el tema: se guarda
en su usuario, se aplica al momento y sin pintar un instante en el otro idioma. Toda la interfaz (textos, `lang` del
documento, fechas y números) sigue ese idioma.

## Inputs

| Input | Valor |
|---|---|
| Objetivo | Selector de idioma por usuario con inglés además de español |
| Rutas | abajo |
| Contrato HTTP | `Me.language`; `Preferences` acepta `language` y/o `color_scheme`; cabecera `Accept-Language` en todas las peticiones |
| Pantallas | Menú de usuario → «Idioma» (junto a «Tema»); inicio de sesión y cambio de contraseña en el idioma de la copia local o del navegador |
| Permisos | Solo el propio usuario (sesión); no se audita (preferencia, como el tema) |
| doc_organize | Ninguno (no cambia lo que se envía a la librería ni sus salidas) |
| Restricciones | Sin dependencias nuevas; migración `0031` aditiva; sin cambios en ubicaciones ni colas |

## Scope and affected paths

### Backend

| Fichero | Cambio |
|---|---|
| `backend/alembic/versions/0031_user_language.py` (nuevo) | `users.language` `String(5)`, `server_default 'es'`, `nullable=False`; downgrade la quita |
| `backend/app/db/models.py` | `User.language` |
| `backend/app/domain/identity/users.py` | `LANGUAGES = ("es", "en")`, `set_language()` (como `set_color_scheme`) |
| `backend/app/api/v1/schemas.py` | `Language = Literal["es", "en"]`; `Me.language`; `Preferences`: `color_scheme` y `language` opcionales, al menos uno (validador → 422) |
| `backend/app/api/v1/auth.py` | `me_out` con `language`; `update_preferences` guarda lo que llegue |
| `backend/tests/api/test_auth*.py` | `language` en `Me`, `PUT` solo idioma, solo tema, ambos, ninguno (422), valor no válido (422) |
| `openapi/openapi.json` + `frontend/src/api/schema.d.ts` | Regenerados (`export_openapi.py`, `npm run gen:api`) |

### Frontend

| Fichero | Cambio |
|---|---|
| `frontend/src/i18n/en/core.json`, `en/features.json` (nuevos) | Traducción completa, mismas claves y mismos `{{marcadores}}` que `es` |
| `frontend/src/i18n/index.ts` | `LANGUAGES = ['es', 'en']`; idioma inicial = copia local (`localStorage`, clave `dow-language`) → `navigator.languages` (`en*` → `en`) → `es`; ambos `core.json` en el bundle inicial (pequeños); `features.json` del idioma activo por `import()` dinámico; `setLanguage(lng)` carga sus `features`, llama a `changeLanguage`, pone `document.documentElement.lang` y guarda la copia local; `intlLocale()` (`{ es: 'es-ES', en: 'en-GB' }`) sustituye a la constante `INTL_LOCALE` |
| `frontend/src/components/format.ts` | Formateadores por idioma (caché por locale) en vez de constantes de módulo |
| `frontend/src/features/admin/AiUsagePage.tsx`, `AiUsageCharts.tsx` | Ídem (`money`, `number`, `compact`, `full`) |
| `frontend/src/app/LanguageSync.tsx` (nuevo) | Al llegar `/me`, aplica `Me.language` si difiere de la copia local (como `ColorSchemeSync`) |
| `frontend/src/app/Providers.tsx` | Monta `LanguageSync` |
| `frontend/src/features/auth/UserMenu.tsx` | Submenú «Idioma» con «Español» / «English» (cada uno en su idioma, `lang` en la opción), guarda con `PUT /me/preferences`; si falla, vuelve al anterior con aviso (como el tema) |
| `frontend/src/api/client.ts` | Middleware que añade `Accept-Language: <idioma activo>` (base para D1-B; inocuo con D1-A) |
| `frontend/src/components/ErrorAlert.tsx` (+ toasts de error) | Según D1 |
| `frontend/index.html` | Sin cambios de fichero (`lang="es"` inicial; `index.ts` lo corrige antes de pintar) |
| `frontend/src/i18n/i18n.test.ts` | + `en` tiene exactamente las claves de `es` y los mismos marcadores en cada texto; + análisis de claves sobre ambos idiomas |
| Tests nuevos | `language.test.tsx`: cambio en el menú (textos en inglés, `lang="en"`, `PUT` con `language`), error al guardar → vuelve, `Me.language` gana a la copia local, inicio de sesión con `navigator.languages = ['en-US']` |
| `frontend/src/test/setup.ts` | Fija `es` en cada test (los tests existentes buscan textos en español) |

### Documentación

- `docs/guides/usuarios_y_sesiones.md`: sección «Idioma» junto a «Tema claro u oscuro» y qué queda en español (D1).
- `CHANGELOG.md` (`[Unreleased]` → 2.6.0), `.github/instructions/frontend.instructions.md` (un texto nuevo va en
  `es` **y** `en`).
- Si D1-B: ADR-016 «Idioma de los mensajes del backend».

## D1 — Mensajes que genera el backend (decidido: A)

Hoy el backend genera en español: ~97 clases de error de dominio (71 con `code` estable) con ~190 `detail` propios
(muchos con nombres interpolados: «La ubicación está en uso: Proyecto A, Proyecto B»), los 422 de validación de
Pydantic, el `error_message` de las ejecuciones y las líneas de log del run (algunas vienen de doc_organize), y los
contenidos que exporta (cabeceras del Excel de la caché, informes de duplicados, sitio del contexto).

| Opción | Qué ve un usuario en inglés | Coste | Riesgo |
|---|---|---|---|
| **A. Solo interfaz (recomendada para la 2.6)** | Toda la interfaz en inglés. En un error de la API: título traducido por `code` (`errors.<code>`, los 71) o por estado HTTP (`errors.http.<status>`) y, debajo, el `detail` del backend tal cual (español). Ejecuciones: el estado y `error_code` ya se traducen (`runs.errors.*`); `error_message` y log, en español. Exportaciones, en español | Bajo: solo frontend + ~80 claves | Mezcla de idiomas en el detalle de los errores; se documenta como limitación |
| B. Backend con `Accept-Language` | Además, `title`/`detail` de los errores y `error_message` en inglés | Alto: catálogo de ~300 textos en el backend, convertir ~190 `raise` con f-strings a mensajes con parámetros, contexto de idioma en la petición y en el worker | Cambio transversal del backend; merece ADR y su propia funcionalidad (2.7) |
| C. Detalles estructurados | El backend devuelve `code` + `params` y el frontend compone el texto en el idioma | Alto: cambia el contrato de errores de ~190 sitios | Igual que B, y además todos los clientes deben conocer cada `code` |

Recomendación: **A** ahora (la interfaz es lo que se usa a diario), con `Accept-Language` ya enviado, y **B** como
funcionalidad posterior con ADR si la mezcla molesta. Exportaciones y sitio del contexto quedan en español en ambas.

## D2 — Idioma por defecto (decidido: `es`)

Recomendación: los usuarios existentes y nuevos, **`es`** (`server_default`): actualizar no cambia el idioma a nadie.
Antes de iniciar sesión (sin preferencia todavía) se usa la copia local o, si no hay, el navegador. No se añade
«Como el navegador» como opción guardada (simplifica y evita que la interfaz cambie según el equipo).

## HTTP contract

- `GET /api/v1/auth/me` → `Me` + `language: "es" | "en"`.
- `PUT /api/v1/auth/me/preferences` con `{ "language"?: "es"|"en", "color_scheme"?: "auto"|"light"|"dark" }`
  (al menos uno; `extra="forbid"`) → `Me`. 422 si vacío o valor no válido. Compatible: el cuerpo actual
  `{ "color_scheme": … }` sigue valiendo.
- Todas las peticiones del frontend llevan `Accept-Language`; con D1-A el backend lo ignora.

## doc_organize usage (verified signatures)

No aplica: ningún punto de entrada nuevo; la capa anticorrupción no cambia.

## Risks

- **Calidad y mantenimiento de la traducción**: ~1 775 textos. El test exige paridad de claves y de `{{marcadores}}`;
  la revisión del inglés la hace una persona antes de publicar (pendiente de verificar el tono y los términos del
  dominio: «tenant», «ubicación» → *location*, «contexto» → *context*, «ejecución» → *run*). Glosario al inicio de
  la traducción, en `.ai/glossary.md`.
- **Fuga de español**: cualquier texto nuevo sin `en` rompe el test (deseable). Los tests de Vitest y los E2E siguen
  en español (se fija `es`).
- **Destello**: sin script previo nuevo: los textos solo aparecen cuando React arranca, y `index.ts` decide el idioma
  de forma síncrona con la copia local antes de pintar. `lang` del documento se corrige en el mismo momento.
- **Carga de `features`**: al cambiar de idioma hay que descargar `en/features.json` (~100 KB) antes de
  `changeLanguage`, o se verían claves. `setLanguage` espera a la carga.
- **Formatos**: `en-GB` (fecha día/mes como en español, 24 h; confirmado) evita ambigüedad de fechas. Moneda del uso de IA sigue en USD.
- **Contrato**: `Preferences.color_scheme` pasa a opcional; el frontend actual siempre lo manda. Cliente regenerado en
  el mismo cambio.
- **Seguridad**: sin impacto (preferencia propia, valores de lista cerrada, `Accept-Language` no se usa en el
  servidor con D1-A).

## Test strategy

- pytest: `tests/api` de `/auth/me` y `/auth/me/preferences` (casos de arriba); migración `0031` arriba/abajo en el
  test de migraciones existente.
- Vitest: `i18n.test.ts` ampliado (paridad), `language.test.tsx` nuevo, formatos en inglés (`formatDateTime`,
  `formatCount`), regresión completa en español.
- E2E: uno corto en `e2e/` que cambia a English, comprueba el menú y la cabecera y vuelve a Español (deja el usuario
  como estaba).
- Comandos completos de «Comandos de desarrollo», `export_openapi.py --check`, `zensical build --strict`.

## AUDIT_PLAN

- **Funcional**: con D2 nadie ve un cambio al actualizar. Con D1-A, en inglés los detalles de error, el log de las
  ejecuciones y las exportaciones siguen en español: aceptable si se documenta; es el principal punto débil.
- **Técnico**: el refactor previo deja un único punto de idioma; el cambio de constantes a formateadores por idioma
  es necesario para cambiar en caliente (no es refactor gratuito). Bundle inicial +~10 KB (`en/core.json`).
- **Seguridad**: `Preferences` con `extra="forbid"` y literales cerrados; sin auditoría, como el tema (coherente con
  la 2.3).
- **Simplificaciones**: sin detector de idioma de i18next (dependencia nueva): unas líneas con `navigator.languages`.
  Sin opción «como el navegador» guardada. Sin traducir la documentación ni las exportaciones.
- **Alcance**: grande por la traducción, pequeño en código. Si se prefiere, se puede entregar en dos PR: (1) mecanismo
  + selector + `en/core.json`, (2) `en/features.json`; pero sin (2) la interfaz quedaría a medias en inglés, así que
  se publica junto.
- **Pendiente de verificar**: tono y terminología del inglés por una persona.

## Verdict

**GO** — D1 = A, D2 = `es` y `en-GB` decididos por el usuario. Queda la revisión humana del inglés antes de publicar.
