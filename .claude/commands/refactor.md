# refactor

Refactor sin cambios funcionales.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/refactor.prompt.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Plan Architect → Feature Implementer → Code Auditor → Version Closer (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input del prompt, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/refactor

Objetivo: extraer la paginación común de los routers
Rutas: backend/app/api/v1/
Contrato HTTP: no cambia
Tests: tests/api/
```
