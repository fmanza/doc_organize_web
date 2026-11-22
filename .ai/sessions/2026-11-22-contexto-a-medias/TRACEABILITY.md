# TRACEABILITY

## Session metadata
- id: 2026-11-22-contexto-a-medias
- fecha: 2026-11-22
- rama: feature/2.1
- skill: new_feature (corrección acotada; PLAN y AUDIT_PLAN abreviados aquí por tamaño)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE

## Prompt issued
«Antes se permitía borrar en contexto toda una ejecución, ¿ahora dónde está o cómo funciona Construir, elimina lo
creado?» → «Hacemos el hueco, el lanzamiento será con el nuevo contexto».

## Context supplied
- Construcción `48b25741` del proyecto CALIDAD_VD interrumpida al reconstruir el contenedor (11:27): doc_organize había
  escrito `context.json`, `domains/`, `organizado/` (9.676 entradas) y parte de `site/`; la web no guardó el contexto.
- `jobs/operations/context.py` (`_existing_folder`: construir y borrar ya leen la carpeta de `context.json`).

## AI output summary
- PLAN: el hueco es solo de detección y pantalla. `GET /projects/{id}/context/leftover` (`leftover_folder`: sin
  contexto guardado, la carpeta de `context.json` del destino, con el plazo de sondeo de la ubicación); aviso en la
  página con «Ir a Construir» y «Borrar contexto»; «Construir» dice que reutiliza esa carpeta.
- AUDIT_PLAN: lectura en el destino solo sin contexto guardado y con plazo (`run_with_timeout`); destino caído o
  carpeta inexistente → sin aviso, nunca bloquea la página; borrar sigue con la vista previa y el nombre (dos pasos),
  solo propietarios con destino rw; sin migraciones. GO.
- IMPLEMENT: `domain/context/service.py`, `api/v1/{context,schemas}.py`, `features/context/{ContextPage,useContext}.ts(x)`,
  i18n, `docs/guides/contexto.md`, `CHANGELOG.md`; OpenAPI y `schema.d.ts`.
- AUDIT_CODE: test de backend (construir → quitar el contexto guardado → detectar → vista previa → borrar → sin restos)
  y de frontend (aviso, botones, carpeta en Construir); `ruff`, `mypy`, `tsc`, `eslint`, `vitest` (173) en verde.

## Directrices para Futuras IAs
- **[contexto/restos]**: doc_organize escribe en el destino antes de que la web guarde el contexto; un run cortado deja
  restos que solo ve `/context/leftover`. Construir y borrar los resuelven por `context.json`.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- CI del PR #101.
