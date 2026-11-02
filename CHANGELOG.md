# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/). Hasta la 1.0.0, una MINOR por fase del
ROADMAP (`0.<fase+1>.0`).

## [Unreleased]

## [0.8.0] - 2026-11-02

Fase 7 — contexto y taxonomías. Con doc_organize **0.13.0** (L-8 y L-8a…L-8c, pedidas antes de la fase).

### Added

- **backend**: plantillas de taxonomía ([guía](docs/guides/contexto.md#plantillas-de-taxonomía)):
  - las incluidas en doc_organize (`calidad`, `sgi-integrado`, `sgi-iso27001`) se listan y leen, en solo lectura;
  - las personalizadas viven en `taxonomy_templates` (migración `0007_context`) y las gestiona el admin
    (`PUT`/`DELETE /api/v1/taxonomy-templates/{name}`, auditado), con el Markdown validado por doc_organize. No pueden
    usar el nombre de una incluida (409 `template_builtin`).
  - Mejora opcional: `GET /api/v1/taxonomy-templates/{name}/download` exporta cualquier plantilla como `.md`.
- **backend**: contexto del proyecto ([guía](docs/guides/contexto.md)):
  - run `context_build` (editor, destino `rw`): reúne los documentos convertidos cuyo original, `.md` y `.json` siguen
    ahí; clasifica por dominios (descubiertos, catálogo propio, plantilla o manifiesto del proyecto); copia a la
    carpeta reorganizada sin seguir enlaces; construye el sitio Zensical con `DOW_CONTEXT_SITE_TIMEOUT_SECONDS` (600 s
    por defecto).
    - Los documentos que no se copian y las colisiones de nombre (G30) quedan como avisos.
    - La clasificación se cancela entre documentos.
    - La plantilla se fija al encolar, con su Markdown vigente, que no se devuelve en el run.
  - run `context_delete` (propietario, con vista previa y nombre del proyecto): borra la carpeta reorganizada, el
    sitio, `context.json` y `domains/`. Solo actúa sobre la carpeta de la vista previa confirmada.
  - El resumen y los documentos se proyectan en `project_contexts` y `context_documents`.
    `GET /api/v1/projects/{id}/context` y `.../context/documents` (por dominio o sin clasificar, filtros «no copiados» y
    «nombre repetido») paginan sin leer el destino.
  - `GET`/`PUT /api/v1/projects/{id}/context/taxonomy-manifest`: el manifiesto del proyecto, validado; el `PUT` exige
    editor, destino `rw` y que no haya otra escritura en el proyecto.
- **backend**: sitio aislado ([ADR-010](docs/adr/ADR-010-sitio-de-contexto-aislado.md)):
  - `POST /api/v1/projects/{id}/context/site-session` da una URL `/site/<token>/` con un token firmado, ligado a la
    sesión y al proyecto, que caduca en una hora;
  - `/site/` sirve el sitio con una CSP `sandbox` propia (sin `allow-same-origin`), `no-referrer` y `no-store`, a
    través del resolvedor y sin seguir enlaces. El token no se escribe en los registros.
- **frontend**: pantalla «Contexto» del proyecto: construir con los cuatro catálogos, dominios y documentos paginados,
  avisos, manifiesto editable, borrar en dos pasos y visor del sitio en un iframe `sandbox`. «Plantillas de taxonomía»
  en la administración: duplicar las incluidas, crear, editar, importar y exportar `.md`.
- **docs**: guía `contexto.md` y ADR-010.

### Changed

- **backend**: doc_organize **0.13.0** con el extra `site` (zensical; la imagen no lleva mkdocs). G10 y G27–G29 pasan
  a «Resueltos».
- **backend**: vaciar el histórico del proyecto borra también la proyección del contexto.
- **docker**: uvicorn arranca con `--no-access-log`; el registro de accesos es el de la aplicación, que oculta el
  token del sitio.

### Security

- **backend**: la carpeta reorganizada que se lee de `context.json` (que se puede cambiar desde el recurso de red) se
  valida antes de copiar o borrar (G32), y los temporales `.tmp` que doc_organize escribe sin `O_NOFOLLOW` se quitan
  si no son ficheros normales (G31). Se piden a doc_organize como L-8e y L-8f.

### Notas

- Dos documentos con el mismo nombre en el mismo dominio y tipo se sobrescriben en la carpeta reorganizada (G30,
  limitación de doc_organize): la web los marca y avisa. Pedido como L-8d.
- Un script incrustado en un documento puede leer la URL del sitio con su token: es un riesgo aceptado y acotado
  (lectura del sitio de ese proyecto, una hora como mucho, mientras siga la sesión). Ver ADR-010.

## [0.7.0] - 2026-11-02

Fase 6 — duplicados. Con doc_organize **0.12.1** (L-11a: ruta relativa en `duplicados/` y movimiento sin seguir
enlaces simbólicos).

### Added

- **backend**: duplicados en dos pasos ([guía](docs/guides/duplicados.md)):
  - run `dedup_preview` (editor): busca duplicados exactos, conflictos de versión y, opcionalmente, nombres parecidos
    (umbral 50–100) con el hash de la caché del último escaneo más un `stat` de cada documento (G25), sin tocar
    ningún fichero. Los grupos se guardan en `duplicate_groups` (migración `0006_duplicates`) con rutas relativas; una
    búsqueda nueva sustituye a las anteriores del proyecto. El modo «nombre parecido» se limita a 5 000 documentos sin
    agrupar (`fuzzy_too_large`);
  - run `dedup_apply` con los grupos confirmados y el documento que se conserva en cada uno, en modo `copy` o
    `report_only` (editor) o `move` (propietario, con el origen `rw`). Exige vista previa (`dry_run`) y el nombre del
    proyecto; la vista previa de grupos caduca a los 60 min o si el proyecto cambió. Cada grupo se comprueba justo
    antes de aplicarlo (hash actual y ningún tramo de la ruta es un enlace): si cambió, se salta. Cada fichero movido o
    copiado queda en la auditoría (`duplicate.move`/`duplicate.copy`), más un resumen (`duplicate.apply`) que se
    escribe también si algo falla a mitad. El informe de doc_organize va al estado del proyecto;
  - `GET /api/v1/runs/{id}/duplicate-groups` (paginado, filtro por motivo) y
    `GET /api/v1/projects/{id}/duplicates/last` (última búsqueda y última aplicación).
- **backend**: informe Excel de los grupos (mejora opcional) como artefacto de la búsqueda, con celdas protegidas
  contra fórmulas.
- **frontend**: pantalla «Duplicados»: búsqueda con umbral difuso, grupos lado a lado por motivo, política de
  conservación (más antiguo, más reciente, ruta más corta) con elección manual por grupo, aplicar en dos pasos y aviso
  si ya se aplicaron duplicados después de la búsqueda. Las decisiones se guardan por búsqueda en la pestaña.

### Changed

- **backend**: doc_organize **0.12.1** (L-11a): en `duplicados/` cada fichero conserva su ruta relativa al origen
  (`duplicados/2024/a.pdf`, G24) y doc_organize ya no sigue enlaces simbólicos al mover o copiar (G26). La web pasa
  rutas reales (resueltas una vez por el resolvedor de ubicaciones).
- **backend**: las respuestas de un run `dedup_apply` resumen la lista de grupos en su número.
- **backend**: doc_organize **0.12.0** (L-10a…L-10e), con sus rodeos retirados:
  - la API abre la caché en solo lectura (`CacheManager(read_only=True)`, G21);
  - la búsqueda de la lista de documentos mira la ruta relativa a la carpeta, no la del servidor (G22, retira el
    riesgo aceptado en la 0.6.0), y nuevo filtro por estado de conversión (`conversion_status`);
  - las rutas de las salidas las calcula `resolve_output_paths` de la librería, sin Docling (G20);
  - el escaneo pasa la carpeta de modelos con `ScanOptions.artifacts_path` y sin descargas (G17);
  - los JSON nuevos llevan `source_path` relativa (G23); el visor sigue reescribiendo los antiguos.
  La caché se guarda durante la conversión (G16) y «forzar» no borra salidas de carpetas ilegibles (G19) sin cambios
  en la web.
- **frontend**: filtro «Estado» en la lista de documentos.
- **docs**: doc_organize 0.12.0 publicada (L-10a…L-10e): G16–G23 pasan a «Resueltos» en `DOC_ORGANIZE_GAPS.md`, con
  sus rodeos pendientes de retirar al subir la dependencia, y la deprecación de la web integrada (L-10) pasa a la
  0.13.0 en `TAREAS_DOC_ORGANIZE.md`, `PARIDAD.md`, `DECISIONES_Y_RIESGOS.md` y el README del plan.
- **docs**: guía `duplicados.md`; huecos G24 y G26 resueltos en 0.12.1 (L-11a) y G25 con rodeo en la web.

### Notas

- Una aplicación admite como mucho 10 000 grupos: con más, la pantalla avisa y hay que filtrar por motivo o buscar de
  nuevo tras aplicar una parte.
- El ZIP de exportación del proyecto no incluye el informe de duplicados de doc_organize (lleva rutas absolutas del
  contenedor).

## [0.6.0] - 2026-11-02

Fase 5 — caché, resultados y descargas. Con doc_organize **0.11.0** (L-7, `doc_organize.export`).

### Added

- **backend**: `GET /api/v1/projects/{id}/documents` ([guía](docs/guides/documentos.md)): documentos de la caché de
  doc_organize de todas las carpetas de origen, paginados en servidor (`count_entries`/`load_cache_page`), con búsqueda
  en la ruta y filtro por carpeta; rutas relativas a la carpeta y errores enmascarados.
- **backend**: visor `GET /api/v1/projects/{id}/outputs?path=`: Markdown, JSON e imágenes de `Conversión/` por el
  resolvedor de ubicaciones, leídos desde el descriptor ya abierto (un enlace simbólico no lo saca de la carpeta), con
  tipo fijo, `nosniff`, CSP `sandbox` y máx. 20 MB; el JSON se sirve con `source_path` relativa.
- **backend**: exportaciones como ejecuciones con el fichero como artefacto: `export_zip` (con `dry_run` para ver su
  tamaño; comprueba cuota y espacio libre antes de escribir) y `export_xlsx` (`cache` o `errors`), con
  `doc_organize.export`; cualquier miembro del proyecto puede exportar. Cierra G8 sin copiar código de la web
  integrada.
- **backend**: búsqueda de texto completo (mejora opcional): índice SQLite FTS5 por proyecto (`search.db`, incremental
  por `mtime` y tamaño), actualizado al terminar cada escaneo y con el run `search_index` (editor);
  `GET /api/v1/projects/{id}/search` con fragmentos, todas las palabras, sin tildes, consulta sin sintaxis FTS5 y con
  tiempo acotado (`search_too_broad`).
- **backend**: copias de seguridad (mejora opcional, adelanta parte de la Fase 10): `python -m app.cli backup
  [--dest] [--keep N]` y `verify-backup` de `config.db` y de las cachés con la API de backup de SQLite, manifiesto con
  SHA-256 y permisos solo para el usuario de la aplicación.
- **frontend**: pantalla «Documentos» con lista virtualizada (`@tanstack/react-virtual`), visor Markdown saneado
  (`marked` + DOMPurify: sin scripts, estilos, formularios, marcos ni imágenes externas) y JSON, búsqueda en el
  contenido y panel de exportaciones.

### Changed

- **backend**: doc_organize **0.11.0** con el extra `export` (`openpyxl`). La API importa `doc_organize.cache` solo al
  listar documentos, sin Docling ni torch (G15; lo comprueba el test de arquitectura).
- **backend**: `folder_state` pasa a `app/domain/scan/state.py` (lo usan el escaneo, las exportaciones y la API).
- **backend**, **ci**: regla de versiones con ≥ 2 semanas suspendida hasta la 1.0 (decisión del mantenedor): sin
  `exclude-newer` ni sus excepciones por paquete en `backend/pyproject.toml` (el `uv.lock` no cambia de versiones),
  sin `--before` en npm y sin `cooldown` en Dependabot. La Fase 10 la reactiva.

### Security

- **backend**: los JSON de `Conversión/` que escribe doc_organize llevan `source_path` con la ruta absoluta del
  servidor y el ZIP los copia tal cual (G23); la búsqueda por nombre filtra sobre la ruta absoluta (G22). Riesgos bajos
  aceptados hasta que doc_organize los corrija (L-10e); el visor ya muestra `source_path` relativa.

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
