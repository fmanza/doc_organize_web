# version-closure

Cierre de versión, fase o sesión.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/skills/version-closure/SKILL.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Version Closer (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input de la skill, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/version-closure

Cambios: Fase 0 — fundaciones
Versión: v0.1.0
Fase: 0
Sesión: .ai/sessions/2026-10-31-fase0/
```
