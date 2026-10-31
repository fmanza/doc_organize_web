# Prompt: refactor (aplicación web)

Refactor sin cambios funcionales. Contrato HTTP estable salvo justificación explícita.
Agentes: Plan Architect (PLAN + AUDIT_PLAN) → Feature Implementer (IMPLEMENT) → Code Auditor (AUDIT_CODE) →
Version Closer (VERSION).

## Inputs requeridos
- **Objetivo**: qué se mejora (SRP, duplicación, nombres, rendimiento del bundle…)
- **Rutas afectadas**
- **Contrato HTTP**: ¿cambia? (NO, salvo justificación; si cambia, OpenAPI y cliente regenerados)
- **Tests existentes** que validan la ausencia de regresión

## Devuelve en este orden

### PLAN
- objetivo, rutas, componentes, riesgos de regresión

### AUDIT_PLAN
- riesgos funcionales, técnicos y de seguridad; simplificaciones
- **Veredicto:** `GO | GO_CONDICIONAL | NO_GO`

### IMPLEMENT
- cambios por archivo y explicación breve

### AUDIT_CODE
- regresiones, contrato HTTP intacto (`scripts/export_openapi.py --check`), cobertura preservada, tipado

### VERSION
- commit message (`refactor(<área>): <descripción>`), changelog, impacto en la API (cero sin justificación), rollback

## Reglas
- No introducir cambios funcionales.
- La capa anticorrupción sigue siendo el único punto que importa doc_organize y el resolvedor de ubicaciones el único
  que convierte rutas de usuario en rutas del sistema de ficheros.
