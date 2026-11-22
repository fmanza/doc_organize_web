# REQUEST

## Session metadata
- id: 2026-11-22-contexto-orden
- fecha: 2026-11-22
- rama: develop
- skill: new_feature
- fase solicitada: PLAN + AUDIT_PLAN (sin IMPLEMENT)

## Solicitud original saneada
«Mejorar las pantallas de CONTEXTO para que siga un orden lógico, luego AUDIT_PLAN.»

Viene del análisis previo de la misma conversación (plan por fases F0-F5), que pedía, sobre la pantalla Contexto:
- revisar si tienen sentido las cuatro formas de construir (Descubrir dominios, Catálogo propio, Plantilla, Manifiesto);
- «Perfil del proyecto» solo con la opción Plantilla;
- dónde poner un prompt de contexto del proyecto;
- «Reconstruir el contexto» solo si hay contexto (ya es así).

## Objetivo operativo de esta sesión
- Ordenar la pantalla Contexto y sus subpáginas (Revisión, Calidad, Sitio) en el orden de trabajo real:
  definir la taxonomía → construir → ver el resultado → revisar y medir → entregar.
- Ligar «Perfil del proyecto» a la elección del catálogo, sin ocultar nada que siga activo.
- No cambiar el contrato HTTP ni la librería.

## Restricciones explícitas
- Solo PLAN y AUDIT_PLAN; no se implementa.
- Fuera de alcance (otras fases del plan general): error del agente (F0), Copilot (F1), uso con tokens (F2),
  instrucciones únicas para todas las tareas y «Catálogo propio» como asistente (F3b), memoria IA (F4).

## Resultado esperado
- `PLAN.md` con PLAN y AUDIT_PLAN y su veredicto.
- `TRACEABILITY.md` y una fila en `.ai/sessions/INDEX.md`.
