# ADR-002 — Ejecución de jobs: cola propia, colas cpu/gpu y un subproceso por job

- **Estado**: Aceptado (esqueleto del worker en la Fase 0; cola y operaciones en la Fase 3)
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
   cerrados al arrancar; progreso persistido y servido por SSE (ADR-008, Fase 3).

## Consecuencias

- Coste de arranque de un proceso por job (despreciable frente a la duración de un escaneo).
- Hasta que doc_organize ofrezca `on_progress` y `cancel_token` (L-2), el progreso se cuenta por eventos del
  generador y cancelar termina el subproceso (rodeo de G2).

## Fase 0

`app/jobs/worker.py` solo arranca, registra los volúmenes y termina limpio con `SIGTERM`; compose lo define en el
perfil `worker`.
