# TRACEABILITY

## Session metadata
- id: 2026-11-17-manifest-from-template
- fecha: 2026-11-17
- rama: `feat/manifest-versions` (PR #70; parte 1, W1 del plan único de doc_organize 2.0.0); plan en
  `docs/plan-2.0-manifiesto` (PR #69); release **1.8.0** desde `develop`
- skill: new_feature
- fase: IMPLEMENT + AUDIT_CODE + VERSION (1.8.0) de la **parte 1** (manifiesto). Versión objetivo: **1.8.0** (D17 del plan único: sale
  antes de la 2.0.0, sobre doc_organize 1.6.x). La parte 2 (ejes) es de la 2.0.0

## Prompt issued
«Empieza con W1, la web 1.8.0».

## Context supplied
- `.ai/sessions/2026-11-17-manifest-from-template/PLAN.md` (revisión 6; parte 1 con 17 condiciones, GO_CONDICIONAL).
- `doc_organize/.ai/sessions/2026-11-17-ai-2.0/PLAN.md` (plan único 2.0.0; W1, D17, U4, U5).

## AI output summary
- **Backend**: migración `0015` (`project_manifest_versions`), `domain/context/manifest_versions.py` (versiones, recorte
  a 5, `etag`, cerrojo por proyecto), `service.py` (`_mutate_manifest`: `If-Match` → versión confirmada → escritura;
  `save_manifest`, `delete_manifest`, `restore_manifest`), API (`DELETE`, `versions`, `versions/{id}`, `restore`),
  errores (`etag_required`, `manifest_changed`, `manifest_not_found`, `manifest_version_not_found`,
  `manifest_version_invalid`), auditoría de borrar y restaurar sin texto, `history_clear` guarda la versión antes de
  vaciar.
- **Frontend**: selección del catálogo y borrador del manifiesto en `ContextPage` (estado derivado de `built_at`, sin
  efectos), `BuildCard` controlado, «Personalizar para este proyecto», confirmación común `replaceDraft`, foco al
  editor, «Construir» bloqueado con borrador solo con su catálogo; `ManifestCard.tsx` (nuevo) con versiones, ver,
  restaurar, cargar en el editor, borrar y aviso de contexto desfasado; lectores con enlace «Ver el manifiesto».
- **Docs**: `docs/guides/contexto.md` (catálogos corregidos, «¿Descubrir dominios o manifiesto?», versiones),
  `proyectos.md`, CHANGELOG (Unreleased).

## Condiciones del AUDIT_PLAN (parte 1)

| # | Condición | Estado |
|---|---|---|
| 1 | F4: todas las plantillas incluidas se aceptan como manifiesto | ✅ `test_every_builtin_template_is_accepted_as_manifest` |
| 2 | T1: selección inicial desde `initialSelection(context)` y reiniciada al reconstruir | ⚠️ implementado (estado derivado de `built_at`); el reinicio tras reconstruir **no tiene test** propio |
| 3 | F2/F3: copiar nunca guarda; confirmación; sin construir con borrador | ✅ tests de frontend |
| 4 | Ayuda de «Descubrir dominios» como la librería 1.6.0 | ✅ texto y test |
| 5 | A1/A2: textos de ayuda y guía | ✅ |
| 6 | A3: bloqueo solo con «Manifiesto del proyecto» | ✅ test |
| 7 | A4: sin `useEffect` | ✅ |
| 8 | A5: tests afectados actualizados | ✅ `context.test.tsx`, `ai.test.tsx`, `e2e/ai.spec.ts` (el e2e no se ha ejecutado en local) |
| 9 | A6/A7: confirmación común y foco | ✅ tests |
| 10 | Versión de lo que había y 5 por proyecto | ✅ |
| 11 | S4: IDOR por proyecto y versión | ✅ |
| 12 | T6: fichero y versión sincronizados ante fallo | ✅ |
| 13 | Guardar vacío rechazado; borrar solo explícito | ✅ |
| 14 | B1: «Vaciar histórico» guarda versión y lo dice | ✅ test de worker y texto de confirmación |
| 15 | B2: `etag`/`If-Match` y 409 | ✅ |
| 16 | B3: versión antes de escribir; fallo vs. timeout | ✅ tests (timeout simulado con `LocationUnavailableError`) |
| 17 | B4: borrado sin seguir enlaces | ✅ `os.unlink` tras `lstat` (test con enlace, solo POSIX) |

## Desviaciones del plan
- Borrar usa `lstat` + `os.unlink` en `service.py` en lugar de `jobs/operations/_files.py`, que no tiene borrado de un
  solo fichero (solo `delete_tree`); mismo criterio: solo un fichero normal, nunca se sigue un enlace.
- Las versiones y el `etag` normalizan los saltos de línea a `\n` (la librería escribe con el del sistema).
- Un manifiesto mayor de 4 MiB (solo posible editándolo fuera) se puede sustituir, pero su versión queda sin texto
  (aviso en el log).

## Verificación
- CI de #70 en verde (backend, frontend, docs, imagen con E2E). Dos correcciones durante el CI: el E2E pulsaba el
  `input` sin tamaño del `SegmentedControl` (se pulsa su etiqueta) y un test esperaba al texto y no al botón «Ver».
- Backend: ruff, mypy, pytest completo (600 passed + 27 con `caplog`), `export_openapi.py --check`.
- Frontend: format, lint, typecheck, `npm test` (142 passed), build. Docs: `zensical build --strict` sin avisos.

## Directrices para Futuras IAs
- El manifiesto se cambia siempre con `If-Match` (el `etag` del `GET`); la versión se confirma antes de escribir.
- En 2.0.0 (U4), una versión v1 restaurada debe guardarse migrada a v2.
