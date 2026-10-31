# Instrucciones para Claude Code — doc_organize_web

Especialización para Claude Code: slash commands, hooks y configuración. La base común se importa aquí:

@.github/SHARED_INSTRUCTIONS.md

---

## Slash commands

Cada command es un envoltorio fino de su prompt en `.github/prompts/`, que es el **contrato de salida**. Si la tabla
y un prompt discrepan, manda el prompt.

| Comando | Propósito | Prompt | Veredicto |
|---|---|---|---|
| [`/phase`](./.claude/commands/phase.md) | Implementar una fase del ROADMAP | `phase_implementation` | `GO \| GO_CONDICIONAL \| NO_GO` |
| [`/new-feature`](./.claude/commands/new-feature.md) | Funcionalidad fuera de fase | `new_feature` | `GO \| GO_CONDICIONAL \| NO_GO` |
| [`/hotfix`](./.claude/commands/hotfix.md) | Bug P1/P2, fix mínimo | `hotfix` | — |
| [`/refactor`](./.claude/commands/refactor.md) | Refactor sin cambio funcional | `refactor` | `GO \| GO_CONDICIONAL \| NO_GO` |
| [`/audit-code`](./.claude/commands/audit-code.md) | Auditoría técnica (solo lectura) | `audit_code` | `APROBADO \| APROBADO CON CONDICIONES \| RECHAZADO` |
| [`/security-review`](./.claude/commands/security-review.md) | Auditoría de seguridad (solo lectura) | `security_review` | `CRITICAL` bloquea el merge |
| [`/tech-debt`](./.claude/commands/tech-debt.md) | Deuda técnica priorizada | `tech_debt` | `LIMPIO \| DEUDA_MENOR \| DEUDA_SIGNIFICATIVA \| CRÍTICO` |
| [`/config-review`](./.claude/commands/config-review.md) | Configuración IA | `config_review` | `GO \| GO_CONDICIONAL \| NO_GO` |
| [`/version-closure`](./.claude/commands/version-closure.md) | Cierre de versión, fase o sesión | `version_closure` | — |

Ejemplo:

```text
/phase

Fase: 0
Alcance: completa
Mejoras opcionales: no
Restricciones: doc_organize 0.9.x como wheel local (G9); sin GPU en desarrollo
```

---

## Hooks

`.claude/settings.json` (versionado) solo contiene hooks PostToolUse informativos tras `Edit`/`Write`: ruff y mypy del
backend (si existe `backend/` y hay `uv` local) y lint + typecheck del frontend (si existe `frontend/node_modules`).
No ejecutan la suite: antes de cerrar IMPLEMENT ejecuta tú los «Comandos de desarrollo» de SHARED. Permisos y ajustes
personales van a `.claude/settings.local.json` (git-ignored). Detalle: [`.claude/README.md`](./.claude/README.md).

---

*Actualizado: 2026-10-31*
