# TRACEABILITY

## Session metadata
- id: 2026-11-22-ia-alcance-construir
- fecha: 2026-11-22
- rama: feature/2.1
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE

## Prompt issued
«si» (a planificar un selector en «Construir» para pedir a la IA también los ejes vacíos), tras adaptar un prompt de
normalización de un SGI a un manifiesto con un eje `rules: false` («Acción de migración»).

## Context supplied
- doc_organize 2.0.1: `ContextBuilder.build(ai_scope=…)` y `_classify_with_ai` (`missing_axes` incluye los ejes `rules: false`).
- Web: `domain/runs/operations.py` (`ContextBuildParams`, `ContextDryRunParams.ai_scope`), `jobs/operations/context.py:341`,
  `features/context/QualityPage.tsx` (selector de alcance existente), `core/config.py` (`ai_max_documents_per_run`).

## AI output summary
- Comprobado que la web fija `ai_scope="unclassified"` al construir y que Calidad ya ofrece `missing_axes`.
- Comprobado que con `missing_axes` un eje `rules: false` manda todos los documentos a la IA (hasta el tope).
- Emitidos PLAN y AUDIT_PLAN en `PLAN.md`; veredicto GO_CONDICIONAL (D1, D2). Sin cambios de código.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | .ai/sessions/2026-11-22-ia-alcance-construir/PLAN.md | emitido |

## Directrices para Futuras IAs
- **[ia/alcance]**: `missing_axes` pregunta por cualquier eje de etiqueta vacío; un eje `rules: false` está siempre
  vacío tras las reglas, así que envía todos los documentos (hasta `budget_classify`/`ai_max_documents_per_run`).

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Revisión en el navegador (no hecha). CI del PR #101 en verde; publicado en la 2.1.0.
