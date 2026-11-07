# REQUEST

## Session metadata
- id: 2026-11-07-exclusiones
- fecha: 2026-11-07
- rama: develop
- skill: new_feature
- fase solicitada: PLAN + AUDIT_PLAN de dos mejoras de `docs/plan/MEJORAS.md`

## Solicitud original saneada
«Preparamos plan y audit_plan de estas dos últimas mejoras»: excluir subcarpetas de las carpetas de trabajo al
escanear (P2) y patrones de ruido por ubicación (P3). Decisiones del mantenedor durante la sesión:

- La exclusión es **por proyecto** (en cada carpeta guardada), no por ubicación.
- Con `force`, lo ya convertido de una subcarpeta excluida cuenta como eliminado.
- «En cualquier momento las exclusiones se pueden revertir».
- Punto 1 del AUDIT_PLAN aceptado: lo que encaja con un patrón de ubicación también cuenta como eliminado con `force`,
  y la vista previa lo avisa.

## Objetivo operativo de esta sesión
- PLAN y AUDIT_PLAN de las dos mejoras, con la parte de la librería (hueco G41) y la de la web.
- Dejar las decisiones anotadas en `docs/plan/MEJORAS.md`.

## Restricciones explícitas
- Solo planificación: sin IMPLEMENT.
- Sin cambios incompatibles en doc_organize (MINOR 1.3.0) ni en la API HTTP (aditiva).

## Resultado esperado
- `PLAN.md` y `TRACEABILITY.md` en esta carpeta; filas actualizadas en `MEJORAS.md`.
