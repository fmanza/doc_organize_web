# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/). Hasta la 1.0.0, una MINOR por fase del
ROADMAP (`0.<fase+1>.0`).

## [Unreleased]

### Changed

- **backend**: doc_organize **0.10.0** (wheel de su release, SHA-256 `4ca73b85…6fc2` en `uv.lock`), con la API pública
  que necesitan las Fases 3 y siguientes. Sin cambios funcionales en la web.
- **docs**: `DOC_ORGANIZE_GAPS.md` pasa G1–G7, G13 y G15 a «Resueltos» por doc_organize 0.10.0 (G9 y G14 ya lo
  estaban); ADR-006 recoge el workflow de release de doc_organize.

## [0.3.0] - 2026-10-31

Fase 2 — ubicaciones locales/red y ajustes administrables. Sigue con doc_organize **0.9.3**.

### Added

- **backend**: migración `0003_locations_settings` (`locations`, `app_settings`). Ubicaciones registradas por un admin
  bajo `DOW_LOCATIONS_ROOT` (`/mnt`) con uso (origen/destino/ambas), acceso (`ro`/`rw`), tipo (local/red) y ruta para
  mostrar; la carpeta del contenedor es inmutable y se rechazan solapes, la propia `/mnt` y carpetas que contengan
  `data`/`workspace` ([ADR-007](docs/adr/ADR-007-ubicaciones.md)).
- **backend**: resolvedor único de rutas (`app/domain/locations/paths.py`): solo rutas relativas; rechaza absolutas,
  UNC, unidades, `\`, `..` y bytes nulos (400); `resolve(strict)` + `is_relative_to` contra enlaces simbólicos;
  mismo 404 para «fuera de la ubicación» y «no existe»; montaje caído o colgado → 503 con timeout de E/S.
- **backend**: sondeo de ubicaciones (`ok`/`degraded`/`unavailable`: existencia, lectura, latencia, espacio libre y
  escritura en `rw`) bajo demanda; `/api/health` añade el peor estado agregado (`locations`).
- **backend**: `/api/v1/locations` (CRUD admin, lectura para cualquier sesión sin la ruta del contenedor),
  `/api/v1/fs/browse` (sustituye a `/api/fs/browse`), `/api/v1/admin/mounts`, `/api/v1/admin/settings` y
  `/api/v1/instance/capabilities` + `/api/v1/admin/capabilities/refresh`.
- **backend**: ajustes administrables sin reiniciar con precedencia BD > `DOW_*` > defecto
  ([ADR-012](docs/adr/ADR-012-ajustes-administrables.md)): sesión, bloqueo, contraseña y umbrales del sondeo; auditados.
- **backend**: ficha de capacidades (GPU, Whisper + ffmpeg, LibreOffice) obtenida en un **subproceso** con caché de 1 h:
  importar los detectores de doc_organize carga Docling y torch (G15).
- **frontend**: «Ubicaciones» (lista con semáforo de estado accesible, detalle con explorador), alta/edición con el
  explorador de `/mnt`, «Comprobar» y borrado con confirmación por nombre; componentes `FolderBrowser` y `StatusLight`;
  «Administración → Ajustes» con origen de cada valor y ficha de capacidades.
- **ci**: `docker-compose.e2e.yml` monta una carpeta sintética en `/mnt/e2e` y un E2E registra y explora una ubicación.
- **docs**: ADR-007, ADR-012, guías [Ubicaciones](docs/guides/ubicaciones.md) y
  [Montar carpetas de red](docs/guides/carpetas_de_red.md); hueco G15 en `DOC_ORGANIZE_GAPS.md`; PARIDAD del
  explorador y del semáforo.

### Changed

- **backend**: las dependencias de la API y el CLI reciben los ajustes efectivos (`SettingsDep` = `Settings` con
  `app_settings` aplicado).

## [0.2.0] - 2026-10-31

Fase 1 — identidad y multiusuario. Sigue con doc_organize **0.9.3** (esta fase no usa su API).

### Added

- **backend**: migración `0002_identity` con `tenants` (fila `default`), `users` (`tenant_id`, nombre único en la
  instancia), `sessions` y `audit_log`; contraseñas Argon2id (`pwdlib[argon2]`) con política de 12–128 caracteres,
  distinta del usuario y fuera de las 10 000 más frecuentes de SecLists (también su núcleo sin dígitos ni símbolos);
  bloqueo tras 5 intentos fallidos durante 15 minutos.
- **backend**: sesión de servidor en la cookie `__Host-dow_session` (`HttpOnly; Secure; SameSite=Lax`) con caducidad
  por inactividad y absoluta, rotación al iniciar sesión y CSRF de doble envío firmado (`__Host-dow_csrf` +
  `X-CSRF-Token`); en `development`, `dow_session`/`dow_csrf` sin `Secure`.
- **backend**: `/api/v1/auth` (`csrf`, `login`, `logout`, `me`, `password`), `/api/v1/users` (alta, edición, cambio de
  rol, desactivación, restablecer contraseña y `unlock`), `/api/v1/sessions` (el admin, todas; cada usuario, las
  suyas) y `/api/v1/audit` (filtros por acción, autor y fechas con zona).
- **backend**: `python -m app.cli create-admin --username <u> [--password-stdin]` para el primer administrador.
- **frontend**: inicio de sesión, guardas de ruta, menú de usuario, cambio de contraseña, «Mis sesiones» y
  administración de usuarios (con desbloqueo), sesiones y auditoría; formularios con React Hook Form + Zod; pantallas
  en rutas lazy con `features.json` cargado bajo demanda y librerías en chunks propios (ningún chunk supera 500 kB).
- **ci**: el job `image` crea un admin con el CLI y ejecuta los E2E de login, administración y cambio de contraseña.
- **docs**: guía [usuarios y sesiones](docs/guides/usuarios_y_sesiones.md), primer admin en la guía de despliegue y notas
  de implementación en ADR-003.

### Changed

- **backend**: los errores de dominio (`AppError`) se devuelven como *problem details* con su estado HTTP.
- **docs**: `PARIDAD.md` marca las filas de la Fase 1; borrar usuarios pasa a desactivarlos (sustitución deliberada).

### Security

- Respuesta `401` única en el login (usuario inexistente, desactivado, bloqueado o contraseña errónea) con verificación
  ficticia para igualar tiempos; la auditoría no guarda el nombre probado si el usuario no existe.

## [0.1.0] - 2026-10-31

Fase 0 — fundaciones. Consume doc_organize **0.9.3**.

### Added

- **backend**: esqueleto FastAPI con capas `core`, `db`, `api`, `domain`, `integrations/doc_organize`, `jobs` y
  `workspace`. Ajustes `DOW_*` con Docker secrets (`dow_app_secret_key` y `dow_fernet_keys` obligatorios en
  producción); logs JSON con `request_id` (`X-Request-ID`); errores RFC 9457; cabeceras de seguridad y CSP; SQLite con
  WAL, `synchronous=NORMAL`, `busy_timeout` y claves foráneas; Alembic con la revisión `0001` vacía.
- **backend**: `GET /api/health` (`200 ok` / `503 degraded`) con las versiones de la aplicación y de doc_organize y el
  estado de `config.db`; SPA servida en `/` con *fallback*; `/api/docs` solo en `development` y sin
  `/api/openapi.json` en producción.
- **backend**: capa anticorrupción con test de arquitectura (solo `app/integrations/doc_organize` importa
  doc_organize o Docling; `domain` sin FastAPI); `scripts/export_openapi.py --check`; worker mínimo (`app.jobs.worker`).
- **frontend**: React 19 + TypeScript 5.9 estricto + Vite 8, Mantine 9 (tema claro/oscuro automático), React Router 8,
  TanStack Query 5, i18next en español (`core.json` / `features.json`), cliente `openapi-fetch` generado; layout con
  navegación por fases, página de salud y 404; ESLint, Prettier, Vitest y E2E de humo con Playwright.
- **docker**: Dockerfile multi-stage (`frontend-build`, `backend-build`, `backend-dev`, `runtime` CPU) con usuario no
  root, `read_only`, `tmpfs`, `cap_drop: ALL`, `no-new-privileges` y `HEALTHCHECK`; compose con `web` y `worker`
  (perfil), secretos y volúmenes `data`/`workspace`; `docker-compose.dev.yml` con ubicaciones locales de prueba;
  `scripts/generate_secrets.py`.
- **ci**: jobs `backend`, `frontend`, `docs` (`zensical build --strict`) e `image` (build, `/api/health`, import de
  Docling en la imagen y E2E); Dependabot para uv, npm, Docker y Actions con *cooldown* de 14 días.
- **docs**: sitio Zensical; ADR-001 a ADR-006; `PARIDAD.md` (inventario L-0 de la web integrada: 65 rutas HTTP,
  4 WebSocket y 20 plantillas); guías de desarrollo, despliegue y publicación; `LICENSE` (MIT), `CONTRIBUTING.md` y
  plantillas de issue.
- **ia**: configuración IA para Claude Code y GitHub Copilot (WD-0.3).

### Changed

- **docs**: `DOC_ORGANIZE_GAPS.md` con G14 y la sección «Resueltos» (G9 y G14 por doc_organize 0.9.3; G1 en parte).

### Removed

- `scripts/check_doc_links.py`: lo sustituye `zensical build --strict`.

### Notas

- doc_organize se instala desde el wheel de su release `v0.9.3` (URL + hash en `uv.lock`); torch y torchvision, desde
  el índice CPU de PyTorch.
