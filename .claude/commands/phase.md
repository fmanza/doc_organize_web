# phase

Implementa una fase completa de docs/plan/ROADMAP.md con su Definición de Hecho.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/phase_implementation.prompt.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Plan Architect (PLAN + AUDIT_PLAN) → Feature Implementer (IMPLEMENT) → Code Auditor + Frontend Reviewer (+ Security Reviewer si toca auth, secretos, rutas o mueve/borra ficheros) → Version Closer (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input del prompt, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/phase

Fase: 0
Alcance: completa
Mejoras opcionales: no
Restricciones: doc_organize 0.9.x como wheel local (G9); sin GPU en desarrollo
```
