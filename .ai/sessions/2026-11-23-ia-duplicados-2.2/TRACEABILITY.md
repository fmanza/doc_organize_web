# TRACEABILITY

## Session metadata
- id: 2026-11-23-ia-duplicados-2.2
- fecha: 2026-11-22 / 2026-11-23
- rama: fix/2.1.1-ubicaciones-entregar-menu (#104) y feat/2.2.0-ia-duplicados-contenido (#105)
- skill: hotfix (2.1.1) + new_feature (2.2.0)
- fase: PLAN + AUDIT_PLAN (en la conversación, sin fichero) + IMPLEMENT + AUDIT_CODE

## Prompt issued
- IA en la búsqueda de duplicados (contenido, `bge-m3`) con configuración de IA propia; IA › Configuración más usable;
  mensajes de prueba de modelo flotantes que digan qué modelo se probó; IA › Parámetros con la funcionalidad que usa
  cada ajuste.
- Incidencias: borrar una ubicación «No disponible» decía «La ubicación ya existe» + «Hay proyectos que usan esta
  ubicación» sin decir cuáles; desde «6. Entregar» → «Ver el sitio» no se podía volver; menú Proyecto (no se podía
  volver a la lista con un proyecto abierto y tras borrarlo quedaban sus secciones).
- Decisiones del mantenedor: tres entregas (web 2.1.1 → librería 2.2.0 → web 2.2.0); la búsqueda por contenido es la
  misma antes y después de convertir y lo convertido se mueve, nunca se borra; C1 = mensaje claro en 2.1.1 y opción
  (a) (FK de la ubicación a NULL en proyectos borrados) para más adelante.

## Context supplied
- `deteccion_duplicados_local.md`; sesión de la librería `doc_organize/.ai/sessions/2026-11-23-dedup-contenido`.

## AI output summary
- **2.1.1 (#104)**: `LocationInUseError` (`409`, `code: location_in_use`) que nombra los proyectos activos;
  `GET /api/v1/locations/{id}/usage` y aviso en el modal de borrado; «Volver a 6. Entregar» en el visor del sitio;
  bloque «Proyecto abierto» en el menú (desaparece si el proyecto no existe o está borrado); la ejecución de un borrado
  vuelve a «Proyectos». E2E `hardening.spec.ts` adaptado al bloque nuevo.
- **2.2.0 (#105)**: tarea `dedup` con modelo propio (`OWN_MODEL_TASKS`, `require_task`); prueba de modelo con `model`,
  `served_model` y `dimension`, límite de una prueba cada 10 s por modelo; IA › Configuración rediseñada («Conexión
  con LiteLLM», tabla «Modelos por funcionalidad» con panel lateral, «Probar todos los modelos», avisos flotantes
  `ToastStack`); IA › Parámetros con «Se usa en». Duplicados: «Mismo contenido» y «Contenido parecido (IA)» con
  umbral, similitudes y «contenido en», «Ver diferencias», y las conversiones se mueven con el descartado. Migración
  `0027` (columnas de similitud). Primero contra la rama de la librería (G45) y después con el wheel v2.2.0.
- E2E `ai.spec.ts` y `w9-ia.spec.ts` adaptados a la pantalla nueva.
- Al traer `develop` (#104) a #105 solo chocó `CHANGELOG.md`; `openapi.json` y `schema.d.ts` se comprobaron
  regenerándolos.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Hotfix 2.1.1 | PR #104 (`d131119`) | fusionado |
| Feature 2.2.0 | PR #105 (`191c74e`) | fusionado |

## Directrices para Futuras IAs
- **[e2e]**: al cambiar el menú o una pantalla, buscar sus textos también en `frontend/e2e/` (solo se ejecutan en el
  job `image` del CI, no con `vitest`).
- **[tests/windows]**: `tests/jobs/test_worker.py::test_swapped_output_folder_is_not_touched` falla en Windows sin
  permiso de enlaces simbólicos (`WinError 1314`); en el CI (Linux) pasa.
- **[ia/dedup]**: «Contenido parecido» solo se ofrece si la tarea `dedup` tiene modelo propio; no hereda el de
  `embed`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Opción (a) de C1: poner a NULL la ubicación de los proyectos borrados para poder borrar la ubicación (migración y
  revisar sus usos).
- Calibrar el umbral 0,90 y el tamaño de bloque con `bge-m3` real.
- Revisión visual en el navegador de IA › Configuración y Duplicados (claro, oscuro, móvil): no se hizo.
