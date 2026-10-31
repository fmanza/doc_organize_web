# Arquitectura (contexto para IAs)

Fuente detallada: `docs/plan/ARQUITECTURA_PROPUESTA.md` y `docs/adr/` (propuestos en `docs/plan/ADRS_PROPUESTOS.md`).
Resumen operativo:

## Niveles y dependencias permitidas

| Nivel | Paquete | Puede importar |
|---|---|---|
| 1 | `backend/app/core` | stdlib, pydantic-settings, Starlette/FastAPI (errores, middleware), prometheus-client |
| 1 | `backend/app/db` | core, SQLAlchemy, Alembic |
| 2 | `backend/app/integrations/doc_organize` | core, **doc_organize** (único) |
| 2 | `backend/app/workspace` | core |
| 3 | `backend/app/domain` | core, db, integrations, workspace (sin FastAPI) |
| 4 | `backend/app/jobs` | core, db, domain, integrations, workspace |
| 4 | `backend/app/api` | core, db, domain (y `integrations` solo para lecturas triviales como la versión) |
| 5 | `backend/app/main.py` | api, core |

Subpaquetes de `domain/`: `identity` (F1, tenants y roles en F9), `locations` (F2), `settings` (F2, IA en F8),
`projects` (F3/F4), `runs` (F3), `cache` (F5), `duplicates` (F6), `context` (F7), `ai` (F8).

## Zonas de datos (ADR-005)

| Zona | Dónde | Qué |
|---|---|---|
| Estado | volumen local `data` (`DOW_DATA_DIR`) | `config.db` (app) y `projects/<id>/cache.db` (doc_organize); SQLite **nunca** en red |
| Artefactos | volumen `workspace` (`DOW_WORKSPACE_DIR`) | carpeta por ejecución: `run.json`, `logs/run.log`, `outputs/` |
| Salidas | ubicación destino `rw` (local o red) | Markdown, JSON, imágenes, duplicados, sitio de contexto |
| Origen | ubicación origen (`ro` o `rw`) | documentos a procesar; solo lectura salvo duplicados en `rw` con confirmación |

## Patrones con nombre

- **Capa anticorrupción (ACL)**: `integrations/doc_organize` traduce objetos y eventos de doc_organize a tipos propios.
- **Resolvedor de ubicaciones**: único punto que convierte `location_id` + ruta relativa en una ruta del contenedor.
- **Contrato primero**: OpenAPI exportado → cliente TypeScript generado.
- **Job en subproceso**: el worker lanza un proceso hijo *spawn* por ejecución (cancelable, aislado, memoria acotada).
- **Run manifest**: `run.json` en la carpeta de cada ejecución + filas en `runs`/`artifacts`.

## Flujo de una ejecución (Fase 3)

`POST /api/v1/projects/{id}/runs` (202) → fila `runs(queued, queue=cpu|gpu)` → el worker de esa cola la reclama
(`UPDATE … RETURNING`) → subproceso *spawn* con solo el `run_id` → operación (`app/jobs/operations`) → doc_organize vía
ACL con rutas ya resueltas → salidas en destino, `cache.db` en `data`, artefactos en `workspace` → `finalize_run`
registra `artifacts` → `runs(succeeded|failed|cancelled)`. Progreso persistido y servido por SSE
(`/runs/{id}/events`, `Last-Event-ID`). Cancelar = `cancel_requested` → el job para entre documentos o el worker
termina el subproceso.
