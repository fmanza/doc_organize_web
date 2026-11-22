# TRACEABILITY

## Session metadata
- id: 2026-11-22-contexto-orden
- fecha: 2026-11-22
- rama: develop (PLAN) → feature/2.1 (IMPLEMENT)
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE

## Prompt issued
Mejorar las pantallas de CONTEXTO para que siga un orden lógico, luego AUDIT_PLAN

## Context supplied
- Análisis previo de la conversación (plan por fases F0-F5 sobre la IA y la pantalla Contexto)
- Ficheros listados en `00_CONTEXT_SNAPSHOT.md`

## AI output summary
- Lectura de `ContextPage.tsx`, `ManifestCard.tsx`, `ProfileCard.tsx`, `AgentPanel.tsx`, `Versions.tsx`,
  `DeliveryCard.tsx`, cabeceras de `ReviewPage.tsx`, `QualityPage.tsx`, `SiteViewerPage.tsx` y `router.tsx`.
- Comprobado en doc_organize 2.0.1 que `profile.md` se aplica con cualquier catálogo (`context_builder.py:479-481`).
- Emitidos PLAN y AUDIT_PLAN en `PLAN.md`; veredicto GO_CONDICIONAL (D1 bloqueante).
- Decisiones del mantenedor: D1 y D2 recomendadas; D3 = una versión con F1 y F2 (rama `feature/2.1`).
- IMPLEMENT solo en frontend (ver `PLAN.md` § IMPLEMENT); e2e adaptados, no ejecutados.
- AUDIT_CODE: prettier, tsc, eslint, vitest (169) y `zensical build --strict` en verde; C1 y C2 corregidos.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | .ai/sessions/2026-11-22-contexto-orden/00_REQUEST.md | emitido |
| CONTEXT SNAPSHOT | .ai/sessions/2026-11-22-contexto-orden/00_CONTEXT_SNAPSHOT.md | emitido |
| PLAN + AUDIT_PLAN | .ai/sessions/2026-11-22-contexto-orden/PLAN.md | emitido (GO) |
| IMPLEMENT | frontend/src/features/context/*, i18n, e2e, docs/guides/contexto.md, CHANGELOG.md | completado, sin commit |
| AUDIT_CODE | .ai/sessions/2026-11-22-contexto-orden/PLAN.md § AUDIT_CODE | GO_CONDICIONAL (e2e) |

## Directrices para Futuras IAs
- **[contexto/perfil]**: `profile.md` lo usa la librería con cualquier catálogo, al clasificar y al describir con IA
  (`compose_profile`); no ocultarlo en la interfaz sin migrarlo o avisar.
- **[contexto/reconstruir]**: «Reconstruir» ya depende de que exista un contexto (`ContextPage.tsx:496`, `:609`).
- **[contexto/pasos]**: los pasos de `/context` son paneles `hidden` siempre montados; en tests, cambiar de paso con
  `getByRole('link', { name: '2. Construir' })` o entrar con `?paso=`; `getByText` también ve lo oculto (usar
  `{ ignore: '[hidden] *' }`).
- **[contexto/estado]**: selección de catálogo y borrador del manifiesto viven en `ContextPage`; al repartir en
  pestañas, mantenerlas montadas.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- e2e con la imagen de `feature/2.1`; revisión visual en móvil.
- F1 (retirar Copilot) y F2 (uso con tokens) en la misma versión 2.1.0.
