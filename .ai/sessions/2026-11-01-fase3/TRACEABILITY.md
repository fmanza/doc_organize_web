# TRACEABILITY

## Session metadata
- id: 2026-11-01-fase3
- fecha: 2026-11-01
- rama: feature/fase-3 (desde chore/skills, que migra los prompts a `.github/skills/`; PR pendiente de push)
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
/phase — Fase: 3. Alcance: completa. Mejoras opcionales: no. Restricciones: doc_organize 0.10.0 ya fijado (wheel de la
release); sin GPU en desarrollo; no importar doc_organize en el proceso de la API (G15).

## Context supplied
- ROADMAP (Fase 3), ARQUITECTURA_PROPUESTA, DOC_ORGANIZE_GAPS, ADR-001…007 y 012, TRACEABILITY de la Fase 2
- doc_organize `v0.10.0` (clon local, solo lectura): `__init__` (`_EXPORTS`), `projects/layout.py`,
  `projects/project_history_cleaner.py`, `projects/project_registry.py`, `core/progress.py`, `web/routes/projects.py`
- `.github/skills/phase-implementation`, agentes Plan Architect, Code Auditor, Frontend Reviewer y Security Reviewer

## AI output summary
- PLAN + AUDIT_PLAN: `GO_CONDICIONAL` con 6 condiciones; el mantenedor aprobó todas → GO.
- IMPLEMENT backend: migración `0004`; `domain/projects` (alta con carpeta propia, acceso por miembros, solapes);
  `domain/runs` (catálogo de operaciones con unión discriminada, encolar con vista previa, eventos, workers);
  `jobs/` (cola, worker, subproceso *spawn*, contexto con cancelación y fase crítica, operaciones `noop`,
  `history_clear`, `project_move`, `project_delete`); `workspace/runs.py`; capa anticorrupción
  (`clear_project_history`, capacidades desde el worker); routers `projects`, `runs` (SSE), `users/lookup`,
  `admin/workers`; health con `worker`.
- IMPLEMENT frontend: `features/projects` (lista, alta, dashboard, miembros, `DangerousOperationModal`) y
  `features/runs` (historial, detalle con `EventSource`, cancelación); tarjeta de workers; textos en `features.json`.
- AUDIT_CODE (dos revisores independientes: seguridad, y código + frontend). Corregido en la sesión:
  - carpeta de salidas sustituida por un enlace → el worker la rechaza (`folder_replaced`) antes de mover o borrar;
  - borrado con `shutil.rmtree` por entrada (descriptores, sin seguir enlaces en carreras);
  - fase crítica (`runs.uninterruptible`): una cancelación no mata el subproceso mientras borra o mueve;
    `project_delete` marca el proyecto borrado antes de borrar ficheros; `project_move` cambia la BD antes de borrar
    el origen, reserva el destino con `mkdir` y copia ante `EXDEV`;
  - vista previa invalidada por cualquier escritura activa o terminada después de empezar;
  - huérfanos: al arrancar se cierran los runs del mismo `hostname:pid` y cada minuto los de latido caducado;
  - `finish` confirma estado + `status` + `end` en una transacción; `run.log` se registra también si el worker
    cierra el run; fallo al lanzar el subproceso → `failed`;
  - SSE: libera la sesión de BD antes de abrir el flujo, revalida sesión **y** acceso al run cada minuto y solo envía
    el último `progress` de cada lote;
  - tope de 5 runs activos por usuario; `/users/lookup` exige 2 caracteres;
  - frontend: estado del SSE reiniciado al cambiar de run, flujo abierto también en runs terminados (avisos), progreso
    indeterminado con `Loader`, región `aria-live` siempre montada en el modal, carga de las últimas ejecuciones.
- Validación: backend (ruff, format, mypy, pytest 278 + 1 omitido en Windows), OpenAPI `--check`; frontend (format,
  lint, typecheck, Vitest 42, build); `zensical build --strict`; `docker compose build` + `up` con E2E: `/api/health`
  200 con `worker: ok`, capacidades publicadas por el worker, `clear_project_history` real en el contenedor sin cargar
  Docling, E2E 9/9 (`--workers=1`: en paralelo en este Windows, el login Argon2 compite con la carga de torch del
  sondeo de capacidades).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-11-01-fase3/PLAN.md` | emitido (GO tras condiciones) |
| IMPLEMENT | `backend/app/{domain/projects,domain/runs,jobs,workspace/runs.py,api/v1/projects.py,api/v1/runs.py}`, `backend/alembic/versions/0004_projects_runs.py`, `frontend/src/features/{projects,runs}` | completado |
| Tests | `backend/tests/{api/test_projects.py,api/test_runs.py,jobs/test_worker.py,unit/test_projects_runs_domain.py}`, `frontend/src/features/{projects,runs}/*.test.tsx`, `frontend/e2e/projects.spec.ts` | nuevos |
| Docs | ADR-008, notas en ADR-002/005/007, `guides/{proyectos,ejecuciones}.md`, despliegue, ubicaciones | nuevos/actualizados |

## Directrices para Futuras IAs
- **[jobs]**: una operación nueva es un módulo en `app/jobs/operations/` + su modelo de parámetros y `OperationSpec`
  en `app/domain/runs/operations.py` (unión discriminada `RunParams`) + entrada en `REGISTRY`. Si escribe en las
  salidas o en el estado del proyecto (escanear, exportar, deduplicar), `is_write` debe devolver `True` para ella:
  el bloqueo de una escritura por proyecto es el índice `uq_runs_project_write`.
- **[jobs]**: el proceso padre del worker no importa doc_organize (`test_api_and_worker_parent_do_not_load_doc_organize`);
  la capa anticorrupción importa la librería **dentro** de las funciones, que solo llama el subproceso del job.
- **[jobs]**: todo tramo que borre o mueva ficheros va dentro de `with ctx.uninterruptible():` (el worker no lo mata por
  una cancelación; el timeout sí aplica). Las cancelaciones se atienden con `ctx.check_cancelled()` entre elementos.
- **[jobs]**: cerrar un run es `queue.finish` (estado + `status` + `end` en una transacción, condicional a `running`);
  nunca se escribe `runs.status` final por otro camino.
- **[rutas]**: el worker vuelve a resolver las carpetas del proyecto con `_files.project_paths`, que exige que la
  ruta resuelta coincida con la guardada: así un enlace puesto por fuera de la app no redirige un borrado.
- **[destructivas]**: mover, vaciar o borrar exigen `preview_run_id` de un `dry_run` de la misma operación y
  parámetros (`_PREVIEW_KEYS`), de < 15 min, sin escrituras activas ni posteriores, y `confirm_name`; lo valida
  `domain/runs/service._check_preview`.
- **[sse]**: los eventos viven en `run_events`; el flujo los lee con sesiones cortas (nunca con la `DbSession` de la
  petición, que se cierra antes de abrir el flujo) y solo reenvía el último `progress` de cada lote.
- **[tests]**: `admin_client` y `user_client` comparten el mismo `TestClient`: el último login gana. Para dos sesiones a
  la vez, `tests.conftest.login_as`.
- **[tests-frontend]**: los `Select`/`Autocomplete` de Mantine tienen rol `combobox` y sus opciones viven en un portal
  con transición: buscarlas dentro del `listbox` de `aria-controls` con `hidden: true` (helper `choose` en
  `projects.test.tsx`). `Textarea autosize` rompe en jsdom (`document.fonts`): usar `rows`.
- **[cliente-api]**: `openapi-typescript` 7 hace obligatorios los campos con valor por defecto: al lanzar runs se
  envían completos (`NOOP_RUN`); con `exactOptionalPropertyTypes`, los filtros opcionales se omiten en lugar de pasar
  `undefined`.
- **[e2e]**: los nombres de ubicaciones de `projects.spec.ts` no empiezan por «E2E» (`locations.spec.ts` borra las
  suyas por ese prefijo y una ubicación con proyectos da 409); esperar a la cabecera «Última comprobación» antes de
  contar filas (la tabla de salud de Inicio también es una `table`).
- **[shell]**: los heredocs largos con comillas fallan a veces en el Bash de este Windows; para ediciones múltiples,
  escribir el script en el scratchpad y ejecutarlo.

## Pendientes (no bloquean)
- Carrera improbable entre dos altas simultáneas que eligen carpetas anidadas (comprobación fuera de transacción).
- Un `kill` por timeout durante la copia de `project_move` deja la copia parcial en el destino (el proyecto no cambia;
  el reintento falla con `target_exists` hasta borrarla).
- Pillow ≥ 13 antes de la Fase 4 (requisito de entrada del ROADMAP).

## Veredicto final
Veredicto: CLOSED (pendiente de push de `chore/skills` y `feature/fase-3`, PRs y release 0.4.0 si el mantenedor lo pide)
