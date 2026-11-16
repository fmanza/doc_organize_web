# TRACEABILITY

## Session metadata
- id: 2026-11-16-doc-organize-1.5.0
- fecha: 2026-11-16
- rama: `chore/doc-organize-1.5.0` (A), `feat/file-metadata` (B), `feat/context-traceability` (C),
  `feat/ai-enrichment` (D), `feat/context-history` (E); release 1.5.0 desde `develop`
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (A–E) + VERSION (1.4.8 y 1.5.0)

## Prompt issued
«plan y audit_plan para actualizar doc_organize_web con lo incluido en la versión 1.5.0» y, después, «implement,
pregunta lo que necesites y dame recomendaciones».

## Context supplied
- CHANGELOG y API pública de doc_organize 1.5.0 (release del 2026-11-16).
- `.ai/sessions/2026-11-16-doc-organize-1.5.0/PLAN.md` (plan y AUDIT_PLAN, veredicto GO_CONDICIONAL).
- Decisiones del usuario:
  - propietario de los ficheros «fijo por proyecto», solo para owner/admin;
  - presupuesto de IA «uno por familia»;
  - el historial «se conserva» al borrar el contexto;
  - versiones «1.4.8 y luego 1.5.0»;
  - entrega «PR y fusión por fase»;
  - rendimiento en red: «medición local + aviso».

## AI output summary
- **Fase A** (PR #57, web 1.4.8 publicada):
  - Pin `doc_organize==1.5.0` con el hash del wheel; añade `py3langid` 0.4.0.
  - Tests de caché 1.4 en solo lectura, `historial_contexto` reservado y `context.json` dañado.
  - Medición local: lectura de propiedades, mediana 0,34 ms por PDF y 0,14 ms por DOCX.
  - Release: fast-forward de `main`, tag `v1.4.8` y notas del CHANGELOG.
- **Fase B** (PR #58):
  - `DocumentOut` con tipo MIME, fecha de creación y permisos.
  - `projects.capture_owner` (migración 0012): solo lo cambia el owner, queda auditado y el run lo copia al encolar.
  - Fuera del esquema de entrada (`SkipJsonSchema`).
  - `owner_name` solo para el rol owner.
- **Fase C** (PR #59):
  - Migración 0013 con las propiedades y la trazabilidad de cada documento, más la versión y los modelos del contexto.
  - Filtros `language`, `keyword` (sobre el JSON, con el término escapado como se guarda) y `only=ai_disagrees`.
  - Página del contexto con propiedades y el detalle «Cómo se clasificó».
- **Fase D** (PR #60):
  - Familia `litellm_enrichment`, con `ai_enrichment` en `ContextBuildParams`.
  - Los dos clientes se abren con `AsyncExitStack`.
  - Progreso separado por `event.phase` (etapa `context_enrichment`) y `ai_enrichment` en el resultado del run.
  - Tarjeta en Configuración IA y casilla al construir.
- **Fase E** (PR #61):
  - `GET /projects/{id}/context/history` con tope de 16 MB, como mucho 200 cambios por construcción y rutas
    relativas.
  - `export_xlsx` con `kind=context_history`.
  - Bloque «Historial» y botón de exportación.
- Verificación de cada fase:
  - backend: ruff, mypy, pytest (de 528 a 563 passed en Windows) y `export_openapi.py --check`;
  - frontend: prettier, eslint, tsc, vitest (de 116 a 122) y build;
  - docs: `zensical build --strict`;
  - CI en verde antes de cada squash merge a `develop`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-11-16-doc-organize-1.5.0/PLAN.md` | emitido |
| Migraciones | `backend/alembic/versions/0012_project_capture_owner.py`, `0013_context_metadata.py` | completado |
| Integración | `backend/app/integrations/doc_organize/{scan,cache,context,ai,export}.py` | completado |
| API | `backend/app/api/v1/{documents,projects,context}.py`, `schemas.py` | completado |
| Frontend | `features/{documents,projects,context,runs,admin}` | completado |
| Guías | `docs/guides/{usuarios_y_sesiones,contexto,ia,documentos}.md` | completado |

## Directrices para Futuras IAs
- **[tests en Windows]**: las aserciones sobre rutas relativas al origen (`DocumentNamer`) van con
  `@pytest.mark.posix_paths`. En Windows, `folder_roots` no casa con rutas del contenedor; en CI (Linux) sí corren.
- **[búsquedas en JSON]**: SQLite guarda las columnas `JSON` con `json.dumps` (con escapes `\uXXXX`). Para buscar dentro
  hay que escapar el término igual (ver `_keywords_contain`). Ignorar mayúsculas solo funciona en ASCII, como el resto
  de búsquedas sobre SQLite.
- **[cliente TS]**: un `bool` con valor por defecto en un modelo de entrada sale como obligatorio en el cliente
  generado. Si lo rellena el servidor, `SkipJsonSchema` lo saca del esquema.
- **[IA]**: `ai_max_failures` y `ai_max_documents` son argumentos comunes de `ContextBuilder.build`, pero cada fase
  (clasificación y enriquecimiento) cuenta su propio presupuesto.
- **[historial]**: «Vaciar histórico» (`ProjectHistoryCleaner`) vacía la carpeta del proyecto, historial del contexto
  incluido. Borrar el contexto no lo toca.
- **[Python en Windows]**: `Path.write_text` escribe CRLF. Ruff y Prettier lo normalizan; con otros ficheros, usar
  `newline="\n"`.

## Veredicto final
Veredicto: CLOSED

Pendientes al cierre:
- Medir la lectura de propiedades sobre una ubicación de red real (SMB/NFS).
- Propuestas para doc_organize: metadatos de los documentos sin clasificar (`Context.unclassified_documents` solo
  guarda rutas), y filtro y orden por las columnas nuevas de la caché en `load_cache_page`.
