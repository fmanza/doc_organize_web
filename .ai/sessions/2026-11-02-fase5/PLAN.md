# PLAN — Fase 5: Caché, resultados y descargas (0.6.0)

## 1. Historias y DoD

| ID | Historia | Hecho cuando |
|---|---|---|
| WB-5.1 | Como miembro, veo los documentos del proyecto (caché) paginados y con búsqueda por nombre/carpeta | `GET /projects/{id}/documents` pagina sobre las cachés de todas las carpetas, sin rutas del servidor |
| WB-5.2 | Como miembro, abro el Markdown, el JSON y las imágenes de un documento convertido | `GET /projects/{id}/outputs` sirve solo ficheros de `Conversión/`, tipos permitidos, `nosniff`, sin seguir enlaces |
| WB-5.3 | Como miembro, exporto el ZIP del proyecto (con vista previa de tamaño), el Excel de la caché y el de errores | Runs `export_zip` / `export_xlsx`; el fichero queda como artefacto del run; cuota y espacio comprobados antes |
| WF-5.1 | Pantalla «Documentos»: tabla virtualizada, filtros, visor Markdown saneado y JSON, descargas | Vitest + E2E: escanear → ver documento → exportar → descargar |
| M-FTS (opcional) | Como miembro, busco texto dentro de los documentos convertidos | Índice FTS5 por proyecto actualizado al escanear; `GET /projects/{id}/search` con fragmentos |
| M-BCK (opcional) | Como admin, hago copia de seguridad de las cachés | `python -m app.cli backup` y `verify-backup` con `sqlite3` backup API y manifiesto con SHA-256 |

DoD común del ROADMAP: comandos de desarrollo en verde, OpenAPI exportado y cliente regenerado, migración (si hay),
docs de usuario, E2E de la fase, `docker compose build/up` y `/api/health` 200.

## 2. doc_organize

- Requiere **0.11.0** (L-7): publicada el 2026-11-01, wheel `doc_organize-0.11.0-py3-none-any.whl`
  (`sha256:c46e5a9a…eb9e`). Se sube en `backend/pyproject.toml` (las dos líneas: base y grupo `gpu`), con el extra
  `export` (`openpyxl`), y se regenera `uv.lock`. G8 se cierra sin rodeo.
- Firmas **verificadas** en el tag `v0.11.0` (clon local, solo lectura):
  - `doc_organize.export.load_cache_entries(cache_dbs: Iterable[str|Path]) -> list[CacheEntry]` (async; omite cachés
    inexistentes sin crearlas).
  - `load_scan_error_history(history_logs: Iterable[str|Path]) -> list[ScanErrorReport]` (síncrona).
  - `preview_project_zip(entries, *, layout=None, conversion_dir=None, dedup_report=None) -> ExportStats`.
  - `write_project_zip(destination: str|Path|BinaryIO, entries, *, layout|conversion_dir|dedup_report, on_progress,
    cancel_token) -> ExportStats`; nombres en el ZIP `Conversión/<rel>`, `cache_export.json`; borra el parcial al
    cancelar; `InvalidPathError` si el destino está dentro de `Conversión/`.
  - `write_cache_xlsx(destination, entries, *, on_progress, cancel_token) -> int`;
    `write_scan_errors_xlsx(destination, entries, history, *, on_progress, cancel_token) -> int`;
    `MissingDependencyError` sin `openpyxl`.
  - `ExportStats(file_count, total_size_bytes)`; `ProgressEvent(operation="export", phase=started|export|done)`.
  - `CacheManager(db_path)` async: `count_entries(search=None) -> int`,
    `load_cache_page(limit, offset, search=None) -> list[CacheEntry]` (orden por `file_path`, búsqueda insensible a
    mayúsculas y tildes). **Al abrir escribe** (`journal_mode=WAL`, `CREATE TABLE IF NOT EXISTS`, `ALTER` de migración).
  - `CacheEntry(file_path` **absoluta**, `sha256_hash, timestamp, status, conversion_status, error_message,
    error_retry_count)`.
  - `DocumentConverter.resolve_output_paths(full_path, output_dir, scan_roots) -> (md, json)` y
    `resolve_images_dir(md) = md.parent/"img"/md.stem`: **en `converter/converter.py`, que importa Docling**.

### Huecos nuevos

| ID | Hueco | Rodeo |
|---|---|---|
| G20 | `resolve_output_paths`/`resolve_images_dir` viven en un módulo que importa Docling: la API no puede usarlos (G15) | Derivación pura en la web (`domain/documents/outputs.py`, ~20 líneas) + test de contrato contra doc_organize en `tests/integration` |
| G21 | `CacheManager` no tiene modo solo lectura: abrir una caché escribe (WAL, `CREATE`, `ALTER`) | La API solo abre cachés que existen (`is_file`), con `busy_timeout`; el worker es el único que las crea |
| G22 | `count_entries`/`load_cache_page` solo filtran por ruta, no por estado (errores, pendientes) | Filtro por estado fuera de alcance en 0.6.0 (la página de errores de la Fase 4 ya lista los errores) |

## 3. Contrato HTTP (`/api/v1`)

| Método y ruta | Rol | Respuesta | Errores |
|---|---|---|---|
| `GET /projects/{id}/documents?limit&offset&search&folder` | lector | `DocumentPage{items[], total}`; `DocumentOut{folder, path (relativa a la carpeta), status, conversion_status, error_message (enmascarado), error_retry_count, updated_at, output_path}` | 404, 422 (`limit` ≤ 200) |
| `GET /projects/{id}/outputs?path=<relativa a Conversión/>` | lector | Contenido: `.md` `text/markdown; charset=utf-8`, `.json` `application/json`, imágenes `png/jpg/jpeg/gif/webp`; `nosniff`, `Content-Disposition: inline; filename*=…`, `Cache-Control: private, no-store`, `Content-Security-Policy: default-src 'none'`; tamaño máx. 20 MB (si no, 413 `output_too_large`) | 404 `output_not_found`, 415 `output_type_not_allowed` (SVG, HTML…), 422 `invalid_path` |
| `GET /projects/{id}/search?q&limit&offset&folder` (M-FTS) | lector | `SearchPage{items[{folder, output_path, title, snippet}], total, indexed_at}`; el fragmento marca coincidencias con `\u0002…\u0003` (el cliente las pinta como texto, nunca HTML) | 422 `q` vacía o > 200 |
| `POST /projects/{id}/runs` `operation=export_zip` `{dry_run}` | lector | Run; `dry_run=true` → `result{file_count, total_size_bytes}` | 409 run activo, 422 |
| `POST /projects/{id}/runs` `operation=export_xlsx` `{kind: cache\|errors}` | lector | Run con artefacto `.xlsx` | |
| `POST /projects/{id}/runs` `operation=search_index` (M-FTS) | editor | Run: reindexa el contenido | |

El fichero exportado se descarga con el endpoint de artefactos existente (`/runs/{id}/files/...`), sujeto a
`run_retention_days` y a la cuota por usuario. SSE: los `ProgressEvent(operation="export")` se publican como
`progress` con fase `export` (nueva en i18n).

## 4. Modelo de datos

- **Sin migración de `config.db`**: las cachés siguen en `/data/projects/<id>/folders/<clave>/cache.db` (Fase 4).
- `search.db` (M-FTS) por proyecto en `/data/projects/<id>/search.db` (volumen local, nunca en red):
  `docs` FTS5 (`folder UNINDEXED, path UNINDEXED, title, body`, `tokenize='unicode61 remove_diacritics 2'`) +
  `files(path PK, mtime_ns, size, rowid_doc)` + `meta(indexed_at)`. Fuera de Alembic (se reconstruye entero si cambia el
  esquema: `PRAGMA user_version`).
- Backups (M-BCK) en `/data/backups/<UTC>/` con `manifest.json`.

## 5. Integración, dominio y jobs

- `integrations/doc_organize/cache.py`: `count_documents(cache_dbs, search)`, `documents_page(cache_dbs, limit, offset,
  search)` con import perezoso de `CacheManager` (ver condición C1); `export.py`: `zip_preview`, `write_zip`,
  `write_cache_xlsx`, `write_errors_xlsx` con puente `CancelToken` como en `scan.py`.
- Paginación sobre varias cachés: las carpetas se recorren por `subpath` ordenado; `offset` global → (carpeta, offset
  local) con los `count_entries` de cada una. Una carpeta = una caché disjunta, así que la concatenación es estable.
- **Rutas**: toda `file_path` (absoluta, `/mnt/...`) se reescribe a `<carpeta>/<relativa>` antes de devolverla o
  escribirla en el ZIP/Excel (`CacheEntry.model_copy(update=…)`); mensajes de error por `PathRedactor`.
- `domain/documents/`: servicio de documentos, `outputs.py` (G20) y resolución de `?path=` contra
  `resolve_in(destino, project.output_subpath + "/Conversión", ctx)` → `resolve()` sin enlaces, contenido dentro de la
  raíz, extensión permitida.
- Jobs: `export_zip` (preview → comprueba cuota y espacio libre de `workspace` → escribe en
  `workspace/runs/<id>/export/<proyecto>.zip`), `export_xlsx`, `search_index` (recorre `Conversión/**/*.md`,
  reindexa por `mtime_ns+size`, borra los desaparecidos; tope de 2 MB de texto por documento). El escaneo llama al
  indexador al terminar (`result.search_indexed`).
- `cli.py`: `backup [--dest] [--keep N]` (`sqlite3.Connection.backup` de `config.db` y de cada `cache.db`, manifiesto
  con tamaño y SHA-256) y `verify-backup <dir>` (`PRAGMA integrity_check` + hashes). Restauración: Fase 10.

## 6. Frontend

- Dependencias nuevas (exactas): `@tanstack/react-virtual`, `marked`, `dompurify`.
- `features/documents/`: `DocumentsPage` (tabla virtualizada con `useInfiniteQuery`, búsqueda con *debounce*, filtro
  por carpeta, estados de carga/vacío/error/sin permiso), `DocumentViewer` (pestañas Markdown/JSON; Markdown con
  `marked` → `DOMPurify` (sin `style`, `iframe`, `form`, eventos); imágenes `img/…` reescritas a `/api/v1/projects/{id}/
  outputs?path=…`; enlaces externos con `rel="noopener noreferrer"`), `ContentSearch` (M-FTS), `ExportPanel` (ZIP con
  «Calcular tamaño» y «Exportar», Excel de caché y de errores; enlaza al run).
- Rutas `projects/:projectId/documents`, `…/documents/view?path=`, `…/search`. Sustituye al visor de caché del
  `dashboard.html.j2` y a las descargas de la web integrada.

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| XSS por contenido convertido (Markdown con HTML, SVG, JSON) | DOMPurify, SVG/HTML no se sirven (415), CSP `default-src 'none'` y `nosniff` en `/outputs` |
| Fuga de rutas del servidor (`file_path` absoluta) en API, ZIP y Excel | Reescritura a rutas relativas + `PathRedactor`; tests que buscan `/mnt` en las salidas |
| ZIP de ~1 TB llena `workspace` | Vista previa obligatoria en el job: cuota de usuario y espacio libre antes de escribir (`export_too_large`) |
| Contención SQLite: la API abre `cache.db` mientras el worker escribe | WAL + `busy_timeout`; la API no crea cachés (G21) |
| `search.db` grande (100 000 documentos) | Tope por documento, índice incremental, en `/data` local |
| Recorrer `Conversión/` por red es lento | Solo en jobs (vista previa, índice); la API hace como mucho un `stat` por fichero servido |
| Memoria al exportar (todas las entradas en memoria) | ~100 000 `CacheEntry` ≈ 100 MB, dentro del límite del worker |

## AUDIT_PLAN — decisiones del mantenedor (2026-11-02)

- **C1 (G15)**: la API importa `doc_organize.cache` **al usarlo** (dentro de la función de la capa anticorrupción). El
  test de arquitectura pasa a exigir que ni `app.main` ni el worker carguen doc_organize **al arrancar** y que la API
  nunca cargue `docling` ni `torch` tras listar documentos.
- **C2**: exportar (ZIP y Excel) es de **lector** (cualquier miembro), con cuota y espacio comprobados;
  `search_index` es de editor.
- **C3**: `app.cli backup` copia `config.db` **y** todas las `cache.db` (adelanta esa parte de la Fase 10);
  `search.db` no se copia (se regenera). Restauración: Fase 10.
- Huecos nuevos G20–G22 a `DOC_ORGANIZE_GAPS.md`. PARIDAD: filas `cache.py` y las cuatro de `downloads.py`.
- **Veredicto: GO** (pendiente de autorizar IMPLEMENT).

## 8. Pruebas

- Unit: paginación multi-caché, reescritura de rutas, derivación de salidas (G20), consulta FTS sin inyección de
  sintaxis, manifiesto de backup.
- API: documentos (roles, búsqueda, 404 de otro proyecto), `/outputs` (traversal `..`, enlace simbólico, SVG 415,
  tamaño 413, cabeceras), runs de exportación (roles, `dry_run`), búsqueda.
- Jobs (en proceso, `JobContext` real): ZIP con rutas relativas y sin `/mnt`, cancelación borra el parcial, cuota
  superada, Excel de errores enmascarado, indexador incremental.
- Integración: contrato G20 contra `DocumentConverter.resolve_output_paths`; export real con caché de escaneo.
- Frontend: tabla, visor saneado (un `<script>`/`onerror` en el Markdown no llega al DOM), export.
- E2E: escanear → Documentos → abrir → buscar contenido → exportar ZIP → descargar.
