# PLAN — Fase 6: Duplicados (0.7.0)

## 1. Historias y DoD

| ID | Historia | Hecho cuando |
|---|---|---|
| WB-6.1a | Como editor, lanzo una **vista previa** de duplicados (exactos, conflictos de versión y, si lo pido, por nombre parecido) de todas las carpetas del proyecto | Run `dedup_preview`: grupos con `group_id` estable guardados en `config.db`, resumen en el run, sin tocar ficheros |
| WB-6.1b | Reviso los grupos paginados y elijo qué conservar en cada uno | `GET /runs/{id}/duplicate-groups` paginado; rutas relativas a la carpeta; enlace al documento convertido |
| WB-6.1c | **Aplico** solo los grupos confirmados: mover a `duplicados/`, copiar o solo informe | Run `dedup_apply` con modo seco, vista previa vigente, nombre tecleado, rol y ubicación `rw`; auditoría por fichero; informe `DEDUP_REPORT.json`/`DEDUP_HISTORY.jsonl` en el estado del proyecto |
| WF-6.1 | Resolutor: comparación lado a lado, umbral difuso, política de conservación, confirmación e informe; aviso si la última aplicación ya resolvió los duplicados | Vitest + E2E: vista previa → elegir → aplicar (copiar) → informe |
| M-XLSX (opcional) | Descargo los grupos como Excel | Artefacto `duplicados.xlsx` de la vista previa, sin rutas del servidor y sin fórmulas |

DoD común del ROADMAP (migración con `downgrade`, tests de autorización, E2E, guía, PARIDAD…).

## 2. doc_organize

Requiere L-6 (0.10.0), ya consumida en **0.12.0**. Firmas **verificadas** en `v0.12.0`:

- `DeduplicationManager().find_duplicates(docs: list[DocumentMetadata], fuzzy_threshold: int | None = None)
  -> list[DuplicateGroup]` — síncrona, solo compara metadatos (hash, nombre, `modified_time`); exactos por hash,
  conflictos de versión por nombre base + extensión, y con `fuzzy_threshold` (0–100) pares por `WRatio` con
  `rapidfuzz.process.cdist` sobre lo que quede (matriz n×n).
- `DuplicateGroup(group_id, canonical_doc, duplicates, reason, user_choice)`; `group_id` =
  `stable_group_id(docs, reason)` (UUID derivado de razón + `full_path|sha256` de los miembros); canónico = el más
  antiguo; `user_choice` sustituye al canónico.
- `await move_group(group, duplicates_dir, *, mode: DedupMode = "move") -> (exactos, versiones, fallidos)`;
  `DedupMode = move | copy | report_only`; un `OSError` por fichero no para el grupo.
- `await finalize_report(groups, duplicates_dir, exact, version, started_at, failed_paths=, report_dir=, mode=)`
  → escribe `DEDUP_REPORT.json` y añade a `DEDUP_HISTORY.jsonl` en `report_dir` (L-5: `ProjectLayout.dedup_report_dir`).
- `DocumentMetadata(full_path, display_name, extension, size_bytes, modified_time, sha256_hash)` (público).
- `ProjectLayout.duplicates_dir` (`<salidas>/duplicados`), `dedup_report_dir`, `dedup_report`, `dedup_history`.
- `ScanCommand.deduplicate_streaming` (escanea y hashea **todo** el origen y mueve todos los grupos sin revisión): no
  se usa; la web compone `find_duplicates` + `move_group` + `finalize_report` con sus propios puntos de cancelación.

### Huecos nuevos

| ID | Hueco | Rodeo propuesto |
|---|---|---|
| G24 | `_move_to_duplicates` replica la **ruta absoluta** del origen bajo `duplicados/` (`duplicados/mnt/origen/2024/a.pdf`) | Ver condición C1 |
| G25 | No hay forma pública de construir `DocumentMetadata` desde la caché (tamaño y fecha no están en `CacheEntry`) | La web los construye con la caché (hash) + `stat` (tamaño, fecha); sin rehashear el origen |

## 3. Contrato HTTP

| Método y ruta | Rol | Respuesta |
|---|---|---|
| `POST /projects/{id}/runs` `dedup_preview {fuzzy_threshold?: 50–100}` | editor | Run; `result{groups, exact, version_conflicts, fuzzy, documents, reclaimable_bytes, stale_cache}`; artefacto `duplicados.xlsx` |
| `GET /runs/{id}/duplicate-groups?limit&offset&reason` | miembro con acceso al run | `DuplicateGroupPage{items[{group_id, reason, members[{folder, path, size_bytes, modified_at, sha256, canonical, output_path}]}], total}` |
| `POST /projects/{id}/runs` `dedup_apply {groups_run_id, mode, groups[{group_id, keep: "<carpeta>/<ruta>"}], dry_run, preview_run_id, confirm_name}` (implementado: `groups_run_id` es la búsqueda y `preview_run_id` el `dry_run`) | ver C3 | Run; con `dry_run` cuenta qué se movería/copiaría y lo que ya no coincide; real: `result{moved, failed, skipped_changed, mode}` |
| `GET /projects/{id}/duplicates/last` | miembro | Última aplicación (run, modo, fecha, recuentos) para el aviso «ya se resolvieron» |

Errores: `422 preview_required`/`preview_mismatch` (grupo que no está en la vista previa), `409 write_locked`,
`422 location_read_only` (mover con origen `ro`), `422 fuzzy_too_large`.

## 4. Modelo de datos (migración `0006_duplicates`)

- `duplicate_groups`: `run_id` (FK `runs`, cascade), `group_id` (str 36), `reason`, `position`, `member_count`,
  `members` (JSON: `folder`, `path` relativa, `size_bytes`, `modified_time`, `sha256`, `canonical`); PK
  (`run_id`, `group_id`); índice (`run_id`, `reason`, `position`). Se borra con el run (retención).
- Sin columnas nuevas en otras tablas. `downgrade` borra la tabla.

## 5. Dominio, integración y jobs

- `integrations/doc_organize/dedup.py`: `find_groups(docs, fuzzy_threshold)` y `apply_groups(groups, duplicates_dir,
  report_dir, mode, on_group, is_cancelled)` con tipos propios (`DedupDocument`, `DedupGroup`).
- `jobs/operations/dedup.py`:
  - **preview**: documentos de las cachés de todas las carpetas (`load_cache_entries`) + `stat` en el origen (G25;
    los que ya no existen se descartan y se cuentan en `stale_cache`); `find_duplicates`; grupos a `duplicate_groups`
    con rutas relativas; Excel opcional (M-XLSX). Umbral difuso solo si quedan ≤ 5 000 documentos sin agrupar
    (C4; `fuzzy_too_large`).
  - **apply** (y su `dry_run`): carga de la vista previa solo los `group_id` enviados (los fuzzy solo si se envían);
    re-resuelve cada miembro con el resolvedor; **rehashea** los miembros de esos grupos y los compara con la vista
    previa: si algo cambió, el grupo se salta (`skipped_changed`); `move_group` por grupo con `user_choice` =
    `keep`; cancelación entre grupos (fase crítica dentro de cada grupo); auditoría `duplicate.move`/`.copy` por
    fichero (relativa); `finalize_report` con `report_dir` = estado del proyecto. Progreso por grupo.
- Reglas (regla 7): `move` exige origen `rw` (sale del origen) y destino `rw`; `copy` exige destino `rw`;
  `report_only` no escribe ficheros. `dedup_apply` real es `is_write` y exige vista previa de aplicar (`dry_run`)
  vigente + nombre tecleado; la vista previa de duplicados caduca a los 60 min (PREVIEW_TTL propio) o si hubo otra
  escritura en el proyecto.
- `ZIP` del proyecto: pasa `dedup_report` (estado) a `write_project_zip`.

## 6. Frontend

- `features/duplicates/`: `DuplicatesPage` (lanzar vista previa con umbral difuso opcional, aviso de última
  aplicación, resumen), `DuplicateGroupList` (paginada en servidor, por motivo), `GroupCard` (miembros lado a lado:
  carpeta, ruta, tamaño, fecha, hash corto, «conservar» por radio, enlace «Ver» al Markdown convertido), barra de
  política (más antiguo / más reciente / ruta más corta) e inclusión (exactos y versiones incluidos por defecto,
  parecidos solo si se marcan), `ApplyModal` (modo, `dry_run` → recuentos → nombre del proyecto → aplicar).
- Selección guardada en cliente por `group_id` (no se pierde al paginar). Botón «Descargar Excel» del run.
- Ruta `projects/:projectId/duplicates`; botón «Duplicados» en el proyecto.

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| Mover ficheros del **origen** (pérdida de datos) | Rol (C3), `rw`, dos vistas previas (grupos + aplicar), nombre tecleado, rehash antes de mover, `move_group` no sobrescribe, auditoría por fichero, informe |
| Caché desactualizada (fichero cambiado desde el escaneo) | Rehash de los miembros al aplicar; los grupos cambiados se saltan |
| Difuso O(n²) en memoria | Tope de 5 000 documentos sin agrupar (C4) |
| Rutas del servidor en `duplicados/` (G24) e informes | C1; las respuestas y el Excel solo con rutas relativas |
| Vista previa con miles de grupos | Paginada en servidor; selección en cliente |
| Montaje de red caído a mitad | `OSError` por fichero → `failed`; cancelación entre grupos |

## AUDIT_PLAN — decisiones del mantenedor (2026-11-02)

- **C1 (G24)**: se pide a doc_organize un parámetro para que `duplicados/` replique la ruta **relativa** a la
  ubicación de origen (`duplicados/2024/a.pdf`); se implementa todo lo demás y la fase se cierra cuando esté publicado.
- **C2**: la vista previa usa la caché (hash) + `stat`; al aplicar se rehashean los miembros de los grupos elegidos y
  se saltan los que hayan cambiado.
- **C3**: vista previa, copiar y solo informe: **editor**; mover: **propietario**.
- **C4**: modo difuso con tope de **5 000** documentos sin agrupar (`fuzzy_too_large`).
- Huecos nuevos G24 (petición L-11a) y G25 (rodeo en la web). PARIDAD: `duplicates_resolver.html.j2`,
  `scan.py` `/scan/deduplicate`, `duplicates.py` GET y POST `/resolve`.
- **Veredicto: GO** (pendiente de autorizar IMPLEMENT).

## 8. Pruebas

- Unit: construcción de documentos desde caché + stat, política de conservación, validación de `keep`.
- API: roles por modo, `preview_required`, grupos ajenos a la vista previa, `ro` + `move` rechazado, paginación.
- Jobs (con doc_organize real, sin Docling): preview exactos/versiones/difuso; apply move/copy/report_only; fichero
  cambiado → saltado; cancelación entre grupos; auditoría; informe en el estado; Excel sin rutas.
- Frontend: selección, política, modal de aplicar. E2E: vista previa → copiar → informe.
