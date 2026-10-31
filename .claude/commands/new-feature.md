# new-feature

Nueva funcionalidad. Política: **prohibido refactorizar**.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/new_feature.prompt.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Plan Architect → Feature Implementer → Code Auditor → Version Closer (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input del prompt, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/new-feature

Objetivo: botón «Relanzar» en el detalle de una ejecución
Rutas: backend/app/api/v1/runs.py, frontend/src/features/runs/RunDetail.tsx
Contrato HTTP: POST /api/v1/runs/{run_id}/rerun -> 202 Run
Pantallas: detalle de ejecución; deshabilitado sin permiso editor
Permisos: editor u owner del proyecto
doc_organize: ninguno nuevo
Restricciones: sin dependencias nuevas; sin migración
```
