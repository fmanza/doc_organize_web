# REQUEST

## Session metadata
- id: 2026-11-16-doc-organize-1.5.0
- fecha: 2026-11-16
- rama: develop (las ramas de trabajo saldrán de aquí)
- skill: new_feature
- fase solicitada: PLAN y AUDIT_PLAN; sin IMPLEMENT

## Solicitud original saneada
Plan y audit_plan para actualizar doc_organize_web con lo incluido en la versión 1.5.0 de doc_organize.

## Objetivo operativo de esta sesión
- Inventariar qué trae doc_organize 1.5.0 y qué cambia en la web solo por subir el pin.
- Proponer por fases cómo adoptar cada novedad (backend, API, frontend, migraciones, pruebas).
- Señalar riesgos y decisiones que dependen del usuario antes de implementar.

## Restricciones explícitas
- Solo planificación: no se toca código ni dependencias en esta sesión.
- doc_organize solo se usa desde la capa anticorrupción `backend/app/integrations/doc_organize/` (ADR-006).

## Resultado esperado
- `PLAN.md` con PLAN y AUDIT_PLAN en esta carpeta.
