# audit-code

Auditoría técnica, solo lectura.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/skills/audit-code/SKILL.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Code Auditor (+ Frontend Reviewer si incluye frontend/) (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input de la skill, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/audit-code

Archivos: backend/app/domain/locations/, frontend/src/features/locations/
Contexto: cierre de la Fase 2
Foco: todo
```
