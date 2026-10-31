---
applyTo: "backend/**/*.py"
---
# Backend (FastAPI + SQLAlchemy) — reglas

> **TL;DR** — Python 3.12, `mypy --strict`, ruff. Routers finos → servicios de dominio → integraciones. Pydantic en
> todo lo que cruza HTTP. doc_organize solo desde `app/integrations/doc_organize/`. Operaciones pesadas como jobs.
> Rutas del sistema de ficheros solo con el resolvedor de ubicaciones (`filesystem.instructions.md`).

## Capas y dependencias
- `api/` (routers) → `domain/` (servicios, reglas) → `db/` (modelos, sesión) e `integrations/` (doc_organize).
- `domain/` no importa FastAPI. `integrations/doc_organize/` no importa `api/` ni `domain/`.
- Dependencias con `Depends` (sesión de BD, usuario actual, ajustes); nada de singletons globales mutables ni estado
  compartido en `app.state` para coordinar trabajos (el bloqueo «una escritura por proyecto» vive en la BD).

## Routers
- Prefijo `/api/v1/<recurso-plural>`; `response_model` siempre; `summary` en español.
- Errores con `HTTPException` o excepciones de dominio mapeadas a *problem details* (`app/core/errors.py`).
- Endpoints que tardan más de ~1 s, leen documentos en masa o tocan ficheros del origen/destino → encolan un job y
  devuelven `202` con el recurso `run`.

## Persistencia
- SQLAlchemy 2 estilo 2.0 (`select()`, `Mapped[...]`), modelos en `app/db/`.
- Tipos portables (`JSON`, `DateTime(timezone=True)`, `Uuid`); nada de SQL crudo salvo el reclamo de la cola
  (`UPDATE … RETURNING`); PRAGMA solo en el *listener* de conexión (ruta de escape a otra BD, D8).
- Toda alteración de esquema con revisión Alembic (`render_as_batch` para SQLite); `downgrade` implementado.
- Transacciones cortas: SQLite admite un único escritor (WAL + `busy_timeout`).
- `cache.db` de cada proyecto es de doc_organize: la web lo lee **solo** a través de la capa anticorrupción y
  paginado; nunca lo migra ni escribe directamente.

## doc_organize
- Firma verificada antes de usarla (wheel o clon local de solo lectura). Adaptadores que devuelven tipos propios
  (dataclasses/Pydantic), no objetos de doc_organize.
- Llamadas siempre por nombre de argumento (G13: `ScanCommand.run_streaming` tiene muchos posicionales).
- Rutas de estado (`cache.db`, historial, errores) siempre explícitas y en el volumen `data` (G5).
- Versión de la librería con `importlib.metadata.version("doc_organize")`, no `__version__` (G1).
- Cada rodeo temporal de un hueco lleva un comentario con su `G<n>` de `docs/plan/DOC_ORGANIZE_GAPS.md`.

## Estilo
- f-strings; `logging` con `extra={...}` (nunca `print`); `pathlib.Path`; docstrings Google en español.
- Excepciones específicas; `except Exception` solo en bordes (handler global, job runner) y con log.
