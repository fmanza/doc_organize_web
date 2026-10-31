# TRACEABILITY

## Session metadata
- id: 2026-10-31-fase1
- fecha: 2026-10-31
- rama: feature/fase-1 (desde develop tras la 0.1.0)
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
/phase — Fase: 1. Alcance: completa. Mejoras opcionales: no. Restricciones: sin dependencias nuevas salvo
pwdlib[argon2] (y react-hook-form, zod); doc_organize 0.9.3 sin cambios.

## Context supplied
- `.ai/*.md`, `docs/plan/ROADMAP.md`, `ARQUITECTURA_PROPUESTA.md`, ADR-003, `PARIDAD.md`
- util_bbdd_web fase 1 (commit `b74eeb7`) y sus Directrices para Futuras IAs

## AI output summary
- PLAN + AUDIT_PLAN (`PLAN.md`): `GO_CONDICIONAL`; el mantenedor aprobó la lista de SecLists, `username` único global y
  desactivar en lugar de borrar → GO.
- IMPLEMENT backend: identidad copiada de UBW y adaptada (prefijos `DOW_`, `tenants` + `tenant_id`, cookies
  `__Host-`, contraseñas comunes con núcleo, `unlock`, sesiones propias para usuarios, filtros de auditoría por autor y
  fechas con zona, auditoría sin el nombre probado si no existe), migración `0002`, CLI; 104 tests.
- IMPLEMENT frontend: auth y admin de UBW adaptados; formularios con React Hook Form + Zod (resolver propio);
  rutas lazy con `loadFeatureMessages`; chunks de librerías; 23 tests; E2E de login, administración y cambio de
  contraseña (6/6 contra la imagen).
- AUDIT_CODE (Code Auditor + Frontend Reviewer + Security Reviewer, en la propia sesión): CSRF en todo método no
  seguro, rotación de sesión, `__Host-`, 401 genérico con tiempo igualado, sin secretos en logs ni auditoría (test con
  `caplog`), 404 para sesiones ajenas, último admin protegido, fechas sin zona → 422. Riesgo aceptado: bloqueo por
  intentos usable para bloquear a un usuario conocido (K1; rate limiting por IP en la Fase 10).
- Validación local: ruff, format, mypy, pytest (104), `export_openapi --check`; format, lint, typecheck, Vitest (23),
  build sin chunks > 500 kB; `zensical build --strict`; imagen (3,02 GB), `/api/health`, E2E 6/6.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-31-fase1/PLAN.md` | emitido (GO tras condiciones) |
| IMPLEMENT | `backend/app/{core,db,domain/identity,api}`, `backend/alembic/versions/0002_identity.py`, `frontend/src/features/{auth,admin}` | completado |
| Guía | `docs/guides/usuarios_y_sesiones.md` | nueva |

## Directrices para Futuras IAs
- **[auth-deps]**: en los routers usa `CurrentUser`, `CurrentSession`, `AdminUser`, `DbSession`, `SettingsDep` y
  `Context` de `app/api/deps.py`; los errores de dominio heredan de `AppError` (`app/core/errors.py`).
- **[cookies]**: los nombres de cookie salen de `Settings.session_cookie`/`csrf_cookie` (`__Host-dow_*`, o `dow_*` en
  `development`); el frontend prueba los dos nombres de la cookie CSRF. Chromium acepta `__Host-` con `Secure` sobre
  `http://127.0.0.1` (verificado en los E2E).
- **[tests-backend]**: `client` usa `base_url="https://testserver"` (cookies `Secure`) y `do_login()` deja
  `X-CSRF-Token` en `client.headers`; para una segunda sesión, `TestClient(client.app, base_url="https://testserver")`.
- **[contraseñas]**: la lista de SecLists casi no tiene entradas de 12+ caracteres; `is_common()` compara también el
  núcleo sin dígitos ni símbolos. Las contraseñas de los tests no pueden tener una palabra común como núcleo.
- **[sqlite-fechas]**: `UTCDateTime` exige `datetime` con zona; los parámetros de fecha de la API usan
  `AwareDatetime` (sin zona → 422, no 500).
- **[openapi-typescript]**: un campo con valor por defecto (p. ej. `UserUpdate.unlock`) sale como obligatorio en
  `schema.d.ts`: el cliente lo envía siempre.
- **[frontend-forms]**: `components/forms.ts` tiene `zodResolver` (sin `@hookform/resolvers`); los mensajes del esquema
  Zod son claves i18n que traduce el componente.
- **[frontend-i18n]**: `core.json` (login, menú, salud, comunes) y `features.json` (pantallas lazy, `admin.*`); cada ruta
  lazy usa `page()` de `app/router.tsx`, que carga `features.json` antes de pintar.
- **[frontend-bundle]**: `vite.config.ts` separa `vendor-react`, `vendor-mantine` y `vendor-app`; ningún chunk supera
  500 kB.
- **[e2e]**: `login.spec.ts` necesita `DOW_E2E_ADMIN_USER`/`DOW_E2E_ADMIN_PASSWORD` (el CI crea `e2e-admin` con el CLI).
  Con Mantine, `getByLabel(..., { exact: true })` falla en campos obligatorios por el asterisco: usar
  `getByRole('textbox', { name, exact: true })`.
- **[imagen]**: 3,02 GB con `pwdlib[argon2]` (+10 MB respecto a la 0.1.0).

## Veredicto final
Veredicto: CLOSED (pendiente de CI del PR y de publicar)
Pendientes al cierre:
- PR `feature/fase-1` → `develop` con CI en verde y release 0.2.0 si el mantenedor lo pide.
