# REQUEST

## Session metadata
- id: 2026-11-28-doc-organize-2.7.0
- fecha: 2026-11-28
- rama: develop
- skill: dependencia + new_feature (pendiente de planificar)
- fase solicitada: aviso de la librería; sin PLAN ni código todavía

## Solicitud original saneada
Aviso de doc_organize: la web sigue en doc_organize **2.5.0** y la librería publica **2.7.0** (PR fmanza/doc_organize#124),
con la **2.6.0** en medio. Este documento recoge qué tiene que adoptar la web al subir, para planificarlo como sesión
propia. Origen: análisis de precisión del contexto de la librería
(`doc_organize/.ai/sessions/2026-11-27-precision-contexto/`), su cierre de F0 (`CIERRE_F0.md`) y el PLAN de P3
(`doc_organize/.ai/sessions/2026-11-28-ia-sobre-todo/PLAN.md`).

## Lo que cambia en la librería y afecta a la web

### 2.7.0: la IA sobre todos los documentos (P3, W8 del análisis)

- **`ai_scope="all"`** (solo con plantilla o manifiesto; sin ellos, `ValueError`): la IA clasifica el dominio y el tipo
  de material de **todos** los documentos y **sustituye** lo que asignaron las reglas. Lo decidido por personas no se
  pregunta. Los ejes que solo etiquetan no se piden. Medido en la librería con qwen2.5:14b sobre 100 documentos de
  CALIDAD_VD: 0,53 en dominio y 0,78 en tipo, frente a 0,20 y 0,20 de las reglas (y 0,35 / 0,55 de asignar siempre
  el valor más frecuente).
- **`DomainDocument.rules_material_type`** y **`rules_material_type_confidence`**: lo que asignaron las reglas en el tipo
  de material, aunque después lo sustituyera la IA (como `rules_domain` en el dominio).
- **`AiPhaseStats.replaced`** (`context.ai_stats.classification.replaced`): ejes en que la IA puso un valor distinto del
  de las reglas.
- **Cola de revisión**: con `"all"` no se añade `rules_ai_disagreement` por discrepar de las reglas (serían casi todo el
  corpus). En la medición, 16 elementos para 100 documentos, todos `unverified_evidence`.
- **Coste**: una llamada por documento a la tarea `classify` (con un modelo local, del orden de 20 s por documento).
  Con un modelo externo, todo el corpus sale del equipo. La caché evita repetir llamadas al reconstruir sin cambios, y
  `ai_max_documents` / `budget_classify` siguen limitando: un tope bajo deja un contexto mixto (parte de la IA y parte
  de las reglas, con precisiones muy distintas).
- **Compatibilidad**: un `context.json` construido con `"all"` necesita 2.7.0 para leerse. La web no se rompe mientras
  no lo pida.
- **Puerta de `compare_classifications`**: `non_inferior` exige además el F1 macro y `improved` superar la línea base
  de mayoría; `AxisComparison` gana `macro_f1`, `majority_value`, `majority_accuracy` y `above_majority`, y
  `AxisEvaluation` gana `majority_value` y `majority_accuracy`. Afecta a la comparación de pruebas en seco
  (`CompareCard.tsx`).

### 2.6.0: medir la clasificación (W1, W5 del análisis)

- `UNCLASSIFIED_SLUG` en la API pública y `Domain.is_placeholder`; el dominio `sin-clasificar` nace en
  `DomainStatus.DRAFT` (antes `CONFIRMED` con catálogo): la web pasará a pintarlo como «Borrador». La etiqueta buena es
  «Por debajo del umbral» (W1).
- `review_queue` añade `unclassified` en el eje de subcarpeta cuando el de carpeta tiene valor.
- `evaluate_classification` da F1 por valor, matriz de confusión y exactitud por tramo de confianza;
  `compare_classifications` compara dos configuraciones de forma pareada (W5).

## Dónde toca en la web

| Qué | Dónde |
|---|---|
| Aceptar `"all"` al construir | `backend/app/domain/runs/operations.py:251` (`ContextBuildParams.ai_scope`) y su validador (`:263`: como `missing_axes`, solo con `template`/`manifest`) |
| Aceptar `"all"` en la prueba en seco | `backend/app/domain/runs/operations.py:318` (`ContextDryRunParams.ai_scope`) |
| Pasarlo a la librería | `backend/app/jobs/operations/context.py:357` (ya pasa `params.ai_scope` tal cual) |
| Ofrecerlo en la interfaz | `frontend/src/features/context/BuildCard.tsx` y `CompareCard.tsx` (selector «Qué se envía a la IA», sesión `2026-11-22-ia-alcance-construir`), con el aviso de coste y de privacidad, y el tiempo estimado |
| Mostrar `replaced` | Resultado de la construcción y tarjeta de la ejecución (`ai_stats`) |
| Mostrar la propuesta de las reglas por eje | Detalle del documento (`rules_domain`, `rules_material_type`) |
| Calidad | `backend/app/domain/context/quality.py:218` (`ai_scope != "off"`): revisar que `"all"` se trate como IA activa |
| Esquemas | `frontend/src/api/schema.d.ts` (regenerar), `backend/app/api/v1/schemas/context.py` (campos nuevos de `DomainDocument` y `AiPhaseStats`) |
| Dependencia | `backend/pyproject.toml` (wheel de la release v2.7.0, con hash; ADR-006) |

## Objetivo operativo de esta sesión
- Subir doc_organize de 2.5.0 a 2.7.0 y adoptar los cambios de 2.6.0 (W1) y 2.7.0 (`"all"`, `replaced`, puerta nueva).
- Ofrecer `ai_scope="all"` en «Construir» y en la prueba en seco, con aviso de coste y privacidad.

## Restricciones explícitas
- No es el valor por defecto: la librería no lo recomienda por defecto hasta medirlo en un segundo corpus (Revisión 18
  de su `DECISIONS_LOG.md`). En la web, opción explícita.
- Comprobar que no haya ejecuciones activas antes de reconstruir los contenedores.

## Resultado esperado
- Sesión con PLAN + AUDIT_PLAN antes de tocar código.
