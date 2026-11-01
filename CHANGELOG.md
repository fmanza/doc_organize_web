# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/). Hasta la 1.0.0, una MINOR por fase del
ROADMAP (`0.<fase+1>.0`).

## [Unreleased]

### Fixed

- **docker**: variante GPU probada con una GPU NVIDIA real (RTX 5070, `sm_120`, driver 616.92): EasyOCR fallaba en
  todos los documentos con OCR porque creaba `~/.EasyOCR` en el sistema de ficheros de solo lectura, y torch perdía la
  caché de kernels CUDA. `runtime-gpu` fija `EASYOCR_MODULE_PATH` y `PYTORCH_KERNEL_CACHE_PATH` en el tmpfs `/tmp`, y
  el entrypoint crea la carpeta de la caché.
- **docker**: `models-init --easyocr` no podía funcionar (la imagen CPU no trae EasyOCR): nuevo servicio
  `models-init-gpu` (perfil `setup-gpu`) con la imagen `runtime-gpu`. Las guías pasaban `python -m …` como comando de
  `models-init`, que ya lo tiene como entrypoint; ahora solo los argumentos (`download --picture-description`).
- **backend**: cada descarga de modelos reescribía `manifest.json` solo con lo pedido y «olvidaba» la visión o EasyOCR
  descargados antes; ahora conserva los grupos opcionales cuyas carpetas siguen en disco.

## [0.5.0] - 2026-11-01

Fase 4 — escaneo y conversión. Con doc_organize **0.10.0**.

### Added

- **backend**: operación `scan` ([guía](docs/guides/escaneo.md)): `ScanCommand.run_streaming` con `ScanOptions`,
  `on_progress` y `CancelToken` en la capa anticorrupción; incremental (solo nuevos o modificados); cada carpeta de
  origen es un ámbito propio (su caché y sus salidas en `Conversión/<carpeta>/`) para que documentos con el mismo
  nombre en carpetas distintas no se pisen (G18) y para no perder la caché de las terminadas (G16); si una carpeta
  falla se siguen las demás; progreso por fases (`discovery`, `conversion`,
  `ocr`) con el documento actual y rutas relativas a la ubicación; recuentos y duraciones (`ScanSummary`,
  `ScanRunReport`) en el resultado del run y errores (`ScanErrorReport`) en la tabla `scan_errors`, sin rutas del
  contenedor.
- **backend**: «forzar reconversión» (`force`): solo propietarios, todas las carpetas, vista previa (`dry_run`: caché,
  documentos que ya no existen y tamaño de las salidas; caduca si cambian las carpetas) y confirmación con el nombre;
  carpeta a carpeta; se niega si una carpeta no se puede leer o su caché tiene documentos de fuera (G19); auditado.
- **backend**: opciones del escaneo validadas contra las capacidades publicadas por los workers vivos de su cola
  (`422 option_unavailable`); «usar GPU» va a la cola `gpu`; `GET /api/v1/instance/capabilities` añade
  `scan_options` y las capacidades `models_ready`, `picture_description_ready` y `gpu_ready`.
- **backend**: carpetas guardadas (`scanned_folders`, migración `0005_scan`): `GET/POST/DELETE
  /api/v1/projects/{id}/scanned-folders` con `used`, último escaneo y disponibilidad; errores paginados en
  `GET /api/v1/runs/{id}/scan-errors` y `GET /api/v1/projects/{id}/scan-errors` (último escaneo).
- **backend**: modelos de Docling sin Internet ([ADR-011](docs/adr/ADR-011-modelos-sin-internet.md)):
  `python -m app.integrations.doc_organize.models download` escribe un manifiesto en `/models/docling` y el job usa
  `DOCLING_ARTIFACTS_PATH`.
- **docker**: variante GPU: grupos de dependencias `cpu` (por defecto) y `gpu` (torch CUDA 13.0 + EasyOCR) en el
  mismo `uv.lock`, etapa `runtime-gpu`, servicio `worker-gpu` (perfil `gpu`, driver NVIDIA ≥ 580); volumen `models` y
  servicio `models-init` (perfil `setup`). La imagen de producción corre con `HF_HUB_OFFLINE=1`.
- **frontend**: pantalla «Escanear» (carpetas con casilla, estado y último escaneo; añadir y quitar; opciones con ayuda
  contextual y desactivadas según la instancia; forzar reconversión en zona roja), página de errores paginada,
  resultado del escaneo y enlace a sus errores en el detalle del run; capacidades de modelos en Ajustes.
- **ci**: E2E de escaneo real con el worker (HTML y TXT sintéticos): progreso, resultado y segundo escaneo con 0
  conversiones. Test de integración (fuera del CI) con conversión real de un PDF generado con Pillow 13, incremental y
  cancelación entre documentos que conserva la caché.
- **docs**: guía [Escaneo y conversión](docs/guides/escaneo.md), ADR-011, notas de la Fase 4 en ADR-002 y ADR-006,
  despliegue con modelos y worker con GPU.

### Changed

- **backend**: al vencer `DOW_JOB_TIMEOUT_SECONDS` el worker pide una **parada ordenada** (`runs.cancel_reason`) y
  espera `DOW_TIMEOUT_GRACE_SECONDS` (10 min) antes de terminar el subproceso: la operación guarda lo hecho y el run
  acaba `failed`/`timeout` con el resultado parcial.
- **backend**: las carpetas de origen de un proyecto ya no pueden anidarse (`422 nested_folders`) en vez de quedarse
  con la de fuera: la ruta de cada salida depende de la carpeta escaneada.
- **frontend**: «Probar el motor» pasa a ser solo para administradores; el proyecto ofrece «Escanear».

### Security

- **backend**: el `run.log` descargable ya no lleva rutas del contenedor ni trazas de las librerías (solo registros de
  la aplicación y avisos, enmascarados, máx. 20 MB); los mensajes de `scan_errors` se enmascaran igual y se guardan
  como mucho 10 000 por run. `models-init` corre sin secretos ni `config.db`.
- **backend**: Pillow **13.0.0** (41 alertas, 5 críticas, al leer JPEG, TIFF, FlashPix y PDF) como mínimo explícito,
  con docling/docling-slim 2.142.0, docling-core 2.104.0, docling-parse 7.22.4 y docling-ibm-models 4.0.4 por
  excepción de seguridad a `exclude-newer` (levantan el límite `pillow<13`).

## [0.4.0] - 2026-11-01

Fase 3 — proyectos y motor de ejecuciones. Con doc_organize **0.10.0**.

### Added

- **backend**: migración `0004_projects_runs` (`projects`, `project_members`, `runs`, `run_events`, `artifacts`,
  `workers`, `periodic_tasks`). Proyectos con origen (ubicación + hasta 20 carpetas) y una carpeta de salidas **propia**
  en una ubicación de destino `rw` (nueva o vacía al crearla), estado de doc_organize en `/data/projects/<id>`
  (`ProjectLayout` con `state_root`, L-5); miembros `owner`/`editor`/`viewer` (cualquier usuario crea proyectos y queda
  como propietario; un admin actúa como propietario de todos); proyecto ajeno o borrado → 404.
- **backend**: motor de ejecuciones ([ADR-002](docs/adr/ADR-002-ejecucion-de-jobs.md)): cola sobre `runs` con reclamo
  atómico (`UPDATE … RETURNING`), colas `cpu`/`gpu`, un subproceso *spawn* por job que recibe solo el `run_id`,
  latido, huérfanos, cancelación cooperativa con terminación forzada fuera de las fases críticas, timeout, una
  escritura por proyecto garantizada por un índice único parcial (`409 write_locked`), tope de 5 runs activos por
  usuario, tareas periódicas (sondeo de ubicaciones, purga del workspace, capacidades) y `run.json`/`run.log` por run.
- **backend**: progreso por **SSE** en `GET /api/v1/runs/{id}/events`, reanudable con `Last-Event-ID`
  ([ADR-008](docs/adr/ADR-008-progreso-sse.md)); historial, detalle, cancelación y descarga de artefactos (adjunto,
  `nosniff`, tipo fijo; 410 tras la retención).
- **backend**: operaciones `noop` (prueba del motor), `history_clear` (`ProjectHistoryCleaner` con `state_root`),
  `project_move` (renombrado atómico o copia → cambio en la BD → borrado del origen, con vuelta atrás si la copia
  falla) y `project_delete` (con o sin las salidas). Las tres que mueven o borran exigen una **vista previa**
  (`dry_run`) de menos de 15 min sin escrituras posteriores y el nombre del proyecto tecleado, rechazan una carpeta de
  salidas sustituida por un enlace y se auditan.
- **backend**: `/api/v1/projects` (+ miembros y lanzar runs), `/api/v1/runs`, `/api/v1/users/lookup`,
  `/api/v1/admin/workers`; ajustes administrables `location_probe_interval_minutes`, `run_retention_days` y
  `user_quota_mb`; `/api/health` añade `worker` (`ok`/`stale`/`none`).
- **frontend**: «Proyectos» (lista, alta con exploradores de origen y destino, dashboard con últimas ejecuciones,
  miembros y zona de peligro con vista previa y confirmación por nombre) y «Ejecuciones» (historial con filtros,
  detalle con progreso en vivo por `EventSource`, anuncios `aria-live` por fase y cada 10 %, avisos, resultado,
  ficheros y cancelación); tarjeta de workers en Ajustes; estado del worker en Inicio.
- **ci**: el E2E levanta `web` + `worker` con un origen de solo lectura y un destino de escritura sintéticos: crea un
  proyecto, sigue el progreso en vivo y cancela una ejecución tras cerrar la pestaña.
- **docs**: ADR-008, notas de implementación en ADR-002/005/007, guías [Proyectos](docs/guides/proyectos.md) y
  [Ejecuciones](docs/guides/ejecuciones.md), despliegue con el worker.

### Changed

- **docker**: el servicio `worker` arranca por defecto (sale del perfil `worker`) y monta las mismas ubicaciones que
  `web`; publica las capacidades de su contenedor y la API deja de lanzar su propio subproceso de capacidades.
- **backend**: borrar una ubicación que usa algún proyecto responde 409.
- **frontend**: la ficha de capacidades indica si no hay worker en marcha y las colas atendidas.
- **backend**: doc_organize **0.10.0** (wheel de su release, SHA-256 `4ca73b85…6fc2` en `uv.lock`), con la API pública
  que necesitan las Fases 3 y siguientes. Sin cambios funcionales en la web.
- **docs**: `DOC_ORGANIZE_GAPS.md` pasa G1–G7, G13 y G15 a «Resueltos» por doc_organize 0.10.0 (G9 y G14 ya lo
  estaban); ADR-006 recoge el workflow de release de doc_organize.
- **ci**: la suite corre en los PR y en `develop`, no en `main`. Los PR se fusionan con squash y `main` avanza por
  fast-forward a un commit de `develop` con el CI en verde (rulesets; `docs/guides/publicar_version.md`).

### Security

- **backend**: certifi 2026.10.18 (retira los raíz de emSign con intermedias comprometidas), filelock 4.2.1 (17
  alertas) y setuptools 84.1.0, con excepción por paquete a `exclude-newer` en `backend/pyproject.toml`. Pillow
  (41 alertas) queda para antes de la Fase 4: exige subir también la familia Docling, que limitaba `pillow<13` hasta
  sus versiones del 2026-10-21/22.

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
