# Prompt: new_feature (aplicación web)

Nueva funcionalidad fuera del ROADMAP o dentro de una fase ya cerrada. Política: **prohibido refactorizar** código no
relacionado. Para implementar una fase completa usa `phase_implementation.prompt.md`.
Agentes: Plan Architect (PLAN + AUDIT_PLAN) → Feature Implementer (IMPLEMENT) → Code Auditor (AUDIT_CODE) →
Version Closer (VERSION).

## Inputs requeridos
- **Objetivo**: qué se implementa (1-2 líneas)
- **Rutas**: archivos de `backend/` y `frontend/`; marca `(nuevo)` los que no existen
- **Contrato HTTP**: endpoints, métodos, esquemas de entrada y salida, errores
- **Pantallas**: dónde aparece en la UI y estados (carga, vacío, error, sin permiso)
- **Permisos**: qué rol o pertenencia a proyecto se exige
- **doc_organize**: puntos de entrada usados (firma verificada)
- **Restricciones técnicas**: dependencias nuevas, migraciones, ubicaciones o colas (cpu/gpu) afectadas

Si falta alguno, detente y aclara antes de emitir PLAN.

## Devuelve en este orden

### PLAN
- objetivo, rutas afectadas, contrato HTTP, modelo de datos, riesgos

### AUDIT_PLAN
- riesgos funcionales, técnicos y de seguridad; simplificaciones
- **Veredicto:** `GO | GO_CONDICIONAL | NO_GO`

### IMPLEMENT (backend → contrato → frontend)
- cambios por archivo con explicación breve

### AUDIT_CODE
- bugs (`archivo:línea`), edge cases, autorización, rutas, seguridad, tipado, accesibilidad, tests

### VERSION
- commit message (`feat(<área>): <descripción>`), changelog, impacto en la API HTTP, rollback, pruebas sugeridas

## Reglas
- Antes de cerrar IMPLEMENT, los comandos de `SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo» deben pasar.
- Cambios en la API HTTP: OpenAPI exportado y cliente regenerado en el mismo cambio.
