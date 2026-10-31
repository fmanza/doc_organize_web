---
name: config-review
description: "Revisa la configuración IA (Claude Code y Copilot): duplicación, referencias huérfanas y coherencia entre commands, skills y agentes; veredicto GO, GO_CONDICIONAL o NO_GO."
disable-model-invocation: true
---
# Prompt: config_review — Revisión de la configuración IA

Revisa los ficheros de instrucciones IA de doc_organize_web (Claude Code + GitHub Copilot) y propone correcciones sin
duplicación. Agente: `.github/agents/config-reviewer.agent.md`.

## Inputs
- **Modo**: `auditoría` (solo ANÁLISIS → AUDIT_PLAN) o `completa`
- **Ficheros**: todos o una lista

## Ficheros a leer
- `.github/SHARED_INSTRUCTIONS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/AGENTS.md`
- `.github/instructions/*.instructions.md`, `.github/agents/*.agent.md`, `.github/skills/*/SKILL.md`
- `.claude/commands/*.md`, `.claude/settings.json`, `.ai/*.md`

## Devuelve en este orden
1. **ANÁLISIS** — tabla por categoría del agente con `fichero:línea`; `% duplicación`; referencias huérfanas.
2. **PLAN** — correcciones por fichero.
3. **AUDIT_PLAN** — riesgos; **veredicto** `GO | GO_CONDICIONAL | NO_GO`.
4. **IMPLEMENT** — solo con modo `completa` y aprobación.
5. **AUDIT_CODE** — rutas existentes, commands ↔ skills, hooks válidos, `% duplicación` final;
   veredicto `APROBADO | APROBADO CON CONDICIONES | RECHAZADO`.
6. **VERSION** — commit `docs(ia): …`, changelog, rollback.

## Criterios
- Estrategia vigente: SHARED + especializaciones (CLAUDE.md importa SHARED con `@`; Copilot lo referencia).
- Cero reglas comunes copiadas en entry points; cero referencias heredadas de util_bbdd_web o de la web integrada de
  doc_organize.
