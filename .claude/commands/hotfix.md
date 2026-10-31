# hotfix

Bug P1/P2: RCA y fix mínimo, sin refactorizar.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/skills/hotfix/SKILL.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Hotfix Responder → Code Auditor → Version Closer (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input de la skill, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/hotfix

Bug: el escaneo de una ubicación de red falla entero tras un corte
Dónde: operación scan (backend/app/jobs/operations/)
Síntomas: run.log con exc_type=OSError errno=ESTALE
Supuesto: el reintento no cubre ESTALE
```
