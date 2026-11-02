# TRACEABILITY

## Session metadata
- id: 2026-11-02-fase8
- fecha: 2026-11-02 → 2026-11-03
- rama: `develop` (f84b031, 0.8.0); cambios sin commit, rama propuesta `feature/fase-8`
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
/phase — Fase: 8. Inputs del mantenedor ([00_REQUEST.md](00_REQUEST.md)):
- alcance completo (WB-8.1, WB-8.2, WB-8.3, WF-8.1 y cierre de paridad);
- sin mejoras opcionales;
- `cryptography` permitida;
- sin credenciales reales: clientes de IA sustituidos.

## Context supplied
- ROADMAP (Fase 8), PARIDAD, DOC_ORGANIZE_GAPS, TAREAS_DOC_ORGANIZE, ADR-004 y ADR-012, TRACEABILITY de la Fase 7.
- doc_organize `v0.13.0-1-g8a0e35a` (clon local, solo lectura):
  - `ai/` (los 5 clientes, `_http_client_base`, `_secrets`);
  - `core/models.py` (`*Config`, resultados, `UsageSnapshot`) y `core/exceptions.py`;
  - `context/context_builder.py`, `taxonomy_manifest_sampler.py` y `taxonomy_manifest.py`;
  - web integrada `web/ai_settings_config.py`, `web/routes/ai_settings.py` y `web/routes/context.py` como referencia
    funcional (no tiene panel de uso).

## AI output summary
- **PLAN + AUDIT_PLAN** ([PLAN.md](PLAN.md)): `GO_CONDICIONAL`. El mantenedor aprobó D1–D4 tal cual:
  - D1: la Fase 8 cierra la paridad funcional y L-10 se puede pedir ya;
  - D2: panel de uso solo para admin, en la API con caché;
  - D3: 500 documentos con IA por run;
  - D4: el rol `editor` basta para la IA.
- **IMPLEMENT backend**:
  - migración `0008_ai`: `ai_settings`, `project_contexts.ai_classification` y `context_documents.classified_by`;
  - `core/crypto.py` (MultiFernet) y `domain/ai/` (`settings.py`, `usage.py`, `errors.py`);
  - `integrations/doc_organize/ai.py`, el único módulo que importa `doc_organize.ai`: familias, `*Config`, clientes
    vigilados (G33–G35), borrador (G36) y uso;
  - `context_build` con `ai_classification`; operación nueva `taxonomy_draft`;
  - router `api/v1/ai.py`; CLI `rotate-secrets`; 3 ajustes administrables;
  - auditoría `ai_settings.update` y `project.taxonomy_draft`.
- **IMPLEMENT frontend**:
  - `AiSettingsPage` y `AiUsagePage`;
  - en la página de contexto, el interruptor de IA, la marca «IA» y el panel «Borrador con IA» (`useTaxonomyDraft`);
  - `RunResult` con datos anidados; traducciones; menú lateral desplazable.
- **E2E**: `frontend/e2e/ai.spec.ts` contra `litellm-fake` (`docker/e2e/fake_litellm.py`, solo en
  `docker-compose.e2e.yml`).
- **AUDIT_CODE** (revisión propia con los checklists de Code Auditor, Frontend Reviewer y Security Reviewer):
  - **CRITICAL corregido**: la clave virtual de LiteLLM salía en claro en los logs de `web`. `LiteLLMUsageClient`
    consulta `/key/info?key=<clave>` y el logger `httpx` escribe la URL en INFO. Se vio con el E2E, en
    `docker compose logs web`. Arreglo: `httpx`/`httpcore` en WARNING en `configure_logging` (API y subproceso).
    Test de regresión `test_usage_never_logs_the_key`, que falla sin el arreglo.
  - **MEDIUM corregido**: el borrador de la IA no tenía tope antes de guardarse en `runs.result`. Ahora se limita a
    `MAX_TEMPLATE_BYTES`.
  - **Frontend corregido**: el menú lateral no se desplazaba y en 720 px los enlaces nuevos quedaban fuera de alcance
    (WCAG 1.4.10).
  - **ADR**: el ADR-013 estaba reservado a multi-tenant (Fase 9); el nuevo se numera ADR-014.
- **VERSION**:
  - 0.9.0 en backend, frontend, OpenAPI, `uv.lock`, `package-lock.json` y `.env.example`;
  - CHANGELOG, ROADMAP, PARIDAD (todas las filas hasta la Fase 8 en ✅), GAPS (G33–G37 abiertos con rodeo, G3
    aplicado), TAREAS (L-3a…L-3e), DEPENDENCIAS, `product.md`;
  - guía `ia.md`, ADR-014 y ADR-004 implementado.
- **Validación final**:
  - backend en Linux (imagen `backend-dev`): ruff format y check, mypy, pytest (450 en verde, 1 omitido) y OpenAPI
    `--check`;
  - frontend: format, lint, typecheck, 77 tests y build;
  - `zensical build --strict` sin avisos;
  - imagen construida con `/api/health` 200 (doc_organize 0.13.0);
  - E2E 14/14 con un worker (`DOW_PORT=8090`: el 8080 lo usa otro proyecto local).
  - En Windows fallan 23 tests de backend que ya fallaban antes de la fase (rutas con `\`). El CI corre en Linux.

## Artefactos generados
- `backend/alembic/versions/0008_ai.py`, `backend/app/core/crypto.py`, `backend/app/domain/ai/`,
  `backend/app/integrations/doc_organize/ai.py`, `backend/app/jobs/operations/ai.py`, `backend/app/api/v1/ai.py`
- `backend/tests/unit/test_ai_domain.py`, `backend/tests/api/test_ai.py`, `backend/tests/jobs/test_ai_operation.py`,
  `backend/tests/jobs/conftest.py`
- `frontend/src/features/admin/{AiSettingsPage,AiUsagePage,useAi,ai.test}.tsx?`, `frontend/src/features/context/ai.test.tsx`,
  `frontend/e2e/ai.spec.ts`
- `docker/e2e/fake_litellm.py`, servicio `litellm-fake` en `docker-compose.e2e.yml`
- `docs/guides/ia.md`, `docs/adr/ADR-014-uso-de-servicios-de-ia.md`
- `build/logs/fase8-*.txt` (local, ignorado por git)

## Directrices para Futuras IAs
- **[secretos]**: `httpx` y `httpcore` deben quedarse en WARNING (`core/logging.py`, `QUIET_LOGGERS`).
  `LiteLLMUsageClient` pone la clave en la URL y httpx escribe cada URL en INFO. Al subir de nivel cualquier logger
  de terceros, pasa `test_usage_never_logs_the_key`.
- **[secretos]**: las credenciales de IA se descifran solo en `domain/ai/settings.py` (`resolve`/`connection`). En
  los jobs se descifran en el subproceso (`jobs/operations/context.py::ai_connection`), nunca al encolar. Nunca van a
  `runs.params`, a `run.json` ni a eventos.
- **[secretos]**: `AiConnection.values` lleva `repr=False`. Cualquier dataclass o modelo nuevo con secretos también
  tiene que ocultarlos en `repr`.
- **[ia]**: solo `integrations/doc_organize/ai.py` importa `doc_organize.ai`. Las `*_config_from_store_or_env`
  están obsoletas (se retiran en 1.0.0): construye los `*Config` con `config_for(connection)`.
- **[ia]**: `ContextBuilder` recibe un cliente **vigilado** (`classification_client`). No le pases un cliente de la
  librería directamente: perderías el presupuesto, los cortes por auth o conexión y el recuento (G33–G35).
- **[ia]**: con plantilla o manifiesto se usa `litellm_taxonomy_classification`; sin ellos,
  `litellm_classification` (`context_ai_family`). `build_context` rechaza la familia equivocada.
- **[ia]**: el borrador (`taxonomy_draft`) nunca escribe en el proyecto. Los documentos de la muestra llevan
  `source_path` relativo a la ubicación (`_relative_documents`, G36) para que no salgan rutas del contenedor.
- **[e2e]**: la IA se prueba con `litellm-fake` (clave `sk-e2e-fake`, `http://litellm-fake:4000`). Un `getByLabel`
  sobre un campo con botón «Borrar el valor guardado de …» necesita `.and(locator('input'))`. Un `Switch` de Mantine
  se acciona con `getByRole('switch').check()`.
- **[tests]**: `json.dumps` escapa los acentos. Para buscar textos en español en eventos usa `ensure_ascii=False`.
  Las fixtures `project` y `run` de `test_context_operation.py` se reexportan en `tests/jobs/conftest.py`.
- **[windows]**: `Path.write_text` en Windows escribe CRLF. En scripts de edición usa `newline="\n"`
  (`.gitattributes` exige LF).

## Pendientes (no bloquean)
- Pedir a doc_organize **L-10** (deprecar la web integrada, 0.14.0) y **L-3a…L-3e** (G33–G37; G37 registrado tras
  el cierre, al preparar las instrucciones para doc_organize). No se pide desde este
  repositorio (regla 1).
- Prueba manual con un LiteLLM real y un PAT de GitHub real; la API de facturación de Copilot no se ha probado contra
  GitHub.
- Los enlaces deshabilitados «Fase N» del menú (escaneo, documentos, duplicados, contexto) ya no corresponden a fases
  pendientes; conviene retirarlos en un refactor de navegación.
- `ai_settings` es de instancia; en la Fase 9 hay que decidir si pasa a ser por tenant.

## Veredicto final
GO — Fase 8 cerrada en 0.9.0 con doc_organize 0.13.0.
