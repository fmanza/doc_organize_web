# ADR-008 — Progreso por SSE en lugar de WebSocket

- **Estado**: Aceptado (implementado en la Fase 3, 0.4.0)
- **Fecha**: 2026-11-01

## Contexto

La web integrada de doc_organize sigue el escaneo, la deduplicación y la construcción y borrado del contexto con cuatro
WebSockets (su ADR-001). El WebSocket **es** la operación: si se cierra la pestaña o se corta la red, el escaneo se
cancela. Con ejecuciones de horas sobre ~100 000 documentos (D10) y un worker separado de la API (ADR-002), el
progreso tiene que sobrevivir a la conexión del navegador. Además, la API usa cookie de sesión y CSRF (ADR-003) y va
detrás de un proxy TLS.

## Decisión

1. Toda operación es un **run** en cola; el progreso se lee con **Server-Sent Events** en
   `GET /api/v1/runs/{id}/events`. El run no depende de que alguien lo mire.
2. **Eventos persistidos** en `run_events` (`run_id`, `seq`, `type`, `data`). `seq` es el `id` del evento SSE: el
   navegador reconecta solo y envía `Last-Event-ID`, y el servidor sigue desde ahí (también `?after=`). La API no
   guarda estado del flujo: lee la tabla cada segundo (SQLite WAL, solo lectura).
3. Tipos: `status`, `progress` (fase, procesados, total, elemento actual), `log` (avisos para el usuario), `artifact`
   y `end`, todos con `schema_version` (1). El servidor cierra el flujo tras `end`.
4. El subproceso del job publica el progreso **como mucho una vez por segundo** (salvo cambios de fase o al terminar)
   para no inundar `config.db` en escaneos de miles de documentos.
5. **Mismo origen y cookie**: `EventSource` envía la cookie de sesión; es un `GET`, así que no lleva CSRF. La sesión se
   revalida cada minuto y el flujo se corta si caducó. Comentario `: keep-alive` cada 15 s para proxies; cabeceras
   `Cache-Control: no-store` y `X-Accel-Buffering: no`.
6. Autorización igual que `GET /runs/{id}`: un run de un proyecto que el usuario no ve da 404 antes de abrir el flujo.
   Como mucho **5 flujos abiertos por usuario** (429).
7. El cliente también consulta `GET /runs/{id}` cada pocos segundos mientras el run está activo: si el SSE se cae
   (proxy que corta, navegador sin `EventSource`), el estado sigue llegando.

## Consecuencias

- Cerrar la pestaña no cancela nada; cancelar es una acción explícita (`POST /runs/{id}/cancel`).
- La tabla `run_events` crece con cada run: la purga por retención borra los `progress` y `log` de los runs antiguos
  y conserva los de estado.
- Cada flujo abierto ocupa una lectura por segundo en `config.db`; con decenas de usuarios es despreciable frente a
  la escritura de los jobs. Con muchos más, se sustituiría la lectura periódica por una notificación (p. ej.
  `LISTEN/NOTIFY` si se migra a PostgreSQL, D8).
- Sustituye al ADR-001 de doc_organize (WebSocket) en la web nueva; la web integrada no cambia (congelada).

## Alternativas descartadas

- **WebSocket**: exige otro mecanismo de autenticación y CSRF, configuración extra en proxies y no se reanuda solo.
- **Solo *polling***: más simple, pero con retraso y más carga para el mismo resultado; queda como respaldo.
