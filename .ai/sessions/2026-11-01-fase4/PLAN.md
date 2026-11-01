# Fase 4 — Escaneo y conversión (0.5.0)

## PLAN

### Historias y DoD

| Id | Historia | Hecho cuando |
|---|---|---|
| WB-4.1 | Operación `scan` con progreso, cancelación y opciones validadas contra las capacidades; `use_gpu` va a la cola `gpu` | Un run `scan` convierte el origen al destino del proyecto, es incremental, se cancela entre documentos conservando lo convertido y rechaza opciones que la instancia no soporta |
| WB-4.2 | Carpetas guardadas en BD (sustituye a `ScannedFoldersStore`) | `GET/POST/DELETE /projects/{id}/scanned-folders`; marca `used` y último escaneo por carpeta |
| WB-4.3 | Historial y errores de escaneo | Cada run `scan` guarda su resumen (`ScanRunReport`) en `runs.result` y sus errores (`ScanErrorReport`) en la tabla `scan_errors`; endpoints paginados |
| WF-4.1 | Pantalla de escaneo y de errores | Elegir carpetas, opciones con ayuda contextual, progreso por fase y documento, página de errores paginada |
| Mejora | Variante GPU | `uv` resuelve torch CPU y CUDA en el mismo lock; imagen `runtime-gpu`; servicio `worker-gpu` (perfil `gpu`) |
| Entrada | Pillow ≥ 13 (seguridad) | Lock con Pillow 13.0.0 y docling sin `pillow<13`; suite e integración en verde |

DoD común del ROADMAP: tests (unit/api/jobs + integración marcada), OpenAPI y `gen:api`, docs de usuario, CHANGELOG,
PARIDAD, GAPS, sin secretos ni rutas del contenedor en respuestas.

### Requisito de entrada: Pillow 13 (excepción de seguridad)

Pillow 13.0.0 (2026-10-16) ya cae dentro de `exclude-newer = 2026-10-17`; lo bloquean los docling fijados, que exigen
`pillow<13`. Excepciones por paquete (comentario con motivo y fecha, se retiran al adelantar `exclude-newer`):

| Paquete | Versión | Publicada | Corte propuesto |
|---|---|---|---|
| docling, docling-slim | 2.142.0 | 2026-10-22 14:31 | `2026-10-22T15:00:00Z` (excluye 2.142.1) |
| docling-core | 2.104.0 | 2026-10-22 14:02 | `2026-10-22T15:00:00Z` |
| docling-parse | 7.22.4 | 2026-10-21 11:59 | `2026-10-21T12:30:00Z` |
| docling-ibm-models | 4.0.4 | 2026-10-21 11:34 | `2026-10-21T12:00:00Z` |

`uv lock` puede pedir alguna dependencia transitiva nueva: si aparece, se añade con su motivo o se para y se pregunta.
Verificación: suite completa + tests de integración con conversión real (PDF e imagen sintéticos generados con Pillow).

### doc_organize: versión y firmas verificadas (0.10.0, clon `../doc_organize` en v0.10.0+3 de CI)

- `ScanCommand().run_streaming(paths: list[str], output_dir: Path, cache_db: Path, folders_json: Path, *, options:
  ScanOptions | None, on_progress: ProgressCallback | None, cancel_token: CancelToken | None, error_log_path=,
  history_log_path=) -> AsyncIterator[ScanEvent]` — `options` excluye los indicadores sueltos (`TypeError`).
- `ScanOptions(use_ocr=True, use_gpu=False, force=False, include_audio_video=False, extract_images=False,
  use_picture_description=False)` (frozen, `extra="forbid"`).
- `ScanEvent(VersionedEvent)`: `event: ScanEventType` (`started`, `scanned`, `file_started`, `file_converted`,
  `ocr_started`, `ocr_file_started`, `ocr_processed`, `completed`, `cancelled`), `data: dict`, `schema_version=1`,
  `to_dict()` (G7).
- `ProgressEvent(operation, phase, processed, total, current)`; `CancelToken.cancel()` (thread-safe); parada entre
  documentos; `CANCELLED` como último evento y `save_entries` de lo ya convertido (G2).
- `ProjectLayout(output_root, state_root=)`: `conversion_dir`, `cache_db`, `folders_json`, `scan_errors_log`,
  `scan_history_log` (estado en `/data/projects/<id>/`, G5).
- `ScanErrorReport(scan_run_id, timestamp, total_scanned, entries: list[ScanErrorEntry(file_path, error_message,
  error_retry_count, capped)])`; `ScanRunReport(scan_run_id, started_at, finished_at, duration_seconds, total_scanned,
  completed, discovery_duration_seconds, total_conversion_seconds)`. JSONL append-only.
- `use_gpu` solo cambia el motor de OCR a EasyOCR con GPU (`EasyOcrOptions(use_gpu=True)`); necesita el extra
  `ocr-gpu` (torch, torchvision, opencv-python, easyocr). El modelo de *layout* usa CUDA si hay GPU.
- Comportamientos que condicionan el diseño (leídos en el código):
  1. Las carpetas pasadas son a la vez **qué se escanea y las raíces** de las que se deriva la ruta de cada salida
     (`resolve_output_paths`, raíz más profunda): escanear subcarpetas arbitrarias cambiaría dónde cae una salida.
  2. `force=True` **vacía toda la caché** y **borra las salidas** de lo cacheado que no aparece en este escaneo: con
     un subconjunto de carpetas borraría las salidas de las demás.
  3. Sin `force`, lo no visto se ignora (`get_changes` solo mira lo descubierto): escanear un subconjunto es seguro.
  4. La caché solo se guarda al final o al cancelar: una excepción o un `kill` pierde la caché de todo el run (las
     salidas quedan escritas, pero el siguiente run lo reconvierte). → hueco nuevo **G16**.
  5. Los eventos y errores llevan **rutas absolutas del contenedor**.
- `PENDIENTE DE VERIFICAR` (en IMPLEMENT, contra docling 2.142 instalado): variable o API para la carpeta de modelos
  (`DOCLING_ARTIFACTS_PATH`/`artifacts_path`, `download_models`), modelos de RapidOCR y de EasyOCR sin Internet;
  versión de torch CUDA disponible en el índice de PyTorch antes del corte.

### Carpetas guardadas (WB-4.2) y rutas

- Las carpetas guardadas **son las carpetas de origen del proyecto** (`projects.source_subpaths`): un escaneo elige un
  subconjunto de ellas (por defecto, todas). No se escanean subcarpetas sueltas (punto 1).
- Tabla `scanned_folders` con el estado de cada una (`used`, `last_scanned_at`, `last_run_id`, `added_by`); `used` es
  permanente (paridad).
- Añadir carpeta: rol `owner`, sin un run de escritura en marcha, resuelta por el resolvedor en la ubicación de origen,
  **rechazando el anidamiento** con otra carpeta del proyecto (`422 nested_folders`) en vez de quedarse con la de fuera
  como hacía la Fase 3 (si no, las salidas existentes cambiarían de ruta). La edición del proyecto aplica la misma
  regla.
- Quitar carpeta: `owner`; no borra ficheros (sus salidas siguen en el destino). Condición 2 sobre las `used`.
- El worker vuelve a resolver cada carpeta (autorización y existencia) y pasa rutas absolutas a doc_organize; las
  convierte a **relativas a la ubicación** en eventos, errores y resultados (`«Origen»/sub/doc.pdf`), y quita del
  texto de los errores el prefijo del contenedor.

### Modelo de datos — Alembic `0005_scan`

- `scanned_folders` (`project_id` FK cascade, `subpath`, `used`, `added_by`, `added_at`, `last_scanned_at`,
  `last_run_id`), PK (`project_id`, `subpath`); la migración crea una fila por cada `source_subpaths` existente.
- `scan_errors` (`id`, `run_id` FK cascade, `project_id` FK cascade, `path` relativo, `message` (≤ 2 000, saneado),
  `retry_count`, `capped`), índice (`project_id`, `run_id`). La purga por retención de runs los arrastra.
- `runs.result` del `scan`: recuentos del `ScanSummary` (`scanned`, `new`, `modified`, `unchanged`, `converted`,
  `errors`, `error_retries`, `error_retries_capped`…), duraciones de `ScanRunReport`, `warnings`,
  `event_schema_version`.

### Operación `scan` (WB-4.1, `app/jobs/operations/scan.py`)

- `ScanParams`: `folders: list[str]` (vacío = todas; ⊆ carpetas guardadas), las seis opciones de `ScanOptions`, y,
  con `force=True`, el patrón de la Fase 3 (`dry_run`, `preview_run_id`, `confirm_name`).
- Rol `editor`; `force` exige `owner`, **todas** las carpetas (punto 2) y vista previa + confirmación (regla 7: borra
  salidas). La vista previa de `force` cuenta entradas de la caché, cuántas ya no existen en el origen (salidas que se
  borrarían, con `stat`, sin hashear 1 TB) y el tamaño de las salidas actuales.
- `is_write` = siempre (un escaneo escribe en el destino): no coincide con mover, vaciar ni borrar el proyecto.
- Cola: `gpu` si `use_gpu`, si no `cpu`.
- Validación en la API contra las capacidades publicadas por los workers vivos de esa cola (`422 option_unavailable`
  con la opción): `use_gpu` → algún worker `gpu` con `gpu_active`; `include_audio_video` → `av_ready`;
  `use_picture_description` → modelo de visión disponible (capacidad nueva `models`). El worker lo vuelve a comprobar.
- Capa anticorrupción `integrations/doc_organize/scan.py`: construye `ProjectLayout`, `ScanOptions` y `CancelToken`,
  ejecuta `run_streaming` en un bucle asyncio propio del subproceso y traduce `ProgressEvent` → `ctx.progress`
  (`discovery`, `conversion`, `ocr`, `done`, `current` relativo) y los avisos (`warnings`, reintentos agotados) →
  `ctx.log`. Un hilo une `ctx` y el `CancelToken`.
- **Mitigación de G16**: sin `force`, un `run_streaming` **por carpeta** (misma derivación de rutas, porque las
  carpetas no se anidan): un corte de red solo pierde la caché de la carpeta en curso. Con `force`, una sola llamada.
- **Timeout cooperativo**: al vencer `job_timeout_seconds` el worker pide la parada (como al cancelar) y espera
  `cancel_grace_seconds` antes de terminar el subproceso; el run acaba `failed/timeout` pero la caché de lo convertido
  se guarda.
- Tras cada llamada se leen las líneas **nuevas** de `scan_errors_log` y `scan_history_log` (posición del fichero al
  empezar) y se guardan en `scan_errors` y en `result`; se marcan las carpetas como `used`. El log del run es artefacto
  como en la Fase 3.

### Variante GPU (mejora opcional)

- `pyproject.toml`: torch y torchvision salen de las dependencias base a dos extras incompatibles (`cpu`, `gpu`) con
  `[tool.uv] conflicts`; `gpu` añade `doc_organize[ocr-gpu]` y toma torch del índice CUDA de PyTorch (`cu128`,
  `PENDIENTE DE VERIFICAR` la versión anterior al corte). Un solo `uv.lock`.
- `docker/Dockerfile`: argumento `TORCH_VARIANT` y objetivo `runtime-gpu` (mismo Python; el driver lo aporta
  `nvidia-container-runtime`). CI construye solo la CPU (la GPU pesa varios GB); la GPU se construye con
  `workflow_dispatch`.
- `docker-compose.yml`: servicio `worker-gpu` en el perfil `gpu`, `DOW_WORKER_QUEUES=gpu`, `deploy.resources.
  reservations.devices` (nvidia), `DOW_WORKER_CONCURRENCY=1`.

### Modelos sin Internet (ADR-011, previsto para esta fase)

- Volumen `models` (`/models`): `HF_HOME` y la carpeta de artefactos de Docling apuntan ahí; el worker corre con
  `HF_HUB_OFFLINE=1`.
- `python -m app.integrations.doc_organize.models download [--picture-description] [--easyocr]` lo llena (servicio
  `models-init` en compose, perfil `setup`); la capacidad `models` dice qué hay.
- Si faltan modelos, un PDF falla con un error claro (`models_missing`) en vez de quedarse descargando.

### Contrato HTTP (`/api/v1`)

| Método y ruta | Rol | Respuesta / errores |
|---|---|---|
| `GET /projects/{id}/scanned-folders` | reader | lista con `used`, `last_scanned_at`, `last_run_id`, `available` |
| `POST /projects/{id}/scanned-folders` `{subpath}` | owner | 201; 409 `write_in_progress`, 422 `nested_folders`, 404 `folder_not_found` |
| `DELETE /projects/{id}/scanned-folders/{subpath:path}` | owner | 204; 409 `last_folder` / `write_in_progress` (+ condición 2) |
| `POST /projects/{id}/runs` `{operation:"scan", …}` | editor (`force`: owner) | 202; 422 `option_unavailable`, `folder_not_saved`, `force_requires_all_folders`; 409 `write_in_progress` |
| `GET /runs/{id}/scan-errors?limit&offset` | reader | página de errores del run |
| `GET /projects/{id}/scan-errors?limit&offset` | reader | errores del último escaneo terminado del proyecto |
| `GET /runs?project_id&operation=scan` | reader | historial (ya existe) |
| `GET /admin/workers`, `/instance` | — | capacidades con `models` |

SSE (ADR-008, sin tipos nuevos): `progress` con `phase` ∈ {`discovery`, `conversion`, `ocr`, `done`}, `log` para
avisos, `status`/`end`. Los eventos por documento no se guardan uno a uno (100 000 documentos): solo el progreso
limitado a 1/s.

### Frontend (`features/scan/`)

- `ScanPage` (`/projects/:id/scan`, sustituye `folder_selector.html.j2` y `_example_modal_macros`): carpetas con casilla,
  `used` y último escaneo; añadir con el explorador de la ubicación de origen; opciones con ayuda contextual (popover
  con ejemplos) y desactivadas con motivo según capacidades; «Forzar reconversión» en zona de peligro
  (`DangerousOperationModal`); lanzar → detalle del run.
- `RunDetailPage`: resultado del `scan` (recuentos, duraciones, avisos), fase y documento actuales, enlace a errores.
- `ScanErrorsPage` (`/runs/:id/errors` y `/projects/:id/scan-errors`, sustituye `scan_errors.html.j2`): tabla paginada en
  servidor.
- Detalle del proyecto: acción «Escanear» (editor) e historial filtrado por `scan`. «Probar el motor» pasa a admin.
- i18n `es`, estados de carga/vacío/error/sin permiso, WCAG 2.2 AA.

### Documentación

Guía `docs/guides/escaneo.md` (opciones, incremental, forzar, errores, GPU); `despliegue.md` (perfil `gpu`, modelos,
memoria); ADR-011 (modelos sin Internet) y nota en ADR-002 (timeout cooperativo, cola `gpu`); `proyectos.md`
(carpetas sin anidar).

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Ficheros de usuario maliciosos (JPEG/TIFF/PDF) | Pillow 13 (entrada); subproceso por job; contenedor no root |
| `force` borra salidas | owner + todas las carpetas + vista previa + confirmación + auditoría |
| Pérdida de caché por corte o timeout (G16) | Un `run_streaming` por carpeta; timeout cooperativo; hueco a doc_organize |
| Memoria de Docling (2–4 GB por job) | `DOW_WORKER_CONCURRENCY=1` por defecto; documentado |
| Rutas del contenedor en errores | Conversión a relativas y saneado del mensaje; test |
| Descarga de modelos en producción | ADR-011: offline + `models-init` |
| Imagen GPU (varios GB) | Fuera del CI por defecto |
| SQLite: escrituras de progreso | Progreso ≤ 1/s; errores en bloque al final de cada carpeta |
| Red SMB/NFS lenta | Descubrimiento y hash en el worker; el resolvedor con timeout ya existe |

### Estrategia de pruebas

- **unit**: conversión de rutas absolutas → relativas y saneado de mensajes; lectura incremental de JSONL; validación
  de opciones contra capacidades; regla de anidamiento.
- **api**: carpetas guardadas (roles, anidamiento, `used`), lanzar `scan` (opciones, `force`, colas, 422/409), errores
  paginados, sin rutas del contenedor.
- **jobs** (doc_organize sustituido en la capa): escaneo incremental (sin cambios = 0 conversiones), cancelación a
  mitad (se guarda lo convertido), **documento que supera el timeout** (parada cooperativa y caché guardada), error
  por documento → `scan_errors`, una llamada por carpeta.
- **integration** (`@pytest.mark.integration`, Docker): conversión real de un PDF y un PNG sintéticos con Pillow 13,
  incremental real, cancelación real; GPU en la máquina con GPU.
- **frontend**: ScanPage (selección, opciones desactivadas, forzar), errores paginados, resultado del run.
- **E2E**: escanear un proyecto con `.md`/`.html` sintéticos (no necesitan modelos), ver progreso y resultado,
  segundo escaneo con 0 conversiones.

## AUDIT_PLAN

- **Arquitectura**: `domain/scan` (carpetas, errores, validación) sin FastAPI; la operación en `jobs/operations/scan.py`;
  doc_organize solo en `integrations/doc_organize/{scan,models}.py`, cargado solo en el subproceso del job (el test de
  arquitectura ya lo cubre). La API sigue sin importar doc_organize (G15).
- **Reglas no negociables**: 1 (sin cambios en doc_organize: G16 va a GAPS), 3, 4 (escaneo en el worker), 5 (carpetas
  por el resolvedor; caché en `data`), 6 (sin secretos), 7 (`force`), 8 (OpenAPI + `gen:api`).
- **ADRs**: ADR-011 nuevo; notas en ADR-002 (timeout cooperativo, `gpu`) y ADR-006 (extras `cpu`/`gpu`).
- **Huecos de doc_organize nuevos**: **G16** — la caché solo se guarda al terminar o cancelar (un fallo a mitad pierde
  la caché del run); petición L-10: guardar cada N documentos. **G17** — sin forma de indicar la carpeta de modelos ni
  modo sin Internet en `DocumentConverter` (si se confirma en IMPLEMENT). G11 sigue (sin timeout por documento).
- **Paridad** (`PARIDAD.md`): `folder_selector.html.j2` + `_example_modal_macros`, `scan_errors.html.j2`,
  WebSocket `/scan` (→ run `scan` + SSE), `/folders/library` (→ `scanned-folders`), `/folders/validate` (→ resolvedor).
- **AUDIT_CODE**: Code Auditor + Frontend Reviewer + **Security Reviewer** (rutas, `force` borra, ficheros de usuario,
  imagen GPU).
- **Fuera de alcance**: deduplicación (F6), exportar errores a Excel (F5), visor de resultados y caché (F5), variante
  `WITH_AV`/LibreOffice (la opción de audio/vídeo se valida con la capacidad; la imagen no la trae).

**Veredicto: `GO_CONDICIONAL`**

Condiciones (decisiones del mantenedor):

1. **Carpetas y `force`**: el escaneo elige entre las carpetas de origen del proyecto (nunca subcarpetas sueltas), sin
   anidamiento; `force` exige `owner`, todas las carpetas, vista previa y confirmación.
2. **Quitar una carpeta `used`**: permitido o prohibido (paridad).
3. **Prueba de la GPU**: este equipo no tiene GPU NVIDIA.
4. **Modelos sin Internet** (ADR-011): volumen + `models-init` o dentro de la imagen.

## Resolución de condiciones (mantenedor, 2026-11-01)

1. Carpetas de origen sin anidar y `force` con owner + todas las carpetas + vista previa + confirmación: aprobado.
2. Quitar una carpeta `used`: permitido al `owner`, con aviso de que sus salidas siguen en el destino (cambia la
   paridad: la web integrada lo impedía).
3. GPU: sin prueba real en esta fase; la variante queda construida y documentada, y la prueba con GPU pendiente
   (anotada en TRACEABILITY).
4. Modelos: volumen `/models` + servicio `models-init`; el worker sin Internet.

Veredicto tras condiciones: **GO** — pendiente de la autorización explícita de IMPLEMENT.

## AUDIT_CODE: resolución (mantenedor, 2026-11-01)

- Colisión de salidas entre carpetas (G18, Code Auditor H1 / Security M1): **un ámbito por carpeta** (caché propia y
  salidas en `Conversión/<carpeta>/`). «Forzar» pasa a actuar carpeta a carpeta.
- El resto de hallazgos HIGH/MEDIUM se corrigieron sin cambiar el contrato (ver TRACEABILITY). `DELETE
  scanned-folders` usa `?subpath=` (no `{subpath:path}`) para admitir la raíz `""`.
