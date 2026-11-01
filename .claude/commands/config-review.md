# config-review

Revisión de la configuración IA (DRY, huérfanos, coherencia Claude/Copilot).

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/skills/config-review/SKILL.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Config Reviewer (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input de la skill, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/config-review

Modo: auditoría
Ficheros: todos
```
