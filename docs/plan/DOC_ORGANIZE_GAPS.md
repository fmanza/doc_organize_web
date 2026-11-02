# Huecos de la API de doc_organize

Mismo contrato que `UTIL_BBDD_GAPS.md`: **no se parchea doc_organize desde la web**; cada hueco tiene un rodeo en
`backend/app/integrations/doc_organize/` hasta que la librería lo resuelva (tareas `L-*` de `TAREAS_DOC_ORGANIZE.md`).

Versión analizada: **doc_organize 0.9.0** (rama `develop`, commit `1e40c8c`, 2026-10-31). Versión consumida desde la
Fase 0: **0.9.3**; desde 2026-10-31 (antes de la Fase 3): **0.10.0** (ver «Resueltos»). Desde la Fase 5: **0.11.0**; desde el 2026-11-02
(antes de la Fase 6): **0.12.0**, que resuelve G16–G23.

| # | Hueco | Impacto en la web | Rodeo hasta resolverlo | Petición | Tarea |
|---|---|---|---|---|---|
| G10 | `MkDocsGenerator` depende de mkdocs (sin soporte futuro), lanza `mkdocs build` si está instalado y devuelve `site_built=False` si no | Resultado silencioso según la imagen; dependencia obsoleta en la imagen | Hasta 0.11.0: instalar `mkdocs` en la imagen y comprobar `site_built` (temporal) | `SiteGenerator` con Zensical + parámetro `build` + error tipado (el extra `site` con mkdocs ya existe en 0.10.0) | L-8 |
| G11 | Sin reintentos ante errores de E/S transitorios ni timeout por documento | Escaneos largos en red fallan enteros por un corte | Reintentar el run entero (incremental gracias a la caché); desde la Fase 4, una llamada por carpeta y timeout del job con parada ordenada | Reintentos y timeout configurables | L-9 |
| G12 | Detectores (`GpuStatus`, `AvStatus`, `OfficeStatus`) sin punto de entrada público | La ficha de capacidades duplicaría la detección | Importar los módulos internos desde la capa anticorrupción | `doc_organize.diagnostics` | L-9b |

## Resueltos

| # | Resuelto en | Cómo | Rodeo retirado |
|---|---|---|---|
| G1 | doc_organize 0.10.0 (2026-10-31) | API pública en `__init__` (`_EXPORTS`, PEP 562) con `ScanCommand`, `ScanOptions`, `ContextBuilder`, `ProjectLayout`, eventos y modelos; `py.typed`; `__version__` = versión del paquete desde 0.9.3 (L-1) | Ninguno: la web sigue leyendo `importlib.metadata` |
| G2 | doc_organize 0.10.0 (2026-10-31) | `CancelToken`, `ProgressEvent` (`on_progress`), evento `CANCELLED` y `OperationCancelledError`; al cancelar conserva en caché lo ya convertido (L-2) | Aplicado en la Fase 4: el escaneo une la cancelación del job (y el timeout ordenado) con el `CancelToken`, que se comprueba en cada `ProgressEvent`; lo convertido queda en caché |
| G3 | doc_organize 0.10.0 (2026-10-31) | Protocol `SecretValueReader`; los clientes de IA ya no importan `auth`; `*_from_store_or_env` obsoletas (L-3) | Se aplica en la Fase 8 construyendo los `*Config` en la web |
| G4 | doc_organize 0.10.0 (2026-10-31) | `ProjectLayout` público; `tenant_id` obsoleto con `DeprecationWarning` (L-4, L-6c) | Aplicado en la Fase 3: la web no usa `ProjectRegistry` (proyectos en `config.db`; mover y borrar son operaciones propias sobre la carpeta del proyecto) y construye `Project` sin `tenant_id` |
| G5 | doc_organize 0.10.0 (2026-10-31) | `ProjectLayout(output_root, state_root=)`: caché, logs, carpetas e informes de deduplicación en `state_root`; `report_dir=` en la deduplicación (L-5) | Aplicado en la Fase 3: estado en `/data/projects/<id>/` (`ProjectHistoryCleaner.clear(…, state_root=)`); nunca SQLite en una ubicación de red |
| G6 | doc_organize 0.10.0 (2026-10-31) | `group_id` estable y `DedupMode` (`move` por defecto, `copy`, `report_only`) en `resolve_duplicates`/`deduplicate_streaming`, aplicando solo los grupos confirmados (L-6) | Se aplica en la Fase 6 |
| G7 | doc_organize 0.10.0 (2026-10-31) | `VersionedEvent` con `schema_version` (`EVENT_SCHEMA_VERSION = 1`) y `to_dict()`, con test de contrato en doc_organize (L-6b) | Aplicado en la Fase 4: `runs.result.event_schema_version` del `scan` |
| G13 | doc_organize 0.10.0 (2026-10-31) | `ScanOptions` y `options=` en `ScanCommand.run`/`run_streaming` | Aplicado en la Fase 4 (`integrations/doc_organize/scan.py`) |
| G15 | doc_organize 0.10.0 (2026-10-31) | `import doc_organize` no carga Docling (de ~49 s y ~4 300 módulos a ~0,5 s y ~300) | Las capacidades siguen en subproceso por G12 y porque el detector de GPU importa torch |
| G16 | doc_organize 0.12.0 (2026-11-02) | `ScanOptions.cache_save_every` (20) y `cache_save_seconds` (30): la caché se guarda durante la conversión y también ante una excepción o cancelación (L-10a) | Automático (guardado cada 20 documentos o 30 s); se mantienen la llamada por carpeta (G18) y la parada ordenada del timeout, que ya no son imprescindibles |
| G17 | doc_organize 0.12.0 (2026-11-02) | `ScanOptions.artifacts_path` y `allow_model_downloads=False` (`ModelsNotAvailableError` si falta un modelo) (L-10b) | Aplicado: `ScanOptions.artifacts_path` = `/models/docling` y `allow_model_downloads=False` cuando hay manifiesto (`ModelsNotAvailableError` → mensaje «repite models-init»); se retira `DOCLING_ARTIFACTS_PATH`. Sin modelos sigue `HF_HUB_OFFLINE=1` |
| G18 | doc_organize 0.12.0 (2026-11-02) | `ScanOptions.root_name_in_output` antepone el nombre de la carpeta escaneada a la salida; sin ella, `SCANNED` avisa de colisiones (L-10c) | No se retira: se mantiene un ámbito por carpeta (caché y estado separados, Fase 4) |
| G19 | doc_organize 0.12.0 (2026-11-02) | `ScanResult.unreadable_dirs` y avisos en `SCANNED`; con `force` no se tratan como huérfanos los documentos de carpetas ilegibles; `ScanErrorReport` también al cancelar (L-10d) | Lo protege la librería; `_check_force` (carpetas legibles y caché sin documentos de fuera) se mantiene como comprobación previa, y los errores de una carpeta cancelada ya llegan en el JSONL |
| G20 | doc_organize 0.12.0 (2026-11-02) | `resolve_output_paths`, `resolve_images_dir` y `relative_source_path` en `doc_organize.projects.layout`, sin Docling (L-10e) | Aplicado: `domain/documents/outputs.py` delega en `resolve_output_paths`/`resolve_images_dir` de la librería (capa anticorrupción, sin Docling); se retira el test de contrato de integración |
| G21 | doc_organize 0.12.0 (2026-11-02) | `CacheManager(db_path, read_only=True)`: `mode=ro`, sin `WAL`/`CREATE`/`ALTER`, `CacheNotFoundError` (L-10e) | Aplicado: `integrations/doc_organize/cache.py` abre con `read_only=True` y trata `CacheNotFoundError` como caché vacía |
| G22 | doc_organize 0.12.0 (2026-11-02) | `count_entries`/`load_cache_page` con `relative_to=` (búsqueda sobre la ruta relativa) y `conversion_status=` (L-10e) | Aplicado: `relative_to=` (la búsqueda mira la ruta relativa a la carpeta; se retira el riesgo aceptado en la Fase 5) y filtro «Estado» en la lista (`conversion_status=`) |
| G23 | doc_organize 0.12.0 (2026-11-02) | `source_path` del JSON relativo a la carpeta escaneada por defecto (`json_source_path="absolute"` recupera lo anterior) (L-10e) | Aplicado a lo que se convierta desde ahora: el visor antepone la carpeta a la ruta relativa. Los JSON ya generados conservan la ruta absoluta hasta reconvertirse («Forzar reconversión»): el visor la sigue reescribiendo y el ZIP la lleva |
| G8 | doc_organize 0.11.0 (2026-11-01) | Módulo `doc_organize.export` (L-7): `write_project_zip` en *streaming* con `preview_project_zip` exacta, `write_cache_xlsx` y `write_scan_errors_xlsx` con varias cachés, `on_progress` y `CancelToken` | Aplicado en la Fase 5 (`integrations/doc_organize/export.py`): no se copió `web/routes/downloads.py` |
| G9 | doc_organize 0.9.3 (2026-10-31) | Wheel y sdist en GitHub Releases; la web lo fija por URL y hash en `uv.lock` (ADR-006) | No hizo falta vendorizar |
| G14 | doc_organize 0.9.3 (2026-10-31) | Versión 0.9.3 en `pyproject.toml`, `__version__` y tag `v0.9.3` | — |
