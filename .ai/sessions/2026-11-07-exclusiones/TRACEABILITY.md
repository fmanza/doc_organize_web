# TRACEABILITY

## Session metadata
- id: 2026-11-07-exclusiones
- fecha: 2026-11-07
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION (web 1.4.0)

## Prompt issued
«Preparamos plan y audit_plan de estas dos últimas mejoras» (excluir subcarpetas al escanear y patrones de ruido por
ubicación, de `docs/plan/MEJORAS.md`). Después: «/new-feature … Continúa esa sesión: IMPLEMENT → AUDIT_CODE →
VERSION» con doc_organize 1.3.0 publicada (wheel y SHA-256) y el contrato HTTP, las pantallas y los permisos fijados.

## Context supplied
- `docs/plan/MEJORAS.md` (las dos filas anotadas el 2026-11-07)
- `backend/app/db/models.py` (`ScannedFolder`, `Location`), `backend/app/domain/scan/folders.py`,
  `backend/app/domain/runs/operations.py` (`ScanParams`), `backend/app/jobs/operations/scan.py`,
  `backend/app/integrations/doc_organize/scan.py`, `backend/app/domain/locations/service.py`
- doc_organize 1.2.0: `scanner/document_scanner.py` (`exclude_dir`, `IGNORED_NAMES`), `scan/scan_command.py`
  (huérfanos con `force`)
- doc_organize 1.3.0 instalada: `ScanOptions.exclude_paths`/`ignore_patterns`, `ScanSummary.excluded_cached`,
  `EntryFilter.covers_cached` (criterio de la vista previa)

## AI output summary
- PLAN + AUDIT_PLAN (GO_CONDICIONAL): ver `PLAN.md`.
- IMPLEMENT: doc_organize 1.3.0 fijado con hash; migración `0011`; `PUT …/scanned-folders/exclusions`;
  `ignore_patterns` en `PATCH /locations/{id}`; copia en `ScanParams` al encolar; `ScanRequest` → `ScanOptions`;
  recuento `excluded` en la vista previa de «forzar»; explorador con casillas, editor de patrones y aviso en la
  confirmación. OpenAPI exportado y cliente TS regenerado.
- Condiciones del AUDIT_PLAN cumplidas: (2) la vista previa muestra `excluded` antes de la confirmación y cambiar
  exclusiones o patrones invalida una vista previa anterior; (3) doc_organize 1.3.0 publicada antes de la web 1.4.0.
- Desviación del contrato pedido: la ruta es `PUT /api/v1/projects/{id}/scanned-folders/exclusions?subpath=…` (igual
  que `DELETE …/scanned-folders?subpath=…`) en lugar de `/folders/{subpath}/exclusions`: `subpath` lleva `/` y puede
  ser `""` (la raíz).
- AUDIT_CODE: `excluded_cached` se quita del resultado si es 0 (sin exclusiones, el resultado es el de 1.3.0); el aviso
  «N subcarpetas excluidas» solo en el primer tramo de cada carpeta (lo destapó el e2e).
- Validación: backend en la imagen `backend-dev` (Linux, como el CI): ruff, mypy, 540 tests, contrato al día;
  frontend: format, lint, typecheck, 109 tests, build; E2E con Playwright contra un stack aislado
  (`-p dow_e2e140`, puerto 8095) con la imagen 1.4.0.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-11-07-exclusiones/00_REQUEST.md` | emitido |
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-11-07-exclusiones/PLAN.md` | emitido |
| Migración | `backend/alembic/versions/0011_scan_exclusions.py` | nuevo |
| Tests API | `backend/tests/api/test_scan_exclusions.py` | nuevo |
| E2E | `frontend/e2e/exclusions.spec.ts` | nuevo |
| Huecos y tareas | `docs/plan/DOC_ORGANIZE_GAPS.md` (G41 resuelto), `docs/plan/TAREAS_DOC_ORGANIZE.md` (L-19 ✅) | actualizado |
| Mejoras | `docs/plan/MEJORAS.md` (P2 y P3 de exclusiones ✅) | actualizado |
| Changelog | `CHANGELOG.md` `[1.4.0]` | actualizado |

## Directrices para Futuras IAs
- **[escaneo]**: con `force`, doc_organize trata como huérfano todo lo de la caché que no ve en el recorrido; excluir
  algo y forzar borra su salida. Sin `force` no se borra nada.
- **[escaneo]**: las exclusiones y los patrones los rellena `_validate_scan` (`domain/runs/service.py`) en
  `ScanParams.exclusions`/`ignore_patterns` al encolar, descartando lo del cliente; los tramos usan solo `params`.
- **[escaneo]**: `ScanParams.exclusions` va por carpeta guardada con rutas relativas a ella; la API y la interfaz usan
  rutas relativas a la ubicación (`ScanExclusionOut.subpath`).
- **[escaneo]**: `ExclusionMatcher` (`jobs/operations/scan.py`) replica `EntryFilter.covers_cached` de doc_organize
  1.3.0 sin importarla; si la librería cambia su criterio, el recuento `excluded` de la vista previa debe cambiar igual.
- **[escaneo]**: `_PREVIEW_KEYS["scan"]` incluye `exclusions` e `ignore_patterns`: cambiarlos invalida la vista previa
  de «forzar».
- **[exclusiones]**: un enlace simbólico no se puede excluir (400): el recorrido no sigue enlaces y resolverlo
  excluiría su destino. Una exclusión que no existe se guarda tal cual (`exists: false`).
- **[tests]**: la suite del backend se valida en Linux (`backend-dev`); en Windows fallan ~25 tests por rutas con `\`
  que ya fallaban antes de la 1.4.0.
- **[librería]**: `IGNORED_NAMES` (`.git`, `__pycache__`, `.DS_Store`) sigue fijo; los patrones de la ubicación se
  suman a él (doc_organize 1.3.0).

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Commit, PR a `develop`, fast-forward de `main` y tag `v1.4.0`, cuando el mantenedor lo pida.
