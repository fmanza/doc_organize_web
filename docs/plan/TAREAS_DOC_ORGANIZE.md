# Tareas en doc_organize (parte API: librería)

Objetivo: que doc_organize sea una **librería pura con CLI**, con API pública bajo SemVer, sin servidor HTTP, sin
usuarios ni tenants, y distribuida como wheel en GitHub Releases (como util_bbdd). Cada tarea se lanza con
`/new-feature` o `/refactor` en doc_organize; las que rompen compatibilidad se agrupan en la 1.0.0.

Estado de partida (verificado en el repo, 2026-10-31): `pyproject.toml` 0.9.0 pero `__init__.__version__ = "0.1.0"`;
`web/` ≈ 4 700 líneas + 20 plantillas Jinja (~3 700 líneas); `auth/` (7 módulos); 15 de 61 ficheros de test son
`test_web_*`; `ai/*_client.py` importan `doc_organize.auth.InstanceSecretsStore`; `Project.tenant_id` y
`ProjectRegistry(..., tenant_id=)`; cancelación solo cerrando el generador asíncrono.

## Versión 0.10.0 — API pública para la web (sin romper nada)

| ID | Tarea | Detalle | Hueco | Tests / DoD |
|---|---|---|---|---|
| L-0 | Inventario de paridad | Lista de cada pantalla, endpoint (≈ 60), WebSocket (4) y opción de la web actual con la fase de doc_organize_web que la cubre. Se guarda en `doc_organize_web/docs/plan/PARIDAD.md` y gobierna L-10/L-11 | — | Revisado por el usuario |
| L-1 | Fachada pública y versión | `__version__` desde `importlib.metadata`; `__all__` con los puntos de entrada reales (`ScanCommand`, `DeduplicationManager`, `CacheManager`, `ContextBuilder`, `Reorganizer`, `MkDocsGenerator` (→ `SiteGenerator` en L-8), `TaxonomyTemplateRegistry`, modelos y eventos); `py.typed`; página «API pública y compatibilidad» en la documentación | G1, G13 | Test que importa todo `__all__`; `mypy` sobre un consumidor de ejemplo |
| L-2 | Progreso y cancelación cooperativa | `on_progress: Callable[[ProgressEvent], None] \| None` y `cancel_token: CancelToken \| None` en `ScanCommand.run_streaming`, `deduplicate_streaming`, `ContextBuilder.build`; parada entre documentos con `OperationCancelledError`; progreso con unidades (`processed/total`, fase, documento actual). Se mantienen los generadores actuales | G2 | Cancelar a mitad deja `cache.db` coherente; evento final `cancelled` |
| L-3 | Desacoplar `ai/` de `auth/` | Los clientes reciben solo modelos `*Config`; `*_config_from_env()` se mantiene; `*_config_from_store_or_env()` y `InstanceSecretsStore` se marcan *deprecated* (se van con `auth/` en 1.0.0) | G3 | Test de arquitectura: `ai/` no importa `auth/` ni `web/` |
| L-4 | `ProjectLayout` público | Clase que deriva todas las rutas de un proyecto (salida, imágenes, duplicados, historial, errores, carpetas guardadas, contexto, sitio) a partir de `output_root` y `state_root` **separables**. `ProjectRegistry` (JSON) queda como registro local del CLI | G4, G5 | Ningún módulo calcula rutas por su cuenta (grep en test) |
| L-5 | Rutas de estado separadas de las de salida | Toda función que hoy asume `cache.db`/historial junto a las salidas acepta rutas explícitas (ya ocurre en `run_streaming(cache_db=…)`; extender a historial, errores, `folders_json`, `DEDUP_REPORT.json`) | G5 | Escaneo con salida en carpeta A y estado en B sin ficheros cruzados |
| L-6 | Deduplicación en dos pasos y modos | `find_duplicates` como vista previa serializable (grupos con id estable); `resolve_duplicates(groups, mode=move\|copy\|report_only, keep_policy)` aplica **solo** los grupos confirmados; el escaneo deja de resolver duplicados implícitamente (o lo hace solo con opción explícita). Resuelve un problema real de la web actual: con «Deduplicar» marcado, el escaneo mueve los duplicados y la página «Revisar duplicados» ya no encuentra ninguno | G6 | Origen `ro` → `report_only`/`copy` sin escribir en origen |
| L-6b | Eventos versionados | `ScanEvent`, `DedupEvent`, `ContextBuildEvent`, `ContextDeleteEvent` con `schema_version` y `to_dict()` estable; `str(Enum)` sin cambios (se respeta la decisión UP042) | G7 | Test de contrato con JSON de referencia |
| L-6c | Retirar `tenant_id` de la librería (deprecación) | `Project.tenant_id` y el parámetro `tenant_id` de `ProjectRegistry` pasan a *deprecated* (la web gestiona tenants en su BD) | G4 | Aviso `DeprecationWarning` |
| L-6d | Publicación del wheel | Workflow `release.yml`: `python -m build`, wheel + sdist + SHA-256 en GitHub Release `vX.Y.Z`; se elimina `dist/` versionado si lo hubiera | G9 | Wheel instalable desde URL con hash en `uv.lock` |

## Versión 0.11.0 — exportación, sitio y red

| ID | Tarea | Detalle | Hueco |
|---|---|---|---|
| L-7 | Módulo `export/` | Mover la lógica de `web/routes/downloads.py` (ZIP de proyecto en *streaming*, vista previa de exportación, Excel de caché, Excel de errores de escaneo) a `doc_organize.export` (extra `export` = `openpyxl`); nuevo comando CLI `doc_organize export` | G8 |
| L-8 | Sitio de contexto con Zensical | Sustituir `MkDocsGenerator` (escribe `mkdocs.yml` y lanza `mkdocs build`) por `SiteGenerator` que escribe `zensical.toml` + `index.md` y lanza `zensical build`; `generate(..., build: bool, site_dir: Path)`; extra `site` = `zensical`; error tipado si falta, en lugar de `site_built=False` silencioso. `MkDocsGenerator` queda como alias *deprecated* en 0.11.0 y se retira en 1.0.0. Contextos ya generados con `mkdocs.yml`: se regeneran al reconstruir el contexto | G10 |
| L-9 | Robustez en carpetas de red | Reintentos configurables ante `OSError` transitorios en escaneo/hash/copia; prechequeo `size+mtime` antes del hash; rutas UNC y largas en Windows (CLI); política de enlaces simbólicos (no seguir fuera de la raíz); timeout por documento en la conversión | G11 |
| L-9b | Detectores como API | `GpuStatus`, `AvStatus`, `OfficeStatus` expuestos en `doc_organize.diagnostics` para la ficha «capacidades de la instancia» | G12 |

## Peticiones de las Fases 4 a 6 (huecos G16–G26)

Los ID `L-10a…L-10e` de `DOC_ORGANIZE_GAPS.md` son estas peticiones (no confundir con L-10, deprecación de la web).
L-7 se publicó en **0.11.0** (2026-11-01), L-10a…L-10e en **0.12.0** (2026-11-02), que cierra G16–G23, y
L-11a en **0.12.1** (2026-11-02), que cierra G24 y G26.

| ID | Tarea | Detalle | Hueco |
|---|---|---|---|
| L-10a | Caché incremental | Guardar la caché cada N documentos o segundos y en el camino de excepción | G16 |
| L-10b | Carpeta de modelos | Indicar la carpeta de modelos de Docling y prohibir descargas al convertir | G17 |
| L-10c | Nombre de la raíz en la salida | Incluir el nombre de la carpeta escaneada en la ruta de salida cuando hay varias raíces | G18 |
| L-10d | Listado fallido y errores al cancelar | Propagar el `OSError` de listar una carpeta (o no borrar huérfanos si hubo avisos) y escribir `ScanErrorReport` al cancelar | G19 |
| L-10e | API de lectura para la web | `resolve_output_paths`/`resolve_images_dir` en un módulo sin Docling; `CacheManager(read_only=True)`; filtros por ruta relativa y `conversion_status=` en `count_entries`/`load_cache_page`; `source_path` relativo a la carpeta escaneada en el JSON de cada documento | G20–G23 |
| L-11a | Ruta relativa en `duplicados/` (Fase 6) | Parámetro `relative_to` en `move_group`/`resolve_duplicates`/`_move_to_duplicates`: el destino replica la ruta relativa a esa raíz en lugar de la absoluta; un documento fuera de ella falla por fichero; además, no seguir enlaces simbólicos al mover o copiar (ni en el origen ni en la base de `duplicados/`) (no confundir con L-11, retirada de `web/`) | G24, G26 |

## Peticiones de la Fase 7 (huecos G10, G27–G32)

L-8 (prevista para 0.11.0) no se publicó con L-7. Se pidió antes de la Fase 7 (decisión del mantenedor, 2026-11-02),
junto con L-8a…L-8c, y salieron en **0.13.0** (2026-11-02). L-8d…L-8f salen de AUDIT_CODE de la Fase 7 y no
bloquean: la web tiene rodeo.

| ID | Tarea | Detalle | Hueco |
|---|---|---|---|
| L-8a | Reorganizar sin seguir enlaces | `Reorganizer` copia original, Markdown, JSON e imágenes sin seguir enlaces simbólicos (mismo criterio que `_move_to_duplicates` en 0.12.1); un documento enlazado falla por documento, sin copiar el destino del enlace | G27 |
| L-8b | Rutas del contexto públicas | `ProjectLayout` expone las rutas del contexto y del sitio, y un conjunto público de nombres reservados para la carpeta reorganizada | G28 |
| L-8c | Plantillas de taxonomía como texto | `parse_taxonomy_template`/`render_taxonomy_template` (ida y vuelta estable) y listado/carga de las plantillas empaquetadas sin carpeta de usuario | G29 |
| L-8d | Desambiguar nombres al reorganizar | Dos documentos con el mismo `stem` en el mismo dominio y tipo no se sobrescriben en la carpeta reorganizada | G30 |
| L-8e | Temporales sin seguir enlaces | Las escrituras atómicas crean el `.tmp` con `O_EXCL \| O_NOFOLLOW` | G31 |
| L-8f | Validar `Context.output_folder_name` al cargar | `ContextRegistry.load_context` rechaza un nombre que no pase `validate_output_folder_name` | G32 |

## Peticiones de la Fase 8 (huecos G33–G37)

Ninguna bloquea: la web las rodea en `backend/app/integrations/doc_organize/ai.py`.

| ID | Tarea | Detalle | Hueco |
|---|---|---|---|
| L-3a | Parar la IA ante una clave rechazada | `ContextBuilder` deja de llamar a la IA tras un `*AuthError` (o tras `max_failures` errores seguidos) y lo indica en el resultado | G33 |
| L-3b | Reintentos y presupuesto | Reintentos con espera creciente ante errores de conexión y `max_calls` por operación en `AiHttpClientBase` | G34 |
| L-3c | Recuento de la Sub-fase B | `Context` (o el resultado de `build`) dice cuántos documentos se enviaron a la IA, cuántos clasificó y cuántos fallaron | G35 |
| L-3d | Carpeta relativa en la muestra | `select_document_sample` muestra la carpeta relativa a la raíz escaneada, nunca nombres de carpetas por encima de ella | G36 |
| L-3e | Clave fuera de la URL del uso | `LiteLLMUsageClient.get_usage()` no pone la virtual key en la *query* cuando se consulta la propia clave del Bearer (httpx registra cada URL); PENDIENTE DE VERIFICAR que `/key/info` sin `key=` devuelve esa clave | G37 |

## Versión 0.14.0 — deprecación de la web (F8 de la web cerrada el 2026-11-02: se puede pedir ya)

> La 0.12.0 se usó para L-10a…L-10e (robustez del escaneo y API de lectura, G16–G23) y la 0.13.0 para L-8 y
> L-8a…L-8c (Fase 7): L-10 pasa a la siguiente MINOR (2026-11-02).

| ID | Tarea | Detalle |
|---|---|---|
| L-10 | Deprecar `web`, `tenant`, `user` en el CLI | Aviso al arrancar con enlace a doc_organize_web; README y docs indican el nuevo proyecto; CHANGELOG con fecha de retirada |

## Versión 1.0.0 — librería pura (cuando F10 de la web esté cerrada)

| ID | Tarea | Detalle |
|---|---|---|
| L-11 | Retirar `web/` y `auth/` | Borrar `src/doc_organize/web/`, `src/doc_organize/auth/`, `ai_settings_config`, `scan_errors_data`, `pagination`; subcomandos `web/tenant/user`; extra `[web]`; `fastapi/uvicorn/starlette/jinja2/python-multipart` de `dev`; los 15 `test_web_*` y `tests/unit/auth/`; `web/STATE.md` y `docs/adr/ADR-004-GIL-Thread-Safety.md` (pasan a histórico con nota) |
| L-12 | Retirar lo deprecado | `tenant_id` de `Project`/`ProjectRegistry`, `*_from_store_or_env`, `InstanceSecretsStore` |
| L-13 | Documentación | Navegación sin web; guías de instalación/inicio rápido solo CLI/librería; guía de migración «de la web integrada a doc_organize_web»; `zensical build --strict` sin avisos |
| L-13b | Migrar la documentación a Zensical (decisión P4; se puede adelantar a 0.10.0, es independiente) | `mkdocs.yml` → `zensical.toml` (nav, tema, extensiones); referencia de API generada desde *docstrings* (verificar el equivalente a `mkdocstrings` — PENDIENTE DE VERIFICAR); workflows `docs.yml` y `docs-zip-release.yml` y `scripts/build_docs_zip.py`; extra `docs` con `zensical`; `CLAUDE.md` y SHARED cambian `mkdocs build/serve` por `zensical build --strict/serve`; se retiran `mkdocs`, `mkdocs-material` y `mkdocstrings` del extra `docs`. Junto con L-8, **ninguna dependencia de mkdocs queda en el repositorio** |
| L-14 | Instrucciones IA | Ver `INSTRUCCIONES_IA.md` (parte doc_organize) |
| L-15 | Cierre | `/version-closure` 1.0.0, CHANGELOG con *breaking changes*, release con wheel |

## Lo que se queda en la librería y lo que se va

| Se queda (doc_organize) | Se va a doc_organize_web |
|---|---|
| `core/`, `utils/`, `validators/`, `scanner/`, `converter/`, `dedup/`, `cache/`, `scan/`, `context/`, `ai/` (clientes con config explícita), `projects/` (registro local del CLI), `export/` (nuevo), CLI | `web/` completo, `auth/` completo (usuarios, tenants, roles, sesiones, secretos de instancia), configuración IA por familias, paginación HTTP, datos de la página de errores, estado de operaciones activas |
