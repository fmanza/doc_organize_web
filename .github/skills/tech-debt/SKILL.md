---
name: tech-debt
description: "Inventario priorizado de deuda técnica de un área, sin mezclar con funcionalidades; veredicto LIMPIO, DEUDA_MENOR, DEUDA_SIGNIFICATIVA o CRÍTICO."
disable-model-invocation: true
---
# Prompt: tech_debt (aplicación web)

Inventario de deuda técnica. No mezclar con nuevas features en el mismo PLAN.
Agentes: Plan Architect (análisis); si se autoriza IMPLEMENT, Feature Implementer → Code Auditor → Version Closer.

## Inputs requeridos
- **Área objetivo** (p. ej. `backend/app/jobs/`, `frontend/src/features/runs/`, `docker/`)
- **Deuda conocida o síntomas**
- **Versión actual** y rama
- **Scope**: solo análisis o también IMPLEMENT
- **Política de compatibilidad**: ¿se autoriza romper el contrato HTTP?

## Devuelve en este orden
1. PLAN — área, síntomas, scope, riesgos de regresión
2. AUDIT_PLAN — riesgos y dependencias entre ítems
3. AUDIT_CODE — deuda por archivo, impacto, prioridad (`quick_win | fase_media | deuda_estructural`), plan por fases
4. VERSION (solo si se autorizó IMPLEMENT) — commit `refactor:` y pruebas

## Reglas
- Veredicto final: `LIMPIO | DEUDA_MENOR | DEUDA_SIGNIFICATIVA | CRÍTICO`.
- Evidencias concretas; diferencia hallazgos de hipótesis.
- Incluye la deuda de dependencias (versiones fijadas desactualizadas, avisos de seguridad, tamaño de las imágenes)
  y los rodeos temporales de `DOC_ORGANIZE_GAPS.md` que ya pueden retirarse con la versión publicada de doc_organize.
