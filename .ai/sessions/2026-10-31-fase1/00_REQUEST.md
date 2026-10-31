# REQUEST

## Session metadata
- id: 2026-10-31-fase1
- fecha: 2026-10-31
- rama: feature/fase-1 (desde develop, tras la 0.1.0)
- skill: phase
- fase solicitada: PLAN + AUDIT_PLAN de la Fase 1 (Identidad y multiusuario → 0.2.0)

## Solicitud original saneada
/phase — Fase: 1. Alcance: completa. Mejoras opcionales: no. Restricciones: sin dependencias nuevas salvo
pwdlib[argon2] (y react-hook-form, zod en el frontend, previstas en DEPENDENCIAS.md); doc_organize 0.9.3 sin cambios.

## Objetivo operativo de esta sesión
- PLAN y AUDIT_PLAN de WB-1.1, WB-1.2 y WF-1.1 contrastados con util_bbdd_web (fase 1, commit `b74eeb7`) y con la
  web integrada de doc_organize (paridad).
- Tras aprobación: IMPLEMENT, AUDIT_CODE (con Security Reviewer) y VERSION 0.2.0.

## Restricciones explícitas
- Dependencias nuevas: solo `pwdlib[argon2]`, `react-hook-form`, `zod`.
- doc_organize 0.9.3 sin cambios; la fase no usa su API.
- Detenerse tras AUDIT_PLAN.
