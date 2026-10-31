---
applyTo: "backend/app/api/**/*.py,frontend/src/api/**,openapi/**"
---
# Contrato HTTP — reglas

- Versión en la ruta: `/api/v1`. Cambios incompatibles → `/api/v2` o deprecación documentada.
- `openapi/openapi.json` es el contrato: tras tocar routers o esquemas, `uv run python scripts/export_openapi.py`
  (desde `backend/`) y `npm run gen:api` (desde `frontend/`) en el mismo cambio. El CI lo comprueba con `--check`.
- Errores: `application/problem+json` (RFC 9457) con `title`, `status`, `detail` opcional y campos extra tipados
  (p. ej. `errors` de validación). Nunca texto de excepciones de doc_organize, Docling ni del sistema de ficheros
  (sin rutas del contenedor en el mensaje).
- Códigos: `200/201/204` éxito; `202` job encolado (cuerpo: el `run`); `400` regla de negocio; `401` sin sesión;
  `403` sin permiso; `404` no existe **o no es visible para el usuario** (no filtrar existencia, tampoco de carpetas);
  `409` conflicto (p. ej. ya hay una escritura en curso en el proyecto); `422` validación; `429` límite;
  `503` ubicación `unavailable`.
- Colecciones: `{"items": [...], "total": n}` con `limit` (máx. 500) y `offset`.
- Progreso: SSE en `GET /api/v1/runs/{id}/events` (`text/event-stream`, `id` por evento, reanudación con
  `Last-Event-ID`); el esquema de los eventos se documenta en OpenAPI aunque no lo genere FastAPI.
- Rutas en la API: siempre `location_id` + ruta relativa a la ubicación; nunca rutas absolutas del contenedor ni
  `display_path` como entrada.
- Fechas en ISO 8601 UTC; identificadores de ejecución ULID.
- Campos secretos (claves IA, PAT) solo de escritura: nunca aparecen en respuestas (solo «configurado» + últimos 4).
