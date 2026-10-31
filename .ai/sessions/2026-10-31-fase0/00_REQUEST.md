# REQUEST

## Session metadata
- id: 2026-10-31-fase0
- fecha: 2026-10-31
- rama: chore/config-ia (base develop)
- skill: phase
- fase solicitada: PLAN + AUDIT_PLAN de la Fase 0 (Fundaciones → 0.1.0)

## Solicitud original saneada
/phase — Fase: 0. Alcance: completa. Mejoras opcionales: no. Restricciones: doc_organize 0.9.x como wheel local
mientras no haya release publicada (G9); sin GPU en desarrollo.

## Objetivo operativo de esta sesión
- PLAN y AUDIT_PLAN de WB-0.1…0.6, WF-0.1…0.3 y WD-0.1…0.5 con firmas y versiones verificadas.
- Tras aprobación: IMPLEMENT, AUDIT_CODE y VERSION 0.1.0.

## Restricciones explícitas
- doc_organize 0.9.x vendorizado como wheel local (sin release con wheel en GitHub).
- Sin GPU en desarrollo; variantes GPU/LibreOffice/AV fuera de la Fase 0.
- Detenerse tras AUDIT_PLAN hasta aprobación.

## Resultado esperado
Monorepo con backend, frontend, Docker, CI, docs Zensical, ADR-001…006 y PARIDAD.md; `/api/health` 200 en la imagen.
