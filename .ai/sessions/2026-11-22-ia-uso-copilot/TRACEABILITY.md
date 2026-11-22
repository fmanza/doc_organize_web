# TRACEABILITY

## Session metadata
- id: 2026-11-22-ia-uso-copilot
- fecha: 2026-11-22
- rama: feature/2.1 (web); develop (librería)
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE

## Prompt issued
sigue

(Tras «Acepto recomendaciones y sacar todo junto»: F1 y F2 en la misma versión que F3.)

## Context supplied
- Análisis inicial de la conversación (F0-F5) y sesión `2026-11-22-contexto-orden`
- Ficheros listados en `00_CONTEXT_SNAPSHOT.md`

## AI output summary
- Localizadas todas las referencias a Copilot en la web (backend, frontend, docs, OpenAPI) y la API pública de la
  librería que lo expone.
- Comprobado que los tokens ya están en `runs.result` de construir, agentes y evaluación, y que `taxonomy_draft` no
  los guarda aunque `draft_taxonomy` devuelve `LlmResult.usage`.
- Comprobado que `budget_<tarea>` es un tope de documentos, no de dinero, y que no hay coste por ejecución.
- Emitidos PLAN y AUDIT_PLAN; veredicto GO_CONDICIONAL (A2 y D1-D4).
- Decisiones: A2 sin cabecera de coste (L2 fuera), D1 obsoleto en 2.1, D2 día local del navegador, D3 relleno sí,
  D4 sin objeto.
- IMPLEMENT en la librería (L1) y en la web (W1-W5); ver `PLAN.md` § IMPLEMENT.
- AUDIT_CODE: C1 y C2 corregidos; C5 (revisión visual) y C6 (e2e) pendientes.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | .ai/sessions/2026-11-22-ia-uso-copilot/00_REQUEST.md | emitido |
| CONTEXT SNAPSHOT | .ai/sessions/2026-11-22-ia-uso-copilot/00_CONTEXT_SNAPSHOT.md | emitido |
| PLAN + AUDIT_PLAN | .ai/sessions/2026-11-22-ia-uso-copilot/PLAN.md | emitido (GO tras decisiones) |
| IMPLEMENT | backend/, frontend/, docs/, openapi/, CHANGELOG.md; librería en su sesión `2026-11-22-copilot-obsoleto` | completado, sin commit |
| AUDIT_CODE | PLAN.md § AUDIT_CODE | GO_CONDICIONAL (revisión visual y e2e) |

## Directrices para Futuras IAs
- **[ia/uso]**: los tokens por ejecución ya existen en `runs.result` (`phase_stats`, agentes, evaluación); no hace
  falta pedírselos a LiteLLM.
- **[ia/presupuesto]**: `budget_<tarea>` en la configuración es un máximo de **documentos** por construcción, no de
  dinero.
- **[ia/consumo]**: una operación con IA nueva debe dejar sus recuentos (y `model`) en su resultado y añadirse a
  `usage_log.rows_from_result`; la migración `0026` tiene su propia copia congelada y no se toca.
- **[ia/coste]**: el proxy del mantenedor no manda `x-litellm-response-cost`: no hay coste por llamada.
- **[ia/copilot]**: en la librería es API pública (`doc_organize.ai`, `doc_organize.core.models`): retirarlo es
  incompatible y va a 3.0.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- Revisión visual de IA › Uso (claro, oscuro, móvil) y e2e de `feature/2.1`.
- Commits, PR a `develop` y cierre de versión (web 2.1.0; doc_organize 2.1.0 por separado).
