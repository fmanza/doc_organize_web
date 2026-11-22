# REQUEST

## Session metadata
- id: 2026-11-22-ia-uso-copilot
- fecha: 2026-11-22
- rama: feature/2.1
- skill: new_feature
- fase solicitada: PLAN + AUDIT_PLAN de F1 y F2 (misma versión que 2026-11-22-contexto-orden)

## Solicitud original saneada
Del análisis inicial de la conversación:

- «El Uso de IA no solo debe mostrar cantidad y coste, sino también tokens usados; propón mejorar cómo se muestra la
  información.» (F2)
- «En configuración de la IA ya no es necesario el Uso de GitHub Copilot: todo se gestionará sobre LiteLLM. Quitarlo
  también del menú Uso.» (F1)

Decisión del mantenedor (2026-11-22): «sacar todo junto» → F1, F2 y F3 (contexto en pasos) en la web 2.1.0. Después:
«sigue».

## Objetivo operativo de esta sesión
- F1: quitar GitHub Copilot de la web (configuración, uso, estado, textos) y marcarlo como obsoleto en la librería.
- F2: registrar el consumo de IA de cada ejecución (tokens, documentos, caché, modelo, tarea, coste si el proxy lo da)
  y mostrarlo por periodo, tarea, modelo, proyecto y ejecución.

## Restricciones explícitas
- Una sola versión web 2.1.0 con F3 (ya implementado en `feature/2.1`).
- La librería sigue siendo pura: la web pide API nueva a la librería en vez de llamar ella a LiteLLM.
- Corregir, no borrar, los documentos históricos que mencionen Copilot (memoria del mantenedor).

## Resultado esperado
- `PLAN.md` con PLAN y AUDIT_PLAN y su veredicto; `TRACEABILITY.md`; fila en `INDEX.md`.
