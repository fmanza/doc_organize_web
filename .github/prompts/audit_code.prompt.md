# Prompt: audit_code (aplicación web)

Auditoría técnica con veredicto final. Modo lectura: no edita código. Agente: Code Auditor (y Frontend Reviewer si
el alcance incluye `frontend/`).

## Inputs requeridos
- **Archivos a revisar**: rutas o globs (p. ej. `backend/app/domain/locations/`, `frontend/src/features/scan/`)
- **Contexto**: qué cambió o por qué se audita
- **Foco**: bugs, seguridad, tipado, accesibilidad, tests o todo

Si no se especifican archivos, detente.

## Devuelve en este orden

### PLAN
- alcance y archivos analizados

### AUDIT_PLAN
- riesgos funcionales, técnicos y de seguridad

### AUDIT_CODE
- bugs potenciales (`archivo:línea`) y edge cases
- contrato HTTP: OpenAPI exportado = código; cliente regenerado; errores RFC 9457
- autorización por recurso (IDOR), secretos, rutas por el resolvedor de ubicaciones (traversal, enlaces simbólicos)
- concurrencia (SQLite, cola de jobs, una escritura por proyecto) y manejo de recursos (memoria, ficheros abiertos)
- escala: listados paginados en servidor, sin cargar colecciones completas
- tipado (`Any`, `any`), accesibilidad, rendimiento
- tests faltantes o insuficientes
- **Veredicto:** `APROBADO | APROBADO CON CONDICIONES | RECHAZADO`

### VERSION
- commit message si hay cambios derivados (`fix:` o `refactor:`) y pruebas sugeridas

## Reglas
- Evidencias por archivo y línea; diferencia hallazgos confirmados de hipótesis.
