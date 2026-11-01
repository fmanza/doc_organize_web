# security-review

Auditoría de seguridad, solo lectura. Los CRITICAL bloquean el merge.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/skills/security-review/SKILL.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Security Reviewer (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input de la skill, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/security-review

Áreas: resolución de rutas y explorador de carpetas; descargas del workspace
Foco: todo
```
