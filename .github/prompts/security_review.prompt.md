# Prompt: security_review (aplicación web)

Auditoría de seguridad independiente (OWASP ASVS nivel 2 como referencia). Hallazgos verificables por severidad.
Agente: Security Reviewer.

## Inputs requeridos
- **Áreas**: rutas o funcionalidades (p. ej. `backend/app/domain/locations/`, «descargas del workspace»)
- **Foco**: autenticación, autorización, secretos, rutas y ubicaciones, documentos no confiables, operaciones que
  mueven o borran ficheros, conexiones salientes IA, contenedor, dependencias o `todo`

Si falta alguno, decláralo como supuesto explícito.

## Devuelve en este orden

### PLAN
- alcance y archivos analizados

### AUDIT_PLAN
- hipótesis de riesgo priorizadas

### AUDIT_CODE
- hallazgos por severidad (`CRITICAL | HIGH | MEDIUM | LOW`) con `archivo:línea`
- escenario de explotación y remediación por hallazgo
- supuestos y datos faltantes etiquetados
- **Veredicto:** los `CRITICAL` bloquean el merge hasta su remediación verificada

### VERSION
- commit message si hay cambios (`security(<área>): <descripción>`)
- checklist de validación post-remediación

## Reglas
- Checklist mínima en `.github/agents/security-reviewer.agent.md`.
- No rebajes severidad sin justificarla.
