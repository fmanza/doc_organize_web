# TRACEABILITY

## Session metadata
- id: 2026-11-01-fase4
- fecha: 2026-11-01
- rama: feature/fase-4 (desde develop b5e9d07, 0.4.0)
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
/phase — Fase: 4. Inputs completados por el mantenedor: alcance completo; mejora opcional «variante GPU»; restricciones
doc_organize 0.10.0, con GPU para probar (resultó no haber GPU NVIDIA en el equipo), la API no importa doc_organize
(G15); requisito de entrada Pillow ≥ 13 con excepción de seguridad inmediata (no esperar al 2026-11-05).

## Context supplied
- ROADMAP (Fase 4), DOC_ORGANIZE_GAPS, PARIDAD, ADRS_PROPUESTOS/MEJORAS (ADR-011), TRACEABILITY de la Fase 3
- doc_organize `v0.10.0` (clon local, solo lectura): `scan/scan_command.py` (`run_streaming`, `_run_pipeline`,
  `_delete_orphaned_outputs`, `resolve_scan_options`), `core/models.py` (`ScanOptions`, `ScanEvent`, `VersionedEvent`,
  `ScanErrorReport`, `ScanRunReport`), `core/progress.py`, `projects/layout.py`, `converter/converter.py`
  (`resolve_output_paths`, motores de OCR), `cache/cache_manager.py`, `web/routes/scan.py` (referencia)
- docling 2.142 instalado en la imagen `backend-dev`: `AppSettings` (`DOCLING_`), `download_models`, carpetas de modelos
- PyPI: fechas de publicación de Pillow y la familia docling; índices CUDA de PyTorch

## AI output summary
- PLAN + AUDIT_PLAN: `GO_CONDICIONAL` con 4 condiciones; el mantenedor las resolvió (carpetas de origen sin anidar y
  «forzar» con owner + todas + vista previa; quitar una carpeta usada con aviso; sin prueba real de GPU; modelos en
  volumen + `models-init`) → GO.
- Requisito de entrada: Pillow 13.0.0 ya entraba por fecha; se añadieron excepciones `exclude-newer-package` solo para
  docling/docling-slim 2.142.0, docling-core 2.104.0, docling-parse 7.22.4 y docling-ibm-models 4.0.4, y `pillow>=13`
  como mínimo explícito. Conversión real verificada (integración y worker sin Internet).
- IMPLEMENT backend: migración `0005_scan` (`scanned_folders`, `scan_errors`, `runs.cancel_reason`); `domain/scan`
  (carpetas guardadas, opciones contra capacidades, errores); `ScanParams` (rol, cola y vista previa por parámetros);
  capa anticorrupción `scan.py` (`run_streaming`, puente `CancelToken` comprobado en cada `ProgressEvent`, JSONL
  incremental) y `models.py` (ADR-011); operación `scan` con un ámbito por carpeta; timeout ordenado con
  `DOW_TIMEOUT_GRACE_SECONDS`; capacidades `models_ready`/`picture_description_ready`/`gpu_ready` y `scan_options`.
- Variante GPU: grupos `cpu`/`gpu` con `conflicts` en un solo `uv.lock` (torch CPU / CUDA 13.0 + EasyOCR), etapas
  `runtime-base`/`runtime-gpu`/`runtime` (la CPU, última), servicio `worker-gpu` (perfil `gpu`). Construida en el lock;
  **sin probar con GPU** (decisión del mantenedor).
- IMPLEMENT frontend: `features/scan` (pantalla de escaneo, errores paginados, hooks), «forzar» en
  `DangerousOperationModal`, resultado del escaneo en el run, capacidades de modelos; «Probar el motor» solo admin.
- AUDIT_CODE:
  - Code Auditor: APROBADO CON CONDICIONES. H1 colisión de salidas entre carpetas (G18) → **decisión del mantenedor:
    un ámbito por carpeta**; H2 vista previa de «forzar» incompleta → se niega si la caché tiene documentos de fuera de
    su carpeta, actúa carpeta a carpeta y la vista previa caduca si cambia el proyecto; M1 raíz sin resolver → se usa
    la resuelta; M2 resultado parcial → `JobCancelled`/`JobFailed` con `result`, una carpeta que falla no para las
    demás; M3 → `DOW_TIMEOUT_GRACE_SECONDS` (600 s); M4 → G19; L1 JSONL tolerante; L4 `cancel_reason` no se pisa.
    Pendientes L2/L3/L5 (no bloquean).
  - Security Reviewer: sin CRITICAL. H1 `run.log` con rutas y trazas → `app/core/redact.py` (filtro, enmascarado,
    sin trazas, 20 MB); M1 = H1 del Code Auditor; M2/M3 cubiertos arriba; M4 `models-init` sin secretos ni `data`;
    L1 enmascarado general de rutas; L2 máx. 10 000 errores por run. Pendientes L3 (tmpfs) y L4 (GET que sincroniza).
  - Frontend Reviewer: GO_CONDICIONAL. Invalidación al terminar un run (`projects`, `scan-errors`), opciones
    efectivas en los dos lanzamientos, capacidades cargando/con error, carpetas que no existen fuera del escaneo,
    `aria-label` interpolado. Pendientes LOW 7–9.
- Validación final: ruff, mypy y 304 tests del backend; integración real 3/3 (incremental, cancelación entre
  documentos, mismo nombre en dos carpetas); OpenAPI `--check`; frontend lint/typecheck/format/50 tests/build;
  `zensical build --strict`; E2E 10/10 (con escaneo real) sobre la imagen final 0.5.0, con las salidas en
  `Conversión/<carpeta>/`; worker sin Internet convirtió un PDF con OCR desde el volumen de modelos. (A mitad de la
  validación el disco C: se llenó y Docker Desktop quedó en solo lectura; tras liberar espacio se purgó la caché de
  construcción y se repitió todo.)

## Artefactos generados
- `backend/alembic/versions/0005_scan.py`, `backend/app/domain/scan/`, `backend/app/jobs/operations/scan.py`,
  `backend/app/integrations/doc_organize/{scan,models}.py`, `backend/app/core/redact.py`
- `backend/tests/api/test_scan.py`, `backend/tests/jobs/test_scan_operation.py`,
  `backend/tests/integration/test_scan_real.py`
- `frontend/src/features/scan/`, `frontend/e2e/{helpers,scan.spec}.ts`
- `docs/guides/escaneo.md`, `docs/adr/ADR-011-modelos-sin-internet.md`
- `build/logs/fase4-*.txt` (local, git-ignored)

## Directrices para Futuras IAs
- **[escaneo]**: cada carpeta de origen es un ámbito de doc_organize: estado en
  `/data/projects/<id>/folders/<sha256(subpath)[:16]>/` (`scan.folder_state`) y salidas en `Conversión/<subpath>/`
  (`ScanRequest.output_subdir`). Nunca pases varias carpetas en una llamada: doc_organize omite el nombre de la raíz al
  derivar la salida (G18). Las Fases 5–7 deben agregar las cachés de todas las carpetas del proyecto.
- **[escaneo]**: con `force`, doc_organize vacía la caché y borra la salida de todo lo cacheado que no ve, y trata un
  listado fallido como carpeta vacía (G19): cualquier llamada con `force` va precedida de `_check_force` (carpetas
  legibles, caché sin documentos de fuera).
- **[escaneo]**: las carpetas guardadas son `projects.source_subpaths` (sin anidar, `422 nested_folders`) y su estado
  en `scanned_folders`; tras cambiar `source_subpaths` llama a `projects.sync_scanned_folders`.
- **[jobs]**: `JobCancelled(result)` y `JobFailed(..., result=)` guardan el resultado parcial; el timeout pide parada
  ordenada (`queue.request_stop`, `cancel_reason`) y espera `timeout_grace_seconds` antes de terminar el subproceso.
- **[seguridad]**: todo texto de librerías que llegue al usuario (mensajes de error, avisos, `run.log`) pasa por
  `app.core.redact.PathRedactor`; usa raíces **resueltas** (`resolve_in(location, "", ctx).absolute`).
- **[modelos]**: el worker corre con `HF_HUB_OFFLINE=1`; los modelos los descarga `models-init` a `/models/docling` con
  `manifest.json`; `DOCLING_ARTIFACTS_PATH` se fija en el subproceso solo si existe el manifiesto. Al actualizar Docling,
  repetir `models-init`.
- **[gpu]**: todo lo que escriba la variante GPU va al tmpfs `/tmp` (`EASYOCR_MODULE_PATH`,
  `PYTORCH_KERNEL_CACHE_PATH`, creada en `entrypoint.sh`); al subir torch/EasyOCR/Docling, repetir la prueba con GPU
  real y buscar `Read-only file system` y `could not be created` en los logs de `worker-gpu`.
- **[dependencias]**: torch va en los grupos `cpu` (por defecto, `default-groups`) y `gpu`, incompatibles; `uv sync
  --frozen` instala CPU; la imagen GPU usa `--no-group cpu --group gpu`. `docker compose build` sin `target` construye
  la última etapa (`runtime`, CPU).
- **[doc_organize]**: `SUPPORTED_EXTENSIONS` no incluye `.md`; para E2E e integración sin modelos usa `.html`/`.txt`.
- **[compose]**: `!reset` no quita claves heredadas por `<<: *app`; un servicio que no debe recibir secretos se define
  sin el ancla. No construyas varios servicios con la misma imagen a la vez (BuildKit en Docker Desktop se cae): usa
  `docker compose build web`.
- **[tests]**: las operaciones del worker corren en subprocesos *spawn* (`monkeypatch` no llega): las operaciones se
  prueban en el propio proceso con un `JobContext` real (`tests/jobs/test_scan_operation.py`) y el motor con `noop`.

## Prueba con GPU real (posterior al cierre, mismo día)
Equipo con RTX 5070 Laptop (Blackwell, compute capability 12.0, 8 GB), driver 616.92 (CUDA 13.4), Docker Desktop
29.6.1 con runtime `nvidia`. Stack 0.5.0 con `--profile gpu`, ubicaciones sintéticas (5 PDF de 3 páginas solo imagen
+ 1 HTML) y escaneos por la API con «usar GPU» (cola `gpu`) y sin ella (cola `cpu`).
- torch 2.14.1+cu130 incluye `sm_120`; `detect_gpu_status` → `gpu_active=True`; el worker publica `gpu_ready` y la
  instancia `scan_options.use_gpu=true`; Docling usa `cuda:0` (maquetación, tablas y EasyOCR).
- **Fallo 1 (L6 confirmado)**: EasyOCR crea siempre `~/.EasyOCR/user_network`; con `/app` de solo lectura los 5 PDF
  fallaban en el OCR (`Errno 30`) y el run terminaba `succeeded` con 5 errores → `ENV EASYOCR_MODULE_PATH=/tmp/easyocr`
  en `runtime-gpu` (los modelos siguen viniendo de `DOCLING_ARTIFACTS_PATH/EasyOcr`, descarga desactivada).
- **Fallo 2**: torch no podía crear su caché de kernels CUDA (`~/.cache/torch/kernels`) y los recompilaba en cada job
  → `PYTORCH_KERNEL_CACHE_PATH=/tmp/torch-kernels`; torch no crea esa carpeta (un solo `mkdir`, ni siquiera bajo
  `XDG_CACHE_HOME`): la crea `docker/entrypoint.sh`.
- **Fallo 3**: `models-init --easyocr` no funcionaba (imagen CPU sin `easyocr`) → servicio `models-init-gpu` (perfil
  `setup-gpu`, imagen `runtime-gpu`). Las guías pasaban `python -m …` como comando de `models-init`, que ya es su
  entrypoint (`invalid choice: 'python'`) → solo argumentos.
- **Mejora**: `download` reescribía el manifiesto solo con lo pedido (`models-init` borraba EasyOCR del manifiesto de
  `models-init-gpu`) → `merge_folders` conserva los grupos opcionales que siguen en disco
  (`tests/unit/test_models_manifest.py`); verificado con `models-init` sin opciones tras `models-init-gpu`.
- Suite del backend en `backend-dev` (Linux): 308 tests; en Windows fallan 5 tests de rutas ya existentes, ajenos a
  este cambio (el CI y la imagen son Linux).
- Resultado final: 2 escaneos GPU seguidos 6/6 con OCR, 0 errores, ≈ 45 s; el mismo escaneo en CPU (RapidOCR) ≈ 94 s;
  0 avisos de escritura; texto reconocido correcto. `zensical build --strict` sin avisos. Logs en
  `build/logs/gpu-*.txt`.

## Pendientes (no bloquean)
- LOW sin aplicar: `GET scanned-folders` sincroniza en un GET (L4 seguridad / L2 código), carrera TOCTOU al cambiar
  carpetas con un run encolándose, `folders.json` por carpeta (L5), tmpfs `/tmp` sin límite (L3 seguridad), mejoras
  de accesibilidad LOW 7–9 del Frontend Reviewer.
- Pedir a doc_organize L-10 (caché incremental, G16), L-10b (carpeta de modelos, G17), L-10c (nombre de la raíz en la
  salida, G18), L-10d (listado fallido y errores al cancelar, G19).

## Veredicto final
GO — Fase 4 cerrada en 0.5.0. Prueba con GPU real hecha después: tres correcciones en `[Unreleased]` (Fixed).
