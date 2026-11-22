# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- Web: `backend/app/integrations/doc_organize/ai.py` (familias, `fetch_usage`, `phase_stats`, prueba de conexión),
  `backend/app/domain/ai/usage.py`, `backend/app/domain/ai/settings.py`, `backend/app/api/v1/ai.py`,
  `backend/app/api/v1/schemas.py` (`AiFamilyKey`, `AiUsage*Out`), `backend/app/db/models.py` (`AiSetting`, `Run`),
  `backend/app/integrations/doc_organize/{agents,evaluation,context}.py`, `backend/app/jobs/operations/{ai,agents,context}.py`,
  `frontend/src/features/admin/{AiUsagePage,AiSettingsPage,useAi}.tsx`, `frontend/src/features/runs/RunResult.tsx`,
  `frontend/src/app/router.tsx`, `alembic/versions` (última `0024`).
- Librería 2.0.1: `ai/__init__.py` (exporta `GitHubCopilotUsageClient`, `github_copilot_usage_config_from_env`),
  `ai/github_copilot_usage_client.py`, `ai/litellm_usage_client.py` (`/key/info`, una línea con `quantity = spend`),
  `ai/llm_client.py` (`LlmUsage(prompt_tokens, completion_tokens)`), `core/models.py` (`AiPhaseStats`, `UsageLineItem`,
  `GitHubCopilotUsageConfig`, `UsageSourceName.GITHUB_COPILOT`), `ai/services.py` (`draft_taxonomy` → `LlmResult`).

## Estado actual observado
- `feature/2.1` con F3 sin commit: frontend en verde (169 tests); e2e pendientes.
- Tokens ya presentes en el resultado de los runs: construir contexto (`ai.classification`, `enrichment`, semántica
  vía `phase_stats`), agentes (`prompt_tokens`/`completion_tokens`), evaluación. El borrador de manifiesto
  (`taxonomy_draft`) **no** los guarda aunque `draft_taxonomy` devuelve `LlmResult.usage`.
- Ningún coste por ejecución: solo el gasto acumulado de la clave (`/key/info`).

## Estado Git relevante
- Rama activa: feature/2.1 (web); develop (librería)
- Cambios locales pre-existentes: los de F3 (sesión 2026-11-22-contexto-orden)
- Último tag / versión publicada: web v2.0.1; doc_organize 2.0.1

## Clasificación metodológica
- Tipo principal: new_feature (F2) + retirada (F1)
- Estado real de alcance: acotado, en dos repos (librería primero)
- Consecuencia: PLAN + AUDIT_PLAN; IMPLEMENT espera aprobación

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica):
- Verificar en el proxy del mantenedor la cabecera de coste de LiteLLM (ver AUDIT_PLAN, A2).
