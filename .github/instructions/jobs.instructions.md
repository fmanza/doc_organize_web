---
applyTo: "backend/app/jobs/**,backend/app/domain/runs/**"
---
# Ejecuciones (jobs) — reglas

> **TL;DR** — Cola propia sobre la tabla `runs` (colas `cpu`/`gpu`), un subproceso *spawn* por job, latido,
> cancelación cooperativa con *fallback* a matar el subproceso, progreso persistido y servido por SSE (ADR-002,
> ADR-008).

## Cola
- Estados: `queued → running → succeeded | failed | cancelled`; `queue` ∈ {`cpu`, `gpu`}; el worker atiende las colas
  de `DOW_WORKER_QUEUES` con `DOW_WORKER_CONCURRENCY` (1 por defecto: Docling consume mucha memoria).
- Reclamo atómico con `UPDATE … RETURNING` (único SQL crudo permitido).
- **Una operación de escritura por proyecto a la vez** (bloqueo en BD; `409` al encolar otra).
- La opción GPU enruta a `gpu`; si no hay worker GPU vivo, la API no la ofrece (capacidades de la instancia).

## Ejecución
- El worker lanza un subproceso *spawn* que recibe **solo el `run_id`** y carga parámetros de la BD (nunca secretos
  por argumentos ni variables de entorno visibles en `ps`).
- Latido (`heartbeat_at`) periódico; huérfanos (latido caducado) → `failed` al arrancar el worker.
- Timeouts: `DOW_JOB_TIMEOUT_SECONDS` por job y `DOW_DOCUMENT_TIMEOUT_SECONDS` por documento.
- Cancelar = `cancel_requested`; el job la comprueba entre documentos (`cancel_token` de doc_organize cuando exista,
  G2) y el worker termina el subproceso si no responde en un plazo.
- El run sobrevive al cierre de la pestaña o a la caída de la conexión SSE.

## Progreso y resultados
- Eventos de progreso con contador, total (si se conoce), fase y documento actual; persistidos para reanudar el SSE
  con `Last-Event-ID`. Los eventos de doc_organize se traducen en la capa anticorrupción (G7: sin versión de esquema).
- Carpeta por ejecución en el workspace: `run.json` (sin secretos), `logs/run.log`, `outputs/`; artefactos registrados
  en `artifacts` al finalizar.
- Errores por documento acumulados y paginables; el resumen va a `runs`.

## Operaciones
- Cada operación (`scan`, `dedup_preview`, `dedup_apply`, `context_build`, `context_delete`, `taxonomy_draft`,
  `export_zip`, `export_xlsx`, `history_clear`, `noop`) es un módulo en `app/jobs/operations/` que valida sus
  parámetros con Pydantic y llama a doc_organize solo a través de la capa anticorrupción.
- Operaciones que mueven o borran ficheros: exigen un artefacto de vista previa vigente y confirmado
  (`filesystem.instructions.md`).
