# PLAN + AUDIT_PLAN — Fase 3 (Proyectos y motor de ejecuciones → 0.4.0)

## PLAN

### Historias y DoD

- Como **usuario** creo un proyecto eligiendo origen (ubicación `source`/`both` + una o varias subcarpetas) y destino
  (ubicación `destination`/`both` con acceso `rw` + carpeta), y quedo como propietario.
- Como **propietario** invito miembros (`owner`/`editor`/`viewer`), les cambio el rol y los quito.
- Como **editor** lanzo una ejecución, sigo su progreso aunque cierre la pestaña, la cancelo y veo el historial del
  proyecto **agrupado por ejecución** (estado, duración, quién, artefactos y registro).
- Como **propietario** renombro el proyecto y, con vista previa y confirmación, lo muevo a otro destino, vacío su
  histórico o lo borro (conservando o borrando las salidas).
- Como **admin** veo los workers vivos y sus colas, y los ajustes de retención, cuota y sondeo periódico.

DoD común del ROADMAP: comandos en verde, OpenAPI + cliente, migración `0004` con `downgrade`, tests 401/403/404 e
IDOR entre proyectos, imagen + `/api/health`, CHANGELOG, guías, TRACEABILITY y `PARIDAD.md` (proyectos y dashboard).

### doc_organize: versión y firmas verificadas

Requiere **0.10.0 (L-1, L-4, L-5)**: publicada y fijada en `backend/pyproject.toml` desde 2026-10-31. Firmas leídas en
el tag `v0.10.0` del clon local (`../doc_organize`, solo lectura):

| Nombre | Firma (v0.10.0) | Uso en la Fase 3 |
|---|---|---|
| `ProjectLayout` | `@dataclass(frozen=True) ProjectLayout(output_root: Path, state_root: Path \| None = None)`; propiedades `conversion_dir`, `duplicates_dir`, `site_dir`, `cache_db`, `scan_history_log`, `dedup_report_dir`… | Rutas del proyecto en el **worker** con `state_root=/data/projects/<id>` (G4/G5 resueltos) |
| `Project` | `Project(name: str, root_path: str, created_at: str, tenant_id="default")` (Pydantic) | Argumento del limpiador; sin `tenant_id` (obsoleto, L-6c) |
| `ProjectHistoryCleaner` | `async clear(project: Project, *, state_root: Path \| None = None) -> None`; `ProjectError` si falta la carpeta o no puede borrar | Run `history_clear`: vacía salidas y estado y **regenera `project.json`** en la raíz de salidas |
| `CancelToken` | `cancel()`, `cancelled`, `raise_if_cancelled()` (lanza `OperationCancelledError`) | Puente desde `runs.cancel_requested` en el subproceso (se usará en la Fase 4; aquí lo usa `noop` vía la capa) |
| `ProgressEvent` | `operation: Literal["scan","deduplicate","context_build"]`, `phase`, `processed`, `total`, `current` | Solo el formato de referencia: el evento propio `progress` de la web lo replica (la traducción llega con `scan`) |

`ProjectRegistry.move_project_root`/`delete_project` **no se usan**: están atados a `projects.json` (G4: la web no usa el
registro). Mover y borrar son operaciones de la web sobre carpetas que ella misma gestiona (abajo).

Nada de lo anterior se importa en la API: solo el subproceso del job, a través de `app/integrations/doc_organize/`.

### Modelo de datos — Alembic `0004_projects_runs`

| Tabla | Columnas | Notas |
|---|---|---|
| `projects` | `id`, `tenant_id`, `name` (único por tenant, sin distinguir mayúsculas), `description`, `source_location_id` (FK RESTRICT), `source_subpaths` (JSON, 1–20 rutas relativas normalizadas), `destination_location_id` (FK RESTRICT), `destination_subpath`, `status` (`active`/`deleted`), `created_by`, `created_at`, `updated_at`, `deleted_at` | Borrado lógico: los runs y la auditoría siguen apuntando al proyecto |
| `project_members` | `project_id`, `user_id` (PK compuesta), `role` (`owner`/`editor`/`viewer`), `added_by`, `added_at` | Al menos un `owner` |
| `runs` | `id` (UUID), `project_id` (FK, nullable para runs de sistema), `operation`, `queue` (`cpu`/`gpu`), `status` (`queued`/`running`/`succeeded`/`failed`/`cancelled`), `is_write`, `params` (JSON, sin secretos), `progress` (JSON: fase, procesados, total, actual), `result` (JSON), `error_code`, `error_message` (texto seguro), `cancel_requested`, `created_by`, `worker_id`, `created_at`, `started_at`, `finished_at`, `heartbeat_at`, `workspace_purged_at` | Índice `(status, queue, created_at)` para el reclamo; **índice único parcial** `(project_id) WHERE is_write AND status IN ('queued','running')` = una escritura por proyecto garantizada por la BD (SQLite y PostgreSQL) |
| `run_events` | `run_id`, `seq` (PK compuesta), `ts`, `type`, `data` (JSON) | Fuente del SSE y de `Last-Event-ID`; se borran con el run al purgar |
| `artifacts` | `id`, `run_id`, `name`, `kind` (`log`/`output`/`report`), `rel_path` (relativa a la carpeta del run), `size_bytes`, `content_type`, `created_at` | Descarga solo por id |
| `workers` | `id` (`hostname:pid`), `queues` (JSON), `version`, `doc_organize_version`, `started_at`, `heartbeat_at`, `capabilities` (JSON), `capabilities_at`, `refresh_requested` | Publica las capacidades (pendiente de la Fase 2) |

`DELETE /locations/{id}` → **409** si un proyecto activo la usa (anunciado en la Fase 2).

### Carpetas y rutas (resolvedor de ubicaciones, ADR-005/007)

| Zona | Ruta | Cómo se construye |
|---|---|---|
| Origen | `source_location.container_path / subpath` | Cada subruta pasa por `resolve_within` al crear/editar y otra vez en el worker al usarla |
| Salidas (`output_root`) | `destination_location.container_path / destination_subpath` | `resolve_within` de la carpeta padre + nombre nuevo validado (abajo) |
| Estado (`state_root`) | `DOW_DATA_DIR/projects/<id>/` | Solo con el id; `cache.db` e historiales de doc_organize viven aquí (SQLite nunca en red) |
| Artefactos | `DOW_WORKSPACE_DIR/runs/<run_id>/{run.json, logs/run.log, outputs/}` | Solo con el UUID; servir exige `resolve()` + `is_relative_to(carpeta del run)` |

Reglas al crear o mover:

1. La **carpeta de salidas pertenece al proyecto**: debe ser nueva (la crea la API con `mkdir` bajo el resolvedor y con
   timeout) o estar vacía. Así borrar o vaciar nunca toca ficheros ajenos. El nombre de la carpeta nueva se valida con
   reglas portables propias (sin `/ \ : * ? " < > |`, control, nombres reservados de Windows, punto final; ≤ 120).
2. Destino con `access = rw` y estado distinto de `unavailable`; origen `usage ∈ {source, both}`.
3. Si origen y destino comparten ubicación, ninguna subruta de origen puede contener la de salidas ni al revés (el
   escaneo leería sus propias salidas).
4. Ninguna función de dominio ni de job recibe un `str` de ruta del usuario: reciben `ResolvedPath` o rutas
   reconstruidas desde la BD y re-resueltas en el worker.

### Motor de ejecuciones (ADR-002, `app/jobs/`)

- **Cola**: reclamo atómico (único SQL crudo) `UPDATE runs SET status='running', worker_id=:w, started_at=:t,
  heartbeat_at=:t WHERE id = (SELECT id FROM runs WHERE status='queued' AND queue IN (…) ORDER BY created_at LIMIT 1)
  RETURNING id`. Bloqueo de escritura por proyecto: el índice único parcial → `409` al encolar.
- **Worker** (`python -m app.jobs.worker`): registra su fila en `workers`; bucle con `DOW_WORKER_CONCURRENCY` (1);
  lanza un subproceso `multiprocessing` *spawn* por job que recibe **solo el `run_id`**. El proceso padre **no importa
  doc_organize** (memoria): solo el subproceso, vía la capa anticorrupción.
- **Latido**: el padre actualiza `runs.heartbeat_at` y `workers.heartbeat_at` cada `DOW_WORKER_HEARTBEAT_SECONDS` (10).
  Al arrancar, los runs `running` con latido más viejo que 3× el intervalo pasan a `failed` (`orphaned`).
- **Cancelación**: `POST /runs/{id}/cancel` marca `cancel_requested`; un `queued` pasa directamente a `cancelled`. El
  subproceso lo consulta (hilo que lee la BD cada 2 s y acciona un `CancelToken`) y termina en el siguiente punto
  seguro; si no lo hace en `DOW_CANCEL_GRACE_SECONDS` (30), el padre lo termina (`terminate` → `kill`).
- **Timeout**: `DOW_JOB_TIMEOUT_SECONDS` (21 600) → se termina el subproceso, `failed` con `error_code=timeout`.
- **Eventos**: `status`, `progress` (persistido como mucho 1/s, salvo cambios de fase), `log` (avisos para el usuario,
  sin rutas del contenedor), `artifact` y `end`. Todos con `schema_version: 1`.
- **Tareas periódicas del worker** (solo un worker las hace a la vez, reclamo por marca de tiempo en BD):
  sondeo de ubicaciones cada `location_probe_interval_minutes` (pendiente de la Fase 2), capacidades al arrancar,
  cada hora y bajo petición (`refresh_requested`), y purga de workspace con `run_retention_days`.
- **Operaciones de la Fase 3** (`app/jobs/operations/`, parámetros validados con Pydantic):

| Operación | Escritura | Rol | Qué hace |
|---|---|---|---|
| `noop` | no | editor | Prueba del motor: `steps` (1–100) × `step_seconds` (0–10), emite progreso, respeta la cancelación y deja un artefacto de texto |
| `history_clear` | sí | owner | `dry_run`: cuenta ficheros y bytes en salidas y estado. Real: `ProjectHistoryCleaner.clear(project, state_root=…)` |
| `project_move` | sí | owner | `dry_run`: tamaño y comprobaciones del destino. Real: `rename` si es el mismo sistema de ficheros; si no, copia con progreso + verificación de tamaños + borrado del origen; si falla o se cancela durante la copia, borra la copia parcial y el proyecto no cambia |
| `project_delete` | sí | owner | `dry_run`: lo que se borrará. Real: con `delete_outputs` borra la carpeta de salidas y el estado; sin él, solo el estado. El proyecto pasa a `deleted` |

  **Vista previa obligatoria** (regla 7): la ejecución real exige `preview_run_id` de un `dry_run` de la misma
  operación y proyecto, `succeeded`, de menos de 15 min, sin otra escritura posterior en el proyecto, y
  `confirm_name` igual al nombre del proyecto. Ubicación destino `rw` comprobada en la API y otra vez en el worker.
  Cada borrado o movimiento se audita (`project.move`, `project.delete`, `project.history_clear`) con recuentos, no con
  la lista de ficheros (puede ser enorme); la lista va al log del run.

- **Workspace, retención y cuota**: `run.json` (operación, parámetros, estados y tiempos; sin secretos), `logs/run.log`
  (JSON, registrado como artefacto `log`), `outputs/`. Purga de las carpetas de runs terminados hace más de
  `run_retention_days` (se conservan la fila del run y sus eventos de estado). `user_quota_mb` (0 = sin límite): al
  encolar una operación que genera artefactos se compara la suma de `artifacts.size_bytes` del usuario → `409`
  `quota_exceeded`.

### Ajustes

Nuevos en `Settings` (`DOW_*`): `worker_queues` (`cpu`), `worker_concurrency` (1, 1–8), `worker_heartbeat_seconds`
(10, 2–60), `job_timeout_seconds` (21 600, 60–604 800), `cancel_grace_seconds` (30, 5–600). **Administrables**
(ADR-012, `ADMIN_KEYS` + `features.json`): `run_retention_days` (30, 1–3 650), `user_quota_mb` (0, 0–10 000 000),
`location_probe_interval_minutes` (5, 0 = desactivado, 0–1 440). `DOW_DOCUMENT_TIMEOUT_SECONDS` y
`DOW_NETWORK_RETRIES` llegan con `scan` (Fase 4).

### Contrato HTTP (`/api/v1`)

| Método | Ruta | Quién | Respuesta |
|---|---|---|---|
| GET | `/projects?limit&offset&q` | sesión | `{items, total}`: los suyos (admin: todos), con su rol y el último run |
| POST | `/projects` | sesión | 201 (creador = `owner`); 400 ruta/solape; 404 ubicación; 409 nombre o carpeta no vacía; 503 ubicación caída |
| GET | `/projects/{id}` | miembro/admin | `ProjectOut` (rutas **relativas** + nombre de ubicación; nunca `container_path`) |
| PATCH | `/projects/{id}` | owner/admin | `name`, `description`, `source_subpaths` (sin run activo) |
| GET, POST | `/projects/{id}/members` | miembro / owner | lista; alta `{user_id, role}` (409 si ya es miembro) |
| PATCH, DELETE | `/projects/{id}/members/{user_id}` | owner | cambio de rol / baja; 409 si deja el proyecto sin `owner` |
| GET | `/users/lookup?q` | sesión | ≤ 20 usuarios activos `{id, username, display_name}` por prefijo (para invitar) |
| POST | `/projects/{id}/runs` | según operación | **202** `RunOut`; cuerpo con unión discriminada por `operation`; 409 `write_locked`/`quota_exceeded`/`preview_required`; 422 parámetros |
| GET | `/runs?project_id&status&operation&limit&offset` | sesión | Historial: runs de los proyectos visibles, recientes primero |
| GET | `/runs/{id}` | miembro/admin | `RunOut` con `progress`, `result`, `error_*`, artefactos |
| POST | `/runs/{id}/cancel` | quien lo lanzó, owner o admin | 202; 409 si ya terminó |
| GET | `/runs/{id}/events` | miembro/admin | **SSE** (`text/event-stream`), reanudable con `Last-Event-ID`; cierra tras `end` |
| GET | `/runs/{id}/artifacts/{artifact_id}` | miembro/admin | Descarga (`Content-Disposition: attachment`, `Content-Type` fijo, `nosniff`); 410 si purgado |
| GET | `/admin/workers` | admin | Workers con colas, latido y capacidades |

- `/instance/capabilities` pasa a leer las capacidades publicadas por los workers (cola `cpu` y, si existe, `gpu`); se
  retira el subproceso desde la API. `POST /admin/capabilities/refresh` marca `refresh_requested`.
- `/api/health` añade `worker: none|ok|stale` (agregado; no cambia el `status`, igual que `locations`).
- SSE: eventos `id: <seq>`, `event: <type>`, `data: <json>`; comentario `: keep-alive` cada 15 s; el servidor
  revalida la sesión cada 60 s y corta si caducó; máximo 5 conexiones SSE por usuario (429). Errores RFC 9457 antes de
  abrir el flujo.
- Recurso de otro proyecto (run, artefacto, miembro) → **404** sin revelar existencia; miembro con rol insuficiente →
  403.

### Frontend

- Nav **Proyectos** y **Ejecuciones** habilitadas. `features/projects`: lista y selector (sustituye
  `project_selector.html.j2`), alta con dos `FolderBrowser` (origen multiselección; destino con «carpeta nueva»),
  **dashboard** (sustituye `dashboard.html.j2`): origen/destino, estado de las ubicaciones, últimos runs, acciones;
  miembros (buscador `/users/lookup`, roles); zona de peligro (mover, vaciar, borrar) con modal en dos pasos: lanza el
  `dry_run`, muestra el resultado y pide escribir el nombre del proyecto.
- `features/runs`: historial paginado agrupado por ejecución (filtros por estado y operación), detalle con progreso en
  vivo (`useRunEvents` con `EventSource`, reconexión con `Last-Event-ID` nativa, anuncios `aria-live="polite"`
  limitados a cambios de fase y a cada 10 %), cancelación con confirmación, artefactos y registro.
- Admin: tarjeta de workers en la página de capacidades; ajustes nuevos en `SettingsPage` (solo textos i18n).
- Estados de carga/vacío/error/sin permiso en cada vista; textos en `features.json`.

### Documentación

ADR-008 (progreso por SSE) nuevo; ADR-002 con notas de implementación; ADR-005 (estado completo en
`/data/projects/<id>`, G5 resuelto); ADR-007 (sondeo periódico, 409 al borrar). Guías de usuario «Proyectos» y
«Ejecuciones»; despliegue: el servicio `worker` pasa a arrancar por defecto (fuera del perfil) y `worker-gpu` queda
documentado para la Fase 4. PARIDAD y CHANGELOG.

### Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| K1 | Borrar o mover ficheros ajenos | Carpeta de salidas nueva o vacía al crear; borrado solo de esa carpeta y del estado por id; `dry_run` obligatorio + nombre tecleado; `rw` comprobado dos veces; auditoría |
| K2 | IDOR entre proyectos (runs, artefactos, SSE, miembros) | Toda consulta parte del proyecto visible; mismo 404; tests por endpoint |
| K3 | Contención de escritura en SQLite (worker + API + SSE) | WAL + `busy_timeout` ya activos; eventos de progreso limitados a 1/s; SSE solo lee; transacciones cortas en el worker |
| K4 | Dos escrituras simultáneas en un proyecto | Índice único parcial en BD (no un `set` en memoria) |
| K5 | Run huérfano tras caída del worker | Latido + cierre al arrancar; cancelación con *fallback* a matar el subproceso |
| K6 | Movimiento entre ubicaciones de red a medias (~1 TB) | Copia → verificación → borrado; si falla la copia, se borra la parcial y el proyecto no cambia; si falla el borrado del origen, aviso con lo que quedó |
| K7 | SSE agota hilos del servidor (uvicorn, un proceso) | Generador asíncrono con lecturas cortas en el *threadpool*; 5 conexiones por usuario; cierre al terminar el run |
| K8 | Path traversal en descargas | Ruta solo con ids + `resolve` + `is_relative_to`; `Content-Type` fijo y `attachment` |
| K9 | Fuga de rutas internas | `ProjectOut` con rutas relativas; mensajes de error sin `container_path`; `ProjectHistoryCleaner` escribe `project.json` con `root_path` absoluto en la carpeta de salidas (aceptable: el usuario ya conoce su destino; se documenta) |
| K10 | Memoria del worker | El padre no importa doc_organize; concurrencia 1; `mem_limit` del compose |

### Estrategia de pruebas

- **unit**: reclamo de la cola (dos workers no reclaman el mismo run), índice de escritura, validación del nombre de
  carpeta, solape origen/destino, máquina de estados del run, limitador de eventos, vigencia del `preview_run_id`,
  retención y cuota, nueva clave de ajustes.
- **api**: CRUD de proyectos y miembros (401/403/404/409/422, IDOR entre proyectos y entre usuarios, último owner),
  encolar (409 `write_locked`, `preview_required`), cancelar, historial, SSE (orden, `Last-Event-ID`, cierre en `end`,
  404 ajeno), descarga de artefactos (traversal, purgado → 410), `DELETE /locations` → 409, health con worker.
- **jobs** (`tests/jobs`, subproceso real con `noop`): éxito, cancelación cooperativa, *kill* tras gracia, timeout,
  huérfano al arrancar; `history_clear`/`project_move`/`project_delete` sobre carpetas temporales sintéticas
  (`ProjectHistoryCleaner` real: no carga Docling).
- **frontend**: lista y alta de proyecto, miembros, detalle de run con un `EventSource` simulado, cancelación, modal de
  confirmación en dos pasos.
- **E2E**: con `web` + `worker`: crear proyecto sobre `/mnt/e2e` (destino `rw` en `dev-data/e2e-out`), lanzar `noop`,
  ver el progreso en vivo, cancelar otro `noop`, descargar el artefacto.

## AUDIT_PLAN

- **Arquitectura** (`.ai/architecture.md`): `domain/projects` y `domain/runs` sin FastAPI; `jobs/` orquesta;
  `workspace/` construye rutas por id; doc_organize solo en `integrations/doc_organize/` y solo en el subproceso del
  job (el test de arquitectura se amplía: `app.api` y `app.jobs.worker` no deben importar la capa que carga
  doc_organize).
- **Reglas no negociables**: 3 (capa), 4 (todo en el worker; la API solo crea la carpeta de salidas y encola), 5
  (resolvedor en creación, edición y worker; SQLite en `data`), 6 (sin secretos en `params`/`run.json`), 7 (`dry_run` +
  confirmación + `rw` + rol), 8 (OpenAPI + `gen:api`).
- **ADRs**: ADR-008 nuevo; ADR-002, 005 y 007 actualizados. Sin cambios en 003/004/006/012 (solo claves nuevas).
- **Huecos de doc_organize**: ninguno nuevo. `ProjectHistoryCleaner.clear` regenera `project.json` con la ruta
  absoluta: se acepta y se documenta (no merece hueco). G2 se usa parcialmente (puente de cancelación); el rodeo de
  «matar el subproceso» queda como último recurso.
- **Paridad** (`PARIDAD.md`, Fase 3): `project_selector.html.j2`, `dashboard.html.j2`, `GET/POST /api/projects`,
  `GET/DELETE /api/projects/{name}`, `/impact` (→ `dry_run`), `/move` (→ `project_move`), `/clear-history`
  (→ `history_clear`).
- **AUDIT_CODE**: Code Auditor + Frontend Reviewer + **Security Reviewer** (mueve y borra ficheros, rutas, descargas).
- **Fuera de alcance** (no se adelanta): `scan` y la cola `gpu` operativa (F4), carpetas guardadas (F4), exportaciones
  (F5), roles personalizados y tenants (F9).

**Veredicto: `GO_CONDICIONAL`**

Condiciones (decisiones del mantenedor):

1. **Quién crea proyectos**: cualquier usuario activo (queda como `owner`), según la historia del ROADMAP. La web
   integrada lo limitaba a admin. Alternativa: solo admin.
2. **Carpeta de salidas nueva o vacía** al crear y al mover (el proyecto es dueño de su carpeta, borrar es seguro). No
   se pueden «adoptar» salidas existentes (coherente con D4: se empieza limpio).
3. **Renombrar** solo cambia el nombre en la BD (la carpeta no lleva el nombre del proyecto); no es un run.
4. **Vista previa como run `dry_run`** (no un `GET /impact` síncrono): contar ficheros en ~1 TB de red no cabe en una
   petición.
5. **El worker pasa a arrancar por defecto** en `docker-compose.yml` (sale del perfil `worker`) y publica las
   capacidades; la API deja de lanzar el subproceso de capacidades.
6. **`noop` visible en la UI** para editores (prueba del motor, sin efectos en ficheros) hasta que llegue `scan`.

## Resolución de condiciones (mantenedor, 2026-11-01)

1. Cualquier usuario activo crea proyectos (queda como `owner`): aprobado.
2. Carpeta de salidas nueva o vacía al crear y al mover: aprobado.
3. Renombrar solo en BD: aprobado.
4. Vista previa como run `dry_run`: aprobado.
5. Worker por defecto en compose y capacidades publicadas por el worker: aprobado.
6. `noop` visible en la UI para editores: aprobado.

Veredicto tras condiciones: **GO** — IMPLEMENT autorizado.
