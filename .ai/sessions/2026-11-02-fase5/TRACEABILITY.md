# TRACEABILITY

## Session metadata
- id: 2026-11-02-fase5
- fecha: 2026-11-02
- rama: feature/fase-5 (desde develop 1895ed5, 0.5.0)
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
/phase — Fase: 5. Inputs completados por el mantenedor: alcance completo; mejoras opcionales «búsqueda de texto
completo» y «backup de cache.db»; restricciones doc_organize 0.11.0 (L-7 publicado el 2026-11-01), dependencias nuevas
permitidas si hacen falta, sin GPU ni red en las pruebas.

## Context supplied
- ROADMAP (Fase 5 y Fase 10), PARIDAD, DOC_ORGANIZE_GAPS, TAREAS_DOC_ORGANIZE, MEJORAS, TRACEABILITY de la Fase 4
- doc_organize `v0.11.0` (clon local, solo lectura): `export/{sources,zip_export,xlsx_export,_progress}.py`,
  `cache/cache_manager.py` (`count_entries`, `load_cache_page`, apertura con escritura), `projects/layout.py`,
  `converter/converter.py` (`resolve_output_paths`, `resolve_images_dir`, `source_path` en el JSON), `core/models.py`
- Notas del mantenedor sobre 0.11.0 (escrituras síncronas, diferencias con la web anterior)
- Release `v0.11.0` de doc_organize: wheel con SHA-256 `c46e5a9a…eb9e`, igual que el hash de `uv.lock`

## AI output summary
- PLAN + AUDIT_PLAN: `GO_CONDICIONAL` con 3 condiciones; el mantenedor las resolvió → GO:
  - C1: la API importa `doc_organize.cache` al usarlo (no al arrancar; nunca Docling ni torch, test de arquitectura);
  - C2: exportar es de cualquier miembro (lector), reindexar de editor;
  - C3: el backup copia `config.db` y las cachés (adelanta esa parte de la Fase 10; restauración en la Fase 10).
- IMPLEMENT backend:
  - doc_organize 0.11.0 con el extra `export`;
  - `domain/documents` (listado multi-caché, visor, nombres relativos), `domain/search` (FTS5),
    `domain/scan/state.py` (`folder_state`, `folder_cache`, `CONVERSION_DIR`);
  - capa anticorrupción `cache.py` y `export.py`;
  - operaciones `export_zip` (`dry_run` = tamaño), `export_xlsx` (`cache`/`errors`) y `search_index`, y reindexado al
    final del escaneo;
  - router `api/v1/documents.py`; `app/db/backup.py` y `app.cli backup|verify-backup`. Sin migración de `config.db`.
- IMPLEMENT frontend: `features/documents` (lista virtualizada, visor `marked` + DOMPurify, búsqueda en el contenido,
  panel de exportaciones), rutas y botón «Documentos» en el proyecto.
- Hallazgo durante la E2E: el JSON de cada documento lleva `source_path` absoluta (`/mnt/...`); el visor la reescribe a
  relativa (G23).
- AUDIT_CODE:
  - Code Auditor: APROBADO CON CONDICIONES.
    - HIGH-1: el ZIP lleva `source_path` absoluta en los JSON → **decisión del mantenedor**: aceptado y pedido a
      doc_organize (L-10e). Documentado en la guía y el CHANGELOG, y docstrings corregidos.
    - Corregidos:
      - M1: `search_index` es escritura (un solo escritor de `search.db`);
      - M2: el reindexado al final del escaneo no se cancela;
      - M4: FTS5 con tokens de 2 o más caracteres, máximo 8, y 5 s con `search_too_broad`;
      - M5: las cachés se cargan una vez y se comprueba la cancelación antes de escribir;
      - L2: `OSError` → `export_failed`;
      - L3: índice a medio crear → vacío;
      - L4: carpeta de la búsqueda validada y limitada a las del proyecto;
      - L5: G20–G23 registrados;
      - L6: copia a medias borrada y `FileExistsError` capturado en la CLI;
      - L7: `DocumentOut.status` abierto.
    - M3 (búsqueda sobre la ruta absoluta): aceptado por el mantenedor (G22).
    - L1 (cuota en Excel): pendiente.
  - Security Reviewer: sin CRITICAL ni HIGH.
    - Corregidos:
      - M1 (TOCTOU con enlaces en `/outputs`): lectura desde el descriptor, `O_NOFOLLOW`/`O_NONBLOCK`, `fstat` de
        fichero normal y ruta real (`/proc/self/fd`) dentro de `Conversión/`;
      - L3: permisos 0700/0600 en las copias;
      - L4: rutas del manifiesto validadas;
      - L5: = M4 del Code Auditor;
      - nota: `frame-ancestors 'none'` en la CSP.
    - L1/L2 aceptados (G22/G23); L6 = G21.
  - Frontend Reviewer: GO_CONDICIONAL.
    - Corregidos:
      - H1: bucle de peticiones si falla la página siguiente → «Reintentar»;
      - M1: error inicial y vacío a la vez;
      - M2: la lista vuelve arriba al filtrar y no pide páginas de los datos provisionales;
      - M3: visor sin `path`;
      - M4: error con spinner en la búsqueda;
      - M5: `role="status"` en totales y vacíos;
      - L1: `aria-setsize`/`aria-posinset`;
      - L2: contenedor con `tabIndex`;
      - L4: pestaña JSON solo para `.md`;
      - L5: raíz en los dos filtros;
      - L6: HTML serializado en un documento inerte;
      - L7: solo gira el botón pulsado.
    - Pendientes L3 (paginación sin nombres) y L8 (tests de errores).
- Validación final:
  - backend: ruff, mypy, 342 tests en Linux (imagen `backend-dev`), OpenAPI exportado;
  - contrato G20 contra doc_organize 3/3 parametrizado en 6 casos;
  - frontend: format, lint, typecheck, 57 tests y build;
  - `zensical build --strict`;
  - imagen 0.6.0 con `/api/health` 200 y doc_organize 0.11.0;
  - E2E 11/11 con un worker de Playwright (`documents.spec.ts` nuevo: escaneo, lista, visor, JSON sin `/mnt`,
    búsqueda en el contenido y Excel descargado).
  - En Windows con Docker Desktop, en paralelo, fallan los inicios de sesión simultáneos del arranque (5 s de espera);
    con un worker pasan todos.

## Artefactos generados
- `backend/app/domain/documents/`, `backend/app/domain/search/`, `backend/app/domain/scan/state.py`,
  `backend/app/integrations/doc_organize/{cache,export}.py`, `backend/app/jobs/operations/{export,search_index}.py`,
  `backend/app/api/v1/documents.py`, `backend/app/db/backup.py`
- `backend/tests/api/test_documents.py`, `backend/tests/jobs/test_export_operation.py`,
  `backend/tests/unit/test_documents_search_backup.py`, `backend/tests/integration/test_documents_contract.py`
- `frontend/src/features/documents/`, `frontend/e2e/documents.spec.ts`
- `docs/guides/documentos.md`
- `build/logs/fase5-*.txt` (local, git-ignored)

## Directrices para Futuras IAs
- **[documentos]**: la caché de doc_organize guarda rutas **absolutas** del contenedor. Todo lo que sale hacia el
  usuario pasa por `app.domain.documents.paths.DocumentNamer` (`split`/`display`/`text`) con las raíces de
  `folder_roots` (ruta registrada + resuelta). Las cachés son una por carpeta (`app.domain.scan.state.folder_cache`).
- **[documentos]**: el listado pagina sobre varias cachés en el orden de `project.source_subpaths` (sin distinguir
  mayúsculas): cuenta cada una y traduce `offset` global a local. No hay carpetas anidadas, así que no se solapan.
- **[visor]**: `GET /outputs` lee con `_read_inside` (descriptor abierto, `O_NOFOLLOW`, `fstat`, ruta real en
  `/proc/self/fd` dentro de `Conversión/`) y devuelve `Response` con bytes. No uses `FileResponse`: reabre la ruta y
  reintroduce el TOCTOU.
- **[doc_organize]**: `resolve_output_paths` importa Docling. La API usa `app.domain.documents.outputs.output_paths`,
  y cualquier cambio de esa regla en doc_organize debe reflejarse ahí (contrato en
  `tests/integration/test_documents_contract.py`, `pytest -m integration`).
- **[doc_organize]**: `CacheManager` escribe al abrir (G21): la API solo abre cachés con `is_file()`. Las cachés las
  crea el worker.
- **[búsqueda]**: `search.db` lo escribe solo el worker. `search_index` es `is_write` y el escaneo reindexa dentro de
  su propio run, así que nunca hay dos escritores. La API lo abre con `mode=ro`. Las consultas pasan por
  `match_query` (palabras de 2 o más caracteres entre comillas, máximo 8) y tienen 5 s de límite.
- **[exportaciones]**: `ExportRequest.loaded` cachea las entradas entre la vista previa y la escritura.
  `cache_export.json` y los Excel van con rutas relativas, pero los JSON de `Conversión/` en el ZIP llevan
  `source_path` absoluta (G23, aceptado) hasta L-10e.
- **[backup]**: `app.cli backup` usa `sqlite3.Connection.backup` con `umask 077`. `search.db` no se copia. La
  restauración guiada es de la Fase 10.
- **[tests]**: en Windows fallan 6 tests previos (separadores `\` y enlaces simbólicos sin privilegios). La suite se
  valida en Linux:
  `docker run --rm -v "$PWD/backend:/src/backend" -v "$PWD/openapi:/src/openapi" doc_organize_web:backend-dev uv run --frozen pytest`.
- **[e2e]**: en Docker Desktop (Windows), `npx playwright test --workers=1`; en paralelo, los inicios de sesión del
  arranque superan los 5 s.

## Pendientes (no bloquean)
- Pedir a doc_organize L-10e (G20–G23) además de L-10a–L-10d.
- Code Auditor L1 (cuota para los Excel); Frontend Reviewer L3 (nombres de la paginación) y L8 (tests de errores).
- Reindexar tras cada escaneo recorre todo `Conversión/`, aunque se escaneara una sola carpeta (aceptable con mtime;
  revisar a escala en la Fase 10).
- El recuento y la página del listado se calculan por separado: con un escaneo escribiendo a la vez puede repetirse o
  saltarse una fila.

## Veredicto final
GO — Fase 5 cerrada en 0.6.0 (riesgos G22/G23 aceptados por el mantenedor hasta L-10e).
