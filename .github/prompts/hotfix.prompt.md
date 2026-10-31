# Prompt: hotfix (aplicación web)

Corrección acotada de un bug P1/P2. Política: **solo fix mínimo; prohibido refactorizar y optimizar**.
Agentes: Hotfix Responder (PLAN → IMPLEMENT) → Code Auditor (AUDIT_CODE) → Version Closer (VERSION).

## Inputs requeridos
- **Bug**: qué no funciona
- **Dónde**: pantalla, endpoint, job u operación; archivos si se conocen
- **Síntomas**: logs JSON, `run.log`, respuesta *problem details*, estado de la ubicación, captura
- **Dato faltante o supuesto**: qué NO se sabe con seguridad

Si no puedes emitir un PLAN con diagnóstico de causa raíz claro, detente.

## Devuelve en este orden

### PLAN
- objetivo, rutas afectadas, dato faltante o supuesto, riesgos

### AUDIT_PLAN
- riesgos funcionales, técnicos y de seguridad; simplificaciones

### IMPLEMENT
- diagnóstico de causa raíz (RCA)
- implementación acotada
- test que reproduzca el fallo (pytest, Vitest o Playwright)

### AUDIT_CODE
- regresiones potenciales, edge cases, compatibilidad de la API HTTP y de las migraciones

### VERSION
- commit message (`hotfix(<área>): <descripción>`), changelog (1-2 líneas), rollback

## Reglas
- Si la causa está en doc_organize: rodeo en la capa anticorrupción + entrada en `docs/plan/DOC_ORGANIZE_GAPS.md`.
- Antes de cerrar, los comandos de `SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo» deben pasar.
