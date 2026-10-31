# tech-debt

Deuda técnica priorizada.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/skills/tech-debt/SKILL.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Plan Architect (→ Feature Implementer → Code Auditor → Version Closer si se autoriza IMPLEMENT) (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input de la skill, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/tech-debt

Área: docker/
Síntomas: imagen runtime-gpu > 8 GB
Versión: 0.5.0 (develop)
Scope: solo análisis
Compatibilidad: sin romper la API HTTP
```
