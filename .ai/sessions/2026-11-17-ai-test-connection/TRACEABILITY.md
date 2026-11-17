# TRACEABILITY

## Session metadata
- id: 2026-11-17-ai-test-connection
- fecha: 2026-11-17
- rama: `feat/ai-test-connection` (PR #65); release 1.7.0 desde `develop`
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + VERSION (1.7.0)

## Prompt issued
«En configuración IA se necesita poder realizar un Test Connection por el usuario. PLAN y AUDIT_PLAN» y, después,
«IMPLEMENT».

## Context supplied
- `.ai/sessions/2026-11-17-ai-test-connection/PLAN.md` (GO_CONDICIONAL).
- Decisiones: el mantenedor pidió IMPLEMENT sin elegir; se aplicaron las recomendadas (valores del formulario y
  «Probar el modelo» incluido).

## AI output summary
- `POST /admin/ai-settings/{family}/test` (admin de instancia): `domain/ai/connection_test.py` (`probe_family`) e
  `integrations/doc_organize/ai.py` (`check_connection`).
- LiteLLM: `GET /key/info` con `LiteLLMUsageClient` (sin tokens; `model_access` desde `models`). GitHub Copilot: uso del
  mes. «Probar el modelo»: `DomainClassificationClient.classify` mínima; un error genérico es `ai_model`.
- Seguridad: la clave guardada nunca va a otra `base_url` (422 `secret_required`); respuesta con solo un código;
  auditoría `ai_settings.test` sin valores; 429 `ai_test_too_soon` cada 10 s por familia.
- Frontend: botones «Probar conexión» y «Probar el modelo» por tarjeta, resultado con `role="status"`, se borra al
  editar.
- Tests: 14 de API con `httpx.MockTransport` (incluida la fuga de la clave en respuesta, logs y auditoría) y 3 de
  frontend. Backend 591 passed.
- De paso: tests del frontend estables (esperas de 5 s y, en #66, Mantine `env="test"`).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-11-17-ai-test-connection/PLAN.md` | emitido, con estado |
| Backend | `app/domain/ai/connection_test.py`, `app/integrations/doc_organize/ai.py`, `app/api/v1/{ai,schemas}.py` | completado |
| Frontend | `features/admin/{AiSettingsPage,useAi}.tsx` | completado |
| Guía | `docs/guides/ia.md` § «Probar la conexión» | completado |

## Directrices para Futuras IAs
- **[pytest]**: no nombrar `test_*` ni `Test*` a funciones o clases de la app: si un test las importa, pytest las
  recoge (de ahí `check_connection`, `probe_family`, `ProbeOutcome`).
- **[S1]**: cualquier prueba con valores del formulario debe impedir que un secreto guardado vaya a otro servidor.

## Veredicto final
Veredicto: CLOSED

Pendientes al cierre:
- G45 (propuesta, sin abrir): un `check_connection()` en los clientes de doc_organize que pruebe URL, clave y modelo.
