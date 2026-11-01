# ADR-002 — Ejecución de jobs: cola propia, colas cpu/gpu y un subproceso por job

- **Estado**: Aceptado (esqueleto del worker en la Fase 0; cola y operaciones implementadas en la Fase 3, 0.4.0)
- **Fecha**: 2026-10-31

## Contexto

Escanear y convertir con Docling y OCR, deduplicar, construir el contexto o clasificar con IA puede durar horas sobre
~100 000 documentos (D10) y consume mucha memoria por documento (R3). La web integrada lo hace dentro del proceso web
y cancela el escaneo si se cierra el WebSocket. doc_organize 0.9.x no ofrece progreso con total ni cancelación
cooperativa (G2). No se quiere añadir Redis.

## Decisión

1. Las operaciones de doc_organize se ejecutan como **jobs** en un proceso **worker** separado de la API (misma
   imagen, otro comando: `python -m app.jobs.worker`). La API solo encola (`202` con el recurso `run`) y consulta.
2. **Cola propia** sobre la tabla `runs` de `config.db` (como la opción b de util_bbdd_web): reclamo atómico con
   `UPDATE … RETURNING` (SQLite ≥ 3.35, también PostgreSQL), único SQL crudo permitido.
3. **Colas `cpu` y `gpu`**: cada worker atiende las de `DOW_WORKER_QUEUES`; el servicio `worker-gpu` (perfil `gpu`,
   imagen `runtime-gpu`) atiende `gpu`. La opción GPU de un escaneo enruta a `gpu`.
4. **Un subproceso *spawn* por job**, que recibe solo el `run_id`: aísla memoria y estado, y cancelar es, como
   último recurso, terminar el subproceso.
5. **Concurrencia 1 por defecto** (`DOW_WORKER_CONCURRENCY`) por la memoria de Docling; límite de memoria del
   contenedor en compose.
6. **Una operación de escritura por proyecto a la vez** (bloqueo en BD; `409` al encolar otra). Sustituye al `set` en
   `app.state` de la web integrada (su ADR-004 queda obsoleto aquí).
7. Latido, timeouts por job (`DOW_JOB_TIMEOUT_SECONDS`) y por documento (`DOW_DOCUMENT_TIMEOUT_SECONDS`), huérfanos
   cerrados al arrancar; progreso persistido y servido por SSE ([ADR-008](ADR-008-progreso-sse.md)).

## Consecuencias

- Coste de arranque de un proceso por job (despreciable frente a la duración de un escaneo).
- Hasta que doc_organize ofrezca `on_progress` y `cancel_token` (L-2), el progreso se cuenta por eventos del
  generador y cancelar termina el subproceso (rodeo de G2).

## Fase 0

`app/jobs/worker.py` solo arranca, registra los volúmenes y termina limpio con `SIGTERM`; compose lo define en el
perfil `worker`.

## Notas de implementación (Fase 3, 0.4.0)

- **Tablas** (`0004_projects_runs`): `runs` (estado, cola, `is_write`, `params`, `progress`, `result`, error con
  código y mensaje para el usuario, `cancel_requested`, latido, `worker_id`), `run_events` (fuente del SSE, ADR-008),
  `artifacts`, `workers` y `periodic_tasks`.
- **Una escritura por proyecto**: índice único parcial `uq_runs_project_write (project_id) WHERE is_write AND status IN
  ('queued','running')`, válido en SQLite y PostgreSQL; al chocar, `409 write_locked`. Las vistas previas (`dry_run`) y
  `noop` no escriben.
- **Reclamo** en `app/jobs/queue.py` (`UPDATE … RETURNING`, único SQL crudo). Cancelar un run en cola es otro `UPDATE`
  condicional (`WHERE status = 'queued'`): si el worker lo reclama a la vez, gana el reclamo y se pide la cancelación al
  run en marcha.
- **Worker** (`app/jobs/worker.py`): el proceso padre **no importa doc_organize** (lo comprueba un test); el subproceso
  (`app/jobs/runner.py`) carga el run, escribe `run.json` y `logs/run.log`, ejecuta la operación y cierra el run. Si
  el subproceso muere sin cerrarlo, el padre lo marca `failed`/`crashed`; por timeout, `timeout`; si ignora la
  cancelación más de `DOW_CANCEL_GRACE_SECONDS`, se termina y queda `cancelled`/`cancel_forced`. Al recibir `SIGTERM`
  termina sus subprocesos y deja los runs `failed`/`interrupted`.
- **Huérfanos**: al arrancar, los runs `running` con latido más viejo que 3× `DOW_WORKER_HEARTBEAT_SECONDS` pasan a
  `failed`/`orphaned`.
- **Cancelación cooperativa**: un hilo del subproceso consulta `cancel_requested` cada 2 s y activa el contexto del
  job; las operaciones paran entre elementos. En la Fase 4 ese contexto alimenta el `CancelToken` de doc_organize (G2).
- **Tareas periódicas** (un hilo del worker; con varios workers, la tabla `periodic_tasks` hace que solo uno las
  ejecute en cada intervalo): sondeo de ubicaciones, purga del workspace por retención y capacidades del contenedor.
- **Operaciones de la Fase 3**: `noop` (prueba del motor), `history_clear`, `project_move` y `project_delete`, estas
  tres con vista previa obligatoria (regla 7).
