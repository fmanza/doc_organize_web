# Agentes, prompts y slash commands

Registro de la configuración IA de doc_organize_web. Flujo: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

## Invocación

- **Claude Code**: `/phase`, `/new-feature`, `/hotfix`, `/refactor`, `/audit-code`, `/security-review`, `/tech-debt`,
  `/config-review`, `/version-closure` (`.claude/commands/`).
- **GitHub Copilot Chat**: agente por nombre (`.github/agents/`) + prompt (`.github/prompts/`).

## Agentes (`.github/agents/`)

| Agente | Fase | Herramientas | Propósito |
|---|---|---|---|
| Workflow Director | clasificación | read, search | Elegir flujo y siguiente paso |
| Plan Architect | PLAN, AUDIT_PLAN | read, search | Plan contrastado con el código y con doc_organize |
| Feature Implementer | IMPLEMENT | read, edit, search, execute | Cambios acotados con tests y contrato regenerado |
| Hotfix Responder | PLAN → IMPLEMENT | read, edit, search, execute | RCA y fix mínimo |
| Code Auditor | AUDIT_CODE | read, search | Hallazgos técnicos verificables |
| Frontend Reviewer | AUDIT_CODE | read, search | Accesibilidad, UX de estados, rendimiento, i18n |
| Security Reviewer | AUDIT_CODE | read, search | OWASP ASVS / Top 10, rutas y ubicaciones, secretos, contenedor |
| Version Closer | VERSION | read, edit, search | CHANGELOG, TRACEABILITY, PARIDAD, handoff |
| Documentation Generator | documentación | read, edit, search | Docs funcionales, técnicas y ADRs |
| Config Reviewer | configuración IA | read, search | DRY y referencias huérfanas |
| Explore | apoyo | read, search | Localizar código (solo lectura) |

## Prompts (`.github/prompts/`) y slash commands

| Prompt | Slash command | Agentes |
|---|---|---|
| `phase_implementation` | `/phase` | Plan Architect → Feature Implementer → Code Auditor + Frontend Reviewer (+ Security Reviewer) → Version Closer |
| `new_feature` | `/new-feature` | Plan Architect → Feature Implementer → Code Auditor → Version Closer |
| `hotfix` | `/hotfix` | Hotfix Responder → Code Auditor → Version Closer |
| `refactor` | `/refactor` | Plan Architect → Feature Implementer → Code Auditor → Version Closer |
| `audit_code` | `/audit-code` | Code Auditor (+ Frontend Reviewer) |
| `security_review` | `/security-review` | Security Reviewer |
| `tech_debt` | `/tech-debt` | Plan Architect (→ IMPLEMENT si se autoriza) |
| `config_review` | `/config-review` | Config Reviewer |
| `version_closure` | `/version-closure` | Version Closer |

Documentation Generator, Explore y Workflow Director no tienen slash command: se invocan por lenguaje natural
(Claude Code) o por nombre (Copilot Chat).

## Origen

Configuración derivada de la de [util_bbdd_web](https://github.com/fmanza/util_bbdd_web) 1.10.1 y adaptada según
[`docs/plan/INSTRUCCIONES_IA.md`](../docs/plan/INSTRUCCIONES_IA.md) (tarea WD-0.3): reglas de ubicaciones y rutas
(`filesystem.instructions.md`), colas cpu/gpu (`jobs.instructions.md`), operaciones que mueven o borran ficheros en
lugar de escritura en BD destino, y doc_organize como librería consumida.

---

*Actualizado: 2026-10-31*
