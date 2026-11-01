---
name: phase-implementation
description: "Implementa una fase completa del ROADMAP (PLAN, AUDIT_PLAN, IMPLEMENT, AUDIT_CODE y VERSION) con su Definición de Hecho; veredicto GO, GO_CONDICIONAL o NO_GO."
disable-model-invocation: true
---
# Prompt: phase_implementation — Implementar una fase del ROADMAP

Implementa **una** fase de `docs/plan/ROADMAP.md` completa, con su Definición de Hecho (DoD común del ROADMAP).
Agentes: Plan Architect (PLAN + AUDIT_PLAN) → Feature Implementer (IMPLEMENT) → Code Auditor + Frontend Reviewer
(+ Security Reviewer si la fase toca autenticación, secretos, rutas del sistema de ficheros o mueve/borra ficheros)
(AUDIT_CODE) → Version Closer (VERSION).

## Inputs requeridos
- **Fase**: número (p. ej. `2`)
- **Alcance**: `completa` o lista de tareas/historias de la fase (`WB-*`, `WF-*`, `WD-*`)
- **Mejoras opcionales** de la fase a incluir: sí/no y cuáles
- **Restricciones**: dependencias nuevas permitidas, versión de doc_organize disponible, GPU/red disponibles para
  probar, plazos

Si falta alguno o la fase anterior no está cerrada en el ROADMAP, detente y aclara.

## Devuelve en este orden

### PLAN
- tareas e historias de usuario de la fase y DoD
- versión de doc_organize que exige la fase (columna «Requiere») y si está publicada; rodeos temporales con su `G<n>`
- contrato HTTP: endpoints, esquemas, códigos de error, eventos SSE
- modelo de datos y migración Alembic
- uso de doc_organize con **firmas verificadas** (o `PENDIENTE DE VERIFICAR`)
- rutas del sistema de ficheros afectadas y cómo pasan por el resolvedor de ubicaciones
- pantallas y componentes del frontend (y plantilla Jinja de la web integrada a la que sustituyen)
- riesgos (seguridad, concurrencia de SQLite, red, operaciones destructivas, memoria de Docling, tamaño de imagen)
- estrategia de pruebas

### AUDIT_PLAN
- contraste con `.ai/architecture.md`, reglas no negociables de SHARED y ADRs
- huecos de doc_organize nuevos (para `DOC_ORGANIZE_GAPS.md`)
- filas de `docs/plan/PARIDAD.md` que cubre la fase
- **Veredicto:** `GO | GO_CONDICIONAL | NO_GO`. Detente y espera aprobación.

### IMPLEMENT (backend → contrato → frontend)
- cambios por archivo, en orden: modelo/migración → dominio → integración doc_organize → jobs → router → tests →
  `scripts/export_openapi.py` → `npm run gen:api` → hooks → componentes → tests → docs de usuario

### AUDIT_CODE
- salida de los agentes auditores y resultado de todos los comandos de «Comandos de desarrollo»
- `docker compose build` + `docker compose up` + `/api/health` 200
- E2E de la fase (Playwright) si se ha podido ejecutar

### VERSION
- versión MINOR nueva (`0.<fase+1>.0` hasta la 1.0), CHANGELOG, ROADMAP con la fase marcada como cerrada
- `PARIDAD.md` y `DOC_ORGANIZE_GAPS.md` actualizados
- `TRACEABILITY.md` de la sesión con **Directrices para Futuras IAs**
- commit propuesto `feat(<área>): fase N — <resumen>`

## Reglas
- No adelantes historias de fases posteriores.
- Toda operación que mueva o borre ficheros: rol autorizado, ubicación `rw`, vista previa y confirmación.
- Solo documentos sintéticos en tests y E2E.
- Salidas largas de validación en `build/logs/`.
