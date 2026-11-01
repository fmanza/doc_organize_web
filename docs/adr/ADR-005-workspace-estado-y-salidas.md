# ADR-005 — Workspace, estado y salidas: tres zonas

- **Estado**: Aceptado (volúmenes desde la Fase 0; layout de proyectos y runs implementado en la Fase 3, 0.4.0)
- **Fecha**: 2026-10-31

## Contexto

doc_organize escribe su estado (`cache.db`, historial, errores, carpetas guardadas, `DEDUP_REPORT.json`) junto a las
salidas del proyecto (G5). Las salidas pueden ir a una carpeta de red (D3), pero **SQLite con WAL no es fiable sobre
SMB/NFS**: una caché de ~100 000 documentos en red se corrompería. Además cada ejecución produce artefactos propios
(exportaciones, informes) que no son salidas del proyecto.

## Decisión

Tres zonas con propósitos y volúmenes distintos:

| Zona | Dónde | Contenido | Puede ser de red |
|---|---|---|---|
| **Estado** | volumen local `data` (`DOW_DATA_DIR`) | `config.db` y `projects/<project_id>/cache.db` (+ historial y errores de doc_organize cuando sean inyectables, L-5) | **No** |
| **Artefactos** | volumen `workspace` (`DOW_WORKSPACE_DIR`) | una carpeta por ejecución: `run.json`, `logs/run.log`, `outputs/` | No (volumen local) |
| **Salidas** | ubicación destino `rw` (ADR-007) | Markdown, JSON, imágenes, duplicados, sitio de contexto | Sí |

- Rutas de `data` y `workspace` construidas solo con IDs; servir un fichero exige `resolve()` +
  `is_relative_to(raíz)` y permiso sobre el proyecto.
- El origen solo se lee (salvo resolución de duplicados en una ubicación `rw`, con confirmación, ADR-009).
- `cache.db` pertenece a doc_organize: la web lo lee solo a través de la capa anticorrupción, paginado.

## Consecuencias

- Hasta que doc_organize permita inyectar todas las rutas de estado (L-5), solo `cache.db` se separa; el resto del
  estado queda en el destino (rodeo de G5).
- Backup: `config.db` y cada `cache.db` con `sqlite3 .backup` (Fase 10); las salidas, con el backup del almacenamiento
  donde residan.

## Notas de implementación (Fase 3, 0.4.0)

- Con doc_organize 0.10.0 (`ProjectLayout(output_root, state_root=)`, L-5) **todo** el estado de un proyecto (caché,
  historial y errores de escaneo, carpetas guardadas, informes de deduplicación) vive en `DOW_DATA_DIR/projects/<id>/`:
  el rodeo de G5 ya no hace falta.
- La **carpeta de salidas pertenece al proyecto**: al crearlo debe ser nueva o estar vacía (decisión del mantenedor,
  2026-11-01), de modo que vaciar o borrar el proyecto no toca ficheros ajenos. Se guarda relativa a su ubicación y se
  vuelve a resolver con el resolvedor de ubicaciones en cada uso (también en el worker).
- **Workspace**: `runs/<uuid>/{run.json, logs/run.log, outputs/}`, rutas construidas solo con el UUID. Los artefactos
  se descargan por id con `Content-Disposition: attachment`, `nosniff` y tipo fijo (`application/octet-stream` salvo
  texto, JSON, CSV y ZIP). La purga por `run_retention_days` borra la carpeta y deja el run en el historial (descarga →
  410). `user_quota_mb` limita la suma de artefactos vivos por usuario (409 `quota_exceeded` al encolar).
