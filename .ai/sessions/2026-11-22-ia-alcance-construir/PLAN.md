# PLAN + AUDIT_PLAN — Qué envía a la IA al construir el contexto (2026-11-22)

Skill: `new-feature` (web). Solo PLAN y AUDIT_PLAN; sin implementar.

## Solicitud

Al adaptar un prompt de normalización de un SGI a un manifiesto (5 ejes, uno de ellos «Acción de migración» con
`rules: false`, que solo puede rellenar la IA), se vio que la web solo pide a la IA lo que las reglas no colocan en
carpeta. Los ejes que solo etiquetan quedan vacíos en los documentos que las reglas sí clasifican. El mantenedor pidió
planificar un selector en el paso «Construir» («sí», 2026-11-22).

## Contexto: cómo está hoy

| Dónde | Qué hace |
|---|---|
| doc_organize 2.0.1 `ContextBuilder.build(ai_scope=…)` | `off`, `unclassified` (dominio o tipo sin clasificar) o `missing_axes` (además, cualquier eje que solo etiqueta y esté **vacío**, también los de `rules: false`). La IA solo rellena lo vacío: nunca cambia lo que decidieron las reglas ni una persona |
| Web `ContextBuildParams` | Solo `ai_classification: bool` |
| Web `jobs/operations/context.py:341` | `ai_scope="unclassified" if params.ai_classification else "off"`: `missing_axes` no se puede pedir |
| Web Calidad, prueba de clasificación (`ContextDryRunParams.ai_scope`) | Ya ofrece los tres valores, con los textos `quality.scopes.*` |
| Resultado del run | `ai.scope` ya sale en `classification_stats` |
| Tope de documentos | `budget_classify` de la tarea o `ai_max_documents_per_run` (500 por defecto): la librería no manda más |

Con `missing_axes` y un eje `rules: false`, ese eje está vacío en **todos** los documentos tras las reglas, así que
todos van a la IA, hasta el tope. Hay que decirlo en la pantalla.

## Inputs

| Campo | Valor |
|---|---|
| Objetivo | Elegir en «Construir» qué se envía a la IA al clasificar: «Lo que las reglas no clasifican» (hoy) o «También los ejes vacíos» (`missing_axes`) |
| Rutas | Backend: `domain/runs/operations.py` (`ContextBuildParams.ai_scope`, validación), `jobs/operations/context.py` (pasarlo), `domain/context/service.py` si guarda o audita los parámetros; tests `tests/api/test_context.py`, `tests/jobs/test_ai_operation.py`. Frontend: `features/context/ContextPage.tsx` (`BuildCard`), `useContext.ts` (`buildParams`), `features/runs/RunResult.tsx` (alcance en el resultado), `i18n/es/features.json`; tests `features/context/ai.test.tsx`. Docs: `docs/guides/contexto.md`, `docs/guides/ia.md`, `CHANGELOG.md`; `openapi/` y `schema.d.ts` regenerados |
| Contrato HTTP | `POST /projects/{id}/runs` con `context_build`: campo nuevo opcional `ai_scope: "unclassified" \| "missing_axes"` (por defecto `unclassified`). Solo cuenta con `ai_classification: true`. 422 si es `missing_axes` con un catálogo sin ejes de etiqueta (`discover`, `domains`) |
| Pantallas | Paso «Construir»: bajo «Clasificar con IA», visible solo con el interruptor activo y catálogo Plantilla o Manifiesto |
| Permisos | Los de construir (editor con destino rw) |
| doc_organize | `ContextBuilder.build(ai_scope="missing_axes")` (2.0.1, ya usado por la prueba de clasificación) |
| Restricciones | Sin migraciones ni dependencias. Aditivo: los clientes que no lo mandan siguen igual |

## PLAN

### 1. Backend

- `ContextBuildParams.ai_scope: Literal["unclassified", "missing_axes"] = "unclassified"`, documentado.
- Validador: `missing_axes` solo con `catalog in {"template", "manifest"}` (con `discover` o `domains` no hay ejes de
  etiqueta y daría lo mismo que `unclassified`: mejor un 422 claro que una opción que no hace nada). Con
  `ai_classification: false` se ignora (no da error: «Relanzar» con parámetros antiguos sigue valiendo).
- `jobs/operations/context.py`: `ai_scope=params.ai_scope if params.ai_classification else "off"`.
- El resultado ya lleva `ai.scope`; el log del job añade «también los ejes vacíos» cuando toca.
- Nada cambia en `ProjectContext` (ya guarda `ai_classification` y el modelo; el alcance queda en el run).

### 2. Frontend

- `BuildCard`: con «Clasificar con IA» activo y catálogo Plantilla o Manifiesto, un `SegmentedControl` «Qué se envía a
  la IA» con los textos que ya usa Calidad (`quality.scopes.unclassified`, `quality.scopes.missing_axes`; se mueven a
  una clave común `context.ai.scopes.*` para no depender de Calidad).
- Ayuda bajo el selector, con `missing_axes`: «Van también los documentos con algún eje de etiqueta vacío. Los ejes sin
  reglas (`rules: false`) siempre están vacíos tras las reglas: con ellos van todos los documentos, hasta el máximo de
  documentos de clasificar por ejecución.»
- La elección vive en `BuildCard` (como el resto de opciones). Si se cambia a un catálogo sin ejes de etiqueta, vuelve a
  `unclassified` y el selector se oculta.
- `RunResult`: «Alcance de la IA» con el texto del valor de `ai.scope`.

### 3. Tests

- API: `missing_axes` con `discover` → 422; con `manifest` → 202 y el parámetro guardado; sin el campo → `unclassified`.
- Job: con un manifiesto con un eje `rules: false` y `missing_axes`, la IA rellena ese eje en documentos que las reglas
  ya habían colocado en carpeta; con `unclassified`, no (LiteLLM falso).
- Frontend: el selector solo aparece con IA activa y Plantilla o Manifiesto; manda `ai_scope`; se oculta y vuelve a
  `unclassified` al cambiar a «Por carpetas».

### 4. Docs

- `docs/guides/contexto.md` (paso Construir) y `docs/guides/ia.md` (Clasificar con IA): qué hace cada opción y el aviso
  de los ejes `rules: false`.
- CHANGELOG `[Unreleased]` → `Added`.

---

## AUDIT_PLAN

### Riesgos

| Id | Riesgo | Severidad | Corrección |
|---|---|---|---|
| A1 | **Coste**: con un eje `rules: false`, todos los documentos van a la IA | Alta | Ayuda explícita en el selector; el tope de documentos sigue aplicando; IA › Uso lo refleja después |
| A2 | Un manifiesto sin ejes de etiqueta hace que `missing_axes` equivalga a `unclassified` | Baja | Se ofrece igual con Plantilla o Manifiesto (comprobar los ejes en el cliente exigiría parsear el manifiesto); la ayuda lo dice |
| A3 | «Relanzar» una construcción antigua sin el campo | Baja | Valor por defecto `unclassified`: mismo comportamiento que hoy |
| A4 | El tope por documentos corta a mitad y deja ejes vacíos sin avisar | Media | El resultado ya lleva `stopped`/`calls`; el log del job dice cuántos quedaron fuera si se alcanza el tope (si la librería lo informa; si no, se indica el tope usado) |
| A5 | La IA podría cambiar lo decidido | — | No aplica: la librería solo rellena ejes vacíos y respeta las decisiones de personas (F6) |
| A6 | Los textos de Calidad se reutilizan y luego divergen | Baja | Clave común `context.ai.scopes.*` usada por las dos pantallas |

### Seguridad

Más contenido sale hacia el proxy de IA con `missing_axes` (más documentos), pero por la misma vía, con la misma
redacción de credenciales y el mismo aviso de «El contenido sale de la aplicación». Sin cambios de permisos.

### Simplificaciones

- S1: un campo nuevo y aditivo en lugar de sustituir `ai_classification` por un `ai_scope` de tres valores, para no
  romper los parámetros guardados ni «Relanzar».
- S2: no guardar el alcance en `ProjectContext`: queda en el run y en su resultado.

### Decisiones

| Id | Decisión | Recomendación |
|---|---|---|
| D1 | ¿Va en la web 2.1.0 (rama `feature/2.1`, PR #101 aún abierto) o en una 2.1.1/2.2? | **En la 2.1.0**: es pequeño, no tiene migraciones y completa el caso del manifiesto de SGI |
| D2 | Valor por defecto del selector cuando el manifiesto tiene ejes `rules: false` | **«Lo que las reglas no clasifican»** siempre, para no disparar el coste sin querer |

### Veredicto

**GO_CONDICIONAL**: D1 y D2 decididas por el mantenedor.

### Decisiones del mantenedor (2026-11-22)

D1: en la web 2.1.0 (`feature/2.1`). D2: por defecto «Lo que las reglas no clasifican». Veredicto: **GO**.

---

## IMPLEMENT (2026-11-22)

| Fichero | Cambio |
|---|---|
| `backend/app/domain/runs/operations.py` | `ContextBuildParams.ai_scope` (`unclassified` por defecto) y validación con el catálogo |
| `backend/app/jobs/operations/context.py` | Pasa el alcance a la librería; el log dice qué se envió |
| `backend/app/jobs/operations/ai.py`, `domain/ai/usage_log.py` | El borrador guarda `ai_cached` en lugar de `cached` (que en los resultados ya es «documentos en la caché» del escaneo) |
| `frontend/.../ContextPage.tsx` (`BuildCard`), `useContext.ts` | Selector «Qué se envía a la IA» con ayuda; solo con IA activa y Plantilla o Manifiesto |
| `frontend/.../RunResult.tsx`, i18n | Alcance traducido y nombres de los datos de IA del resultado (modelo, caché, tokens) |
| Tests | `tests/jobs/test_ai_operation.py` (eje `rules: false` con y sin `missing_axes`; 422 con «Por carpetas»), `context/ai.test.tsx` |
| Docs | `docs/guides/ia.md`, `docs/guides/contexto.md`, `CHANGELOG.md`; OpenAPI y `schema.d.ts` |

Desviación: A6 (textos comunes) se resolvió dejando iguales los textos de Calidad y los nuevos `context.ai.scopes.*`;
Calidad conserva su clave porque además tiene «Sin IA».

## AUDIT_CODE (2026-11-22)

Comprobado: backend `ruff`, `mypy`, `export_openapi.py --check`, tests de IA, consumo y contexto (55 passed);
frontend `prettier`, `tsc -b`, `eslint`, `vitest` (172); `zensical build --strict`.

Sin hallazgos nuevos. Pendiente: e2e en CI y revisión en el navegador (como el resto de la 2.1).

Veredicto: **GO** (sujeto al CI).
