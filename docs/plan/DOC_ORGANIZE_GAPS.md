# Huecos de la API de doc_organize

Mismo contrato que `UTIL_BBDD_GAPS.md`: **no se parchea doc_organize desde la web**; cada hueco tiene un rodeo en
`backend/app/integrations/doc_organize/` hasta que la librería lo resuelva (tareas `L-*` de `TAREAS_DOC_ORGANIZE.md`).

Versión analizada: **doc_organize 0.9.0** (rama `develop`, commit `1e40c8c`, 2026-10-31). Versión consumida desde la
Fase 0: **0.9.3**; desde 2026-10-31 (antes de la Fase 3): **0.10.0** (ver «Resueltos»).

| # | Hueco | Impacto en la web | Rodeo hasta resolverlo | Petición | Tarea |
|---|---|---|---|---|---|
| G8 | Exportaciones (ZIP, Excel de caché y de errores) dentro de `web/routes/downloads.py` | Se perderían al retirar `web/` | Copiar la lógica a la web (duplicación temporal) | Módulo `doc_organize.export` | L-7 |
| G10 | `MkDocsGenerator` depende de mkdocs (sin soporte futuro), lanza `mkdocs build` si está instalado y devuelve `site_built=False` si no | Resultado silencioso según la imagen; dependencia obsoleta en la imagen | Hasta 0.11.0: instalar `mkdocs` en la imagen y comprobar `site_built` (temporal) | `SiteGenerator` con Zensical + parámetro `build` + error tipado (el extra `site` con mkdocs ya existe en 0.10.0) | L-8 |
| G11 | Sin reintentos ante errores de E/S transitorios ni timeout por documento | Escaneos largos en red fallan enteros por un corte | Reintentar el run entero (incremental gracias a la caché) | Reintentos y timeout configurables | L-9 |
| G12 | Detectores (`GpuStatus`, `AvStatus`, `OfficeStatus`) sin punto de entrada público | La ficha de capacidades duplicaría la detección | Importar los módulos internos desde la capa anticorrupción | `doc_organize.diagnostics` | L-9b |

## Resueltos

| # | Resuelto en | Cómo | Rodeo retirado |
|---|---|---|---|
| G1 | doc_organize 0.10.0 (2026-10-31) | API pública en `__init__` (`_EXPORTS`, PEP 562) con `ScanCommand`, `ScanOptions`, `ContextBuilder`, `ProjectLayout`, eventos y modelos; `py.typed`; `__version__` = versión del paquete desde 0.9.3 (L-1) | Ninguno: la web sigue leyendo `importlib.metadata` |
| G2 | doc_organize 0.10.0 (2026-10-31) | `CancelToken`, `ProgressEvent` (`on_progress`), evento `CANCELLED` y `OperationCancelledError`; al cancelar conserva en caché lo ya convertido (L-2) | Contar eventos y matar el subproceso: se retira en la Fase 4 (matar queda como último recurso del timeout) |
| G3 | doc_organize 0.10.0 (2026-10-31) | Protocol `SecretValueReader`; los clientes de IA ya no importan `auth`; `*_from_store_or_env` obsoletas (L-3) | Se aplica en la Fase 8 construyendo los `*Config` en la web |
| G4 | doc_organize 0.10.0 (2026-10-31) | `ProjectLayout` público; `tenant_id` obsoleto con `DeprecationWarning` (L-4, L-6c) | La web no usa `ProjectRegistry` y deriva las rutas con `ProjectLayout` desde la Fase 3 |
| G5 | doc_organize 0.10.0 (2026-10-31) | `ProjectLayout(output_root, state_root=)`: caché, logs, carpetas e informes de deduplicación en `state_root`; `report_dir=` en la deduplicación (L-5) | Estado en `/data/projects/<id>/` desde la Fase 3; nunca SQLite en una ubicación de red |
| G6 | doc_organize 0.10.0 (2026-10-31) | `group_id` estable y `DedupMode` (`move` por defecto, `copy`, `report_only`) en `resolve_duplicates`/`deduplicate_streaming`, aplicando solo los grupos confirmados (L-6) | Se aplica en la Fase 6 |
| G7 | doc_organize 0.10.0 (2026-10-31) | `VersionedEvent` con `schema_version` (`EVENT_SCHEMA_VERSION = 1`) y `to_dict()`, con test de contrato en doc_organize (L-6b) | Se aplica en la Fase 4 (SSE e historial guardan `schema_version`) |
| G13 | doc_organize 0.10.0 (2026-10-31) | `ScanOptions` y `options=` en `ScanCommand.run`/`run_streaming` | Se aplica en la Fase 4 |
| G15 | doc_organize 0.10.0 (2026-10-31) | `import doc_organize` no carga Docling (de ~49 s y ~4 300 módulos a ~0,5 s y ~300) | Las capacidades siguen en subproceso por G12 y porque el detector de GPU importa torch |
| G9 | doc_organize 0.9.3 (2026-10-31) | Wheel y sdist en GitHub Releases; la web lo fija por URL y hash en `uv.lock` (ADR-006) | No hizo falta vendorizar |
| G14 | doc_organize 0.9.3 (2026-10-31) | Versión 0.9.3 en `pyproject.toml`, `__version__` y tag `v0.9.3` | — |
