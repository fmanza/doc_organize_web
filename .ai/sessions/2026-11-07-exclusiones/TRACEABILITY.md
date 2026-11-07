# TRACEABILITY

## Session metadata
- id: 2026-11-07-exclusiones
- fecha: 2026-11-07
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN

## Prompt issued
«Preparamos plan y audit_plan de estas dos últimas mejoras» (excluir subcarpetas al escanear y patrones de ruido por
ubicación, de `docs/plan/MEJORAS.md`).

## Context supplied
- `docs/plan/MEJORAS.md` (las dos filas anotadas el 2026-11-07)
- `backend/app/db/models.py` (`ScannedFolder`, `Location`), `backend/app/domain/scan/folders.py`,
  `backend/app/domain/runs/operations.py` (`ScanParams`), `backend/app/jobs/operations/scan.py`,
  `backend/app/integrations/doc_organize/scan.py`, `backend/app/domain/locations/service.py`
- doc_organize 1.2.0: `scanner/document_scanner.py` (`exclude_dir`, `IGNORED_NAMES`), `scan/scan_command.py`
  (huérfanos con `force`)

## AI output summary
- Comprobado que doc_organize solo admite un `exclude_dir` (la salida del proyecto) y un `IGNORED_NAMES` fijo: hace
  falta API nueva (G41).
- Comprobado que con `force` todo lo que está en la caché y no aparece en el recorrido es huérfano: lo excluido se
  borra sin código nuevo; sin `force` la caché no se toca.
- Comprobado que cada carpeta guardada tiene su propia caché y su propio `force` (una llamada por carpeta).
- Emitidos PLAN y AUDIT_PLAN (veredicto GO_CONDICIONAL).
- Corregida la fila P3 de MEJORAS: un patrón añadido después sí borra con `force` lo ya convertido.
- Decisiones del mantenedor registradas: por proyecto; `force` cuenta lo excluido como eliminado; reversibles en
  cualquier momento; lo que encaja con un patrón también se borra con `force`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-11-07-exclusiones/00_REQUEST.md` | emitido |
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-11-07-exclusiones/PLAN.md` | emitido |
| Mejoras actualizadas | `docs/plan/MEJORAS.md` | actualizado |

## Directrices para Futuras IAs
- **[escaneo]**: con `force`, doc_organize trata como huérfano todo lo de la caché que no ve en el recorrido; excluir
  algo y forzar borra su salida. Sin `force` no se borra nada.
- **[escaneo]**: las exclusiones se copian en `ScanParams` al encolar; los tramos de un run no deben releerlas de la BD.
- **[librería]**: `IGNORED_NAMES` (`.git`, `__pycache__`, `.DS_Store`) es fijo en doc_organize ≤ 1.2.0.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- Vista previa de `force` con recuento `excluded` antes de confirmar.
- doc_organize 1.3.0 (G41 / L-19) publicada antes de la web 1.4.0.
