# PLAN + AUDIT_PLAN — Sin Copilot y uso de IA con tokens (2026-11-22)

Skill: `new-feature` (web) con una parte en la librería. Solo PLAN y AUDIT_PLAN; sin implementar. Fases F1 y F2 del
plan general; salen con F3 (`2026-11-22-contexto-orden`) en la **web 2.1.0**, sobre **doc_organize 2.1.0**.

## Contexto: cómo está hoy

**Copilot.** Es la familia `github_copilot_usage` (usuario y PAT cifrado) en IA › Configuración, una fuente
`github_copilot` en IA › Uso y una clave en `/ai/status`. En la librería es API pública:
`GitHubCopilotUsageClient`, `github_copilot_usage_config_from_env` (`doc_organize.ai`), `GitHubCopilotUsageConfig` y
`UsageSourceName.GITHUB_COPILOT` (`doc_organize.core.models`).

**Uso.** IA › Uso enseña, por fuente, una tabla de líneas `fecha · producto · cantidad · coste`. LiteLLM solo da
`GET /key/info`: **una línea con el gasto acumulado de la clave**, y la columna «Cantidad» repite el dinero
(`quantity = spend`, `unit_type = "usd"`). No hay tokens, ni periodo, ni reparto por tarea, modelo o proyecto.

**Lo que ya existe y no se aprovecha:**

| Ejecución | Qué guarda hoy en `runs.result` |
|---|---|
| `context_build` | `ai.classification` y `enrichment`: `calls`, `cached`, `failed`, `prompt_tokens`, `completion_tokens` (`phase_stats`); semántica aparte |
| `taxonomy_agent`, revisor | `prompt_tokens`, `completion_tokens` (estimados si el proxy no los da), pasos, herramientas |
| Evaluación (comparar) | `prompt_tokens`, `completion_tokens` |
| `taxonomy_draft` | **Nada de tokens**, aunque `draft_taxonomy` devuelve `LlmResult.usage` |

Los modelos por tarea están en el contexto (`ai_classification_model`, `ai_enrichment_model`) y en la configuración.
El **coste por ejecución no existe** en ningún sitio.

## Inputs

| Campo | Valor |
|---|---|
| Objetivo | F1: retirar Copilot de la web y marcarlo obsoleto en la librería. F2: registrar el consumo de IA de cada ejecución y mostrarlo por periodo, tarea, modelo, proyecto y ejecución, con tokens, caché y coste |
| Rutas (librería) | `ai/github_copilot_usage_client.py`, `ai/__init__.py`, `core/models.py` (`GitHubCopilotUsageConfig`, `LlmUsage`→coste, `AiPhaseStats.cost_usd`), `ai/llm_client.py`, `ai/_http_client_base.py` (cabeceras), `ai/agents.py` (`AgentRun.cost_usd`), tests, `docs/` + `zensical.toml`, `CHANGELOG.md` |
| Rutas (web, backend) | `integrations/doc_organize/ai.py`, `domain/ai/{settings,usage}.py`, `domain/ai/usage_log.py` **(nuevo)**, `api/v1/{ai,runs,schemas}.py`, `db/models.py` (`AiUsageRecord` **nuevo**), `alembic/versions/0025_drop_copilot_settings.py` **(nuevo)**, `0026_ai_usage.py` **(nuevo)**, `jobs/operations/{context,ai,agents,evaluation}.py`, tests |
| Rutas (web, frontend) | `features/admin/{AiUsagePage,useAi}.tsx`, `features/admin/AiUsageCharts.tsx` **(nuevo)**, `features/runs/{RunDetailPage,RunResult}.tsx`, `i18n/es/features.json`, tests, `e2e/ai.spec.ts`; `openapi/` y `schema.d.ts` regenerados |
| Contrato HTTP | `GET /admin/ai-usage?period=7d\|30d\|month\|all` (nuevo parámetro; respuesta ampliada); `GET /runs/{id}` gana `ai_usage`; `/admin/ai-settings` y `/ai/status` pierden la familia `github_copilot_usage`; la fuente `github_copilot` desaparece |
| Pantallas | IA › Configuración (sin la tarjeta de Copilot), IA › Uso (rediseño), detalle de ejecución (tarjeta «Consumo de IA») |
| Permisos | IA › Uso: admin de instancia (como hoy). Detalle de ejecución: miembros del proyecto ven tokens; el coste, solo admins (D4) |
| doc_organize | 2.1.0: `LlmUsage.cost_usd`, `AiPhaseStats.cost_usd`, `AgentRun.cost_usd` (nuevos); Copilot con `DeprecationWarning` |
| Restricciones | Dos migraciones aditivas o de limpieza; sin dependencias nuevas; la web no llama a LiteLLM por su cuenta |

## PLAN

### Orden de entrega

1. **Librería 2.1.0** (L1 + L2), publicada.
2. **Web**: subir a doc_organize 2.1.0; F1 (W1) y F2 (W2-W4) en `feature/2.1`, junto con F3.
3. e2e de todo `feature/2.1` → **web 2.1.0**.

### L1 · Librería: Copilot obsoleto (se retira en 3.0)

- `GitHubCopilotUsageClient.__init__`, `github_copilot_usage_config_from_env()` y `GitHubCopilotUsageConfig`
  (`model_post_init`) lanzan `DeprecationWarning`, con `stacklevel=2`: «Obsoleto desde 2.1.0, se retira en 3.0; el uso se
  consulta en LiteLLM».
- `UsageSourceName.GITHUB_COPILOT` se queda hasta 3.0 (un `Enum` no avisa al usarse; se documenta).
- Docs: aviso en la página de la API, y en la guía de migración la sección «Hacia 3.0». CHANGELOG `Deprecated`.
- Tests: `pytest.warns(DeprecationWarning)` en los tres puntos; los tests existentes de Copilot se marcan para que la
  advertencia no rompa con `-W error`.

### L2 · Librería: coste por llamada

- LiteLLM Proxy devuelve el coste de cada respuesta en la cabecera **`x-litellm-response-cost`** (USD). **Hay que
  comprobarlo en el proxy del mantenedor antes de implementar** (A2).
- `AiHttpClientBase` expone las cabeceras de la respuesta al cliente; `LlmClient` lee la cabecera y rellena
  `LlmUsage.cost_usd: float | None` (`None` si falta o no es un número ≥ 0).
- Se suma en `AiPhaseStats.cost_usd: float | None` y en `AgentRun.cost_usd: float | None`. Es `None` si **ninguna**
  llamada lo trajo; si solo lo trajeron algunas, se suma lo conocido y `cost_complete=False`.
- `LlmResult.usage` ya llega a quien llama (`draft_taxonomy`): no cambia la firma.
- Los resultados de la caché (`cached=True`) cuestan 0 y no suman.
- Aditivo: minor 2.1.0. Tests con `httpx.MockTransport` (con y sin cabecera, valor inválido, caché).

### W1 · Web: sin Copilot (F1)

- `integrations/doc_organize/ai.py`: fuera la `FamilySpec("github_copilot_usage")`, la fuente `github_copilot`, sus ramas
  en `fetch_usage` y en la prueba de conexión, y el import de `GitHubCopilotUsageClient` (así no salta el
  `DeprecationWarning`).
- `domain/ai/usage.py`: `SOURCES` solo con LiteLLM. `domain/ai/settings.py`: fuera la validación de usuario de GitHub.
- `schemas.py`: `AiFamilyKey` y `AiUsageSourceOut.source` sin Copilot.
- **Migración `0025_drop_copilot_settings`**: borra las filas `ai_settings` de la familia `github_copilot_usage` (el PAT
  cifrado no se debe quedar sin uso). `downgrade` no las recupera: queda escrito en el CHANGELOG (A1). Se audita como
  `ai_settings.cleared` sin valores.
- Variables `DOC_ORGANIZE_GITHUB_USERNAME`/`DOC_ORGANIZE_GITHUB_PAT`: si siguen definidas, se avisa en IA › Configuración,
  como las variables antiguas de 1.x (`legacy_env`).
- Frontend: sin textos `ai.families.github_copilot_usage.*` ni `ai.usage.sources.github_copilot`; la página de
  configuración ya pinta las familias que manda el servidor. Tests y stubs sin la familia.
- Docs: `docs/guides/ia.md` sin Copilot. **ADR-014 y ADR-004 se corrigen en el sitio con una nota fechada al final**,
  sin borrar su historia (preferencia del mantenedor). CHANGELOG `Removed`.

### W2 · Web: registro del consumo (F2, datos)

**Tabla `ai_usage` (migración `0026_ai_usage`):**

| Columna | Tipo | Nota |
|---|---|---|
| `id` | int PK | |
| `created_at` | UTC | Fin de la ejecución |
| `tenant_id` | FK tenants | Para una vista por tenant más adelante |
| `project_id` | FK projects `SET NULL` | El consumo se conserva al borrar el proyecto |
| `project_name` | str | Copia del nombre en ese momento |
| `run_id` | FK runs `SET NULL` | |
| `operation` | str | `context_build`, `taxonomy_draft`, `taxonomy_agent`, `review_agent`, `evaluation`… |
| `task` | str | `classify`, `enrich`, `embed`, `taxonomy_design`, `agent` |
| `model` | str nullable | El de la tarea en esa ejecución |
| `calls`, `cached`, `failed` | int | Documentos enviados, resueltos con la caché y fallidos (pasos, en agentes) |
| `prompt_tokens`, `completion_tokens` | int | |
| `tokens_estimated` | bool | Agentes sin datos del proxy |
| `cost_usd` | float nullable | Con L2; `NULL` si el proxy no lo dio |
| `cost_complete` | bool | |

Índices `(created_at)` y `(project_id, created_at)`.

**Quién escribe:** `domain/ai/usage_log.record(db, run, rows)`, al terminar cada job con IA, también si se cancela o
falla después de llamar al modelo (los tokens ya se gastaron). Una fila por tarea:

| Operación | Filas |
|---|---|
| `context_build` | `classify`, `enrich`, `embed` (semántica), si se usaron |
| `taxonomy_draft` | `taxonomy_design` (el job pasa a guardar `usage` en su resultado) |
| `taxonomy_agent`, revisor | `agent` |
| evaluación (comparar) | `classify` |

Escribir el consumo **nunca hace fallar la ejecución**: se registra el error en el log y sigue (A10). «Probar el
modelo» no se registra: son unos pocos tokens.

**Histórico:** la misma migración rellena `ai_usage` desde `runs.result` de las ejecuciones terminadas, con los
campos que ya existen (tokens, envíos, caché). El modelo y el coste quedan vacíos (D3).

### W3 · Web: API

- `GET /admin/ai-usage?period=7d|30d|month|all` (por defecto `30d`). La respuesta añade `local`:
  - `period_start`, `period_end`;
  - `totals`: ejecuciones, documentos enviados, desde caché, fallidos, tokens de entrada y de salida, coste conocido y
    número de ejecuciones con coste;
  - `by_task`, `by_model`, `by_project` (con `project_id` para enlazar), `by_day` (agrupado por día en UTC, D2);
  - `top_runs`: las 10 ejecuciones con más tokens, con enlace.
- La fuente LiteLLM (`/key/info`) añade `budget`: gasto, presupuesto máximo, restante y fecha de reinicio, leídos del
  `raw` del snapshot si el proxy los da; si no, `null`.
- `GET /runs/{id}` añade `ai_usage: [{task, model, calls, cached, failed, prompt_tokens, completion_tokens,
  tokens_estimated, cost_usd?}]`. `cost_usd` solo para admins (D4).
- Agregados en SQL con `GROUP BY` sobre el índice de fecha. El día se agrupa de forma portable entre SQLite y
  PostgreSQL (`date(created_at)` frente a `created_at::date`) con una función de dialecto (A7).

### W4 · Web: pantallas

**IA › Uso** (rediseño):

1. Periodo: 7 días · 30 días · Este mes · Todo.
2. Fila de indicadores: ejecuciones con IA · documentos enviados · desde caché (y % de ahorro) · tokens de entrada ·
   tokens de salida · coste (con «coste de N de M ejecuciones» si no está completo).
3. Tarjeta **LiteLLM**: gasto acumulado de la clave, presupuesto y restante (barra) y reinicio. Sin la columna
   «Cantidad» cuando la unidad es dinero.
4. **Tokens por día**: barras apiladas entrada y salida (SVG propio, sin dependencias; se carga la skill `dataviz`
   al implementar).
5. Tablas por **tarea**, **modelo** y **proyecto** (enlace al proyecto) y **ejecuciones que más gastaron** (enlace a la
   ejecución): ejecuciones, enviados, caché, tokens de entrada y salida, coste.
6. Vacío: «Todavía no hay consumo de IA registrado en este periodo». Error de LiteLLM: la tarjeta lo dice y el resto se
   ve igual.

**Detalle de ejecución:** tarjeta «Consumo de IA» si `ai_usage` no está vacío: una fila por tarea con modelo, enviados,
caché, tokens (con «≈» si son estimados) y coste para admins.

### W5 · Tests y documentación

- Backend: `usage_log` (filas por operación, error que no rompe el run), migraciones `0025` (borra solo Copilot) y
  `0026` (relleno desde `runs.result` con un resultado de cada tipo), API (`period`, agregados, permisos del coste,
  `budget`), sin Copilot en `/ai/status` y `/admin/ai-settings`.
- Frontend: IA › Uso (indicadores, periodo, vacío, error de LiteLLM, sin columna de cantidad), tarjeta del run,
  configuración sin Copilot.
- e2e `ai.spec.ts`: tras construir con IA, IA › Uso muestra tokens > 0 en la tarea `classify`.
- `docs/guides/ia.md` (sección Uso), CHANGELOG `[Unreleased]`, OpenAPI y `schema.d.ts` regenerados.

---

## AUDIT_PLAN

### Riesgos funcionales

| Id | Riesgo | Severidad | Corrección |
|---|---|---|---|
| A1 | La migración `0025` borra el PAT de GitHub y bajar de versión no lo recupera | Baja | Es lo que se busca (no guardar un secreto sin uso). CHANGELOG `Removed` y nota de bajada |
| A2 | **El coste por llamada depende de que el proxy mande `x-litellm-response-cost`.** Con modelos locales (Ollama) puede faltar o valer 0 | Alta | **Comprobarlo antes de L2**: `curl -i` a `/chat/completions` del proxy con la clave de una tarea. Sin cabecera: L2 se queda en `None`, la pantalla dice «sin coste por ejecución» y solo se ve el gasto de la clave |
| A3 | Los tokens de los agentes son estimados si el proxy no los informa | Media | `tokens_estimated` y «≈» en la pantalla |
| A4 | Mezclar tokens de embeddings con los de chat infla los totales | Media | Fila propia `embed` en «por tarea»; los indicadores separan entrada y salida |
| A5 | El relleno desde `runs.result` lee formas distintas por operación y versión | Media | Solo campos conocidos; lo que no encaja se salta sin fallar; un test por forma; el modelo queda vacío |
| A6 | El coste es sensible para los miembros de un proyecto | Media | D4: coste solo para admins; los miembros ven tokens |
| A7 | Agrupar por día no es igual en SQLite y PostgreSQL | Baja | Función por dialecto y tests en los dos (o el que use CI) |
| A8 | Quitar valores de enumeraciones cambia el contrato HTTP | Baja | Solo endpoints de admin y `/ai/status`; el único cliente es el propio frontend, regenerado en el mismo cambio |
| A9 | Si la web aún importara algo de Copilot, el `DeprecationWarning` de la librería rompería los tests con `-W error` | Baja | W1 quita los imports antes de subir a 2.1.0 |
| A10 | Un fallo al escribir el consumo tumba una construcción larga | Alta | `record` con `try`/log; test que lo cubre |
| A11 | Doble registro si un job se reintenta | Media | Clave única `(run_id, task)`; el segundo intento actualiza en vez de duplicar |

### Seguridad

- Menos superficie: desaparece un secreto (PAT) y una llamada a GitHub.
- `ai_usage` no guarda texto de documentos ni prompts: solo recuentos, modelo, coste y el nombre del proyecto.
- El coste se filtra por rol en el servidor (no solo se oculta en la pantalla).

### Simplificaciones

- S1: **sin `/spend/logs` de LiteLLM**: pide clave maestra y cambia entre versiones. Bastan el registro propio y la
  cabecera de coste.
- S2: sin librería de gráficos; barras en SVG.
- S3: sin política de retención por ahora (filas pequeñas). Si crece, se añade un ajuste de días.
- S4: sin exportar a Excel en esta versión.

### Decisiones pendientes

| Id | Decisión | Recomendación |
|---|---|---|
| D1 | Copilot en la librería: obsoleto en 2.1 y fuera en 3.0, o fuera ya (rompe la API: obligaría a 3.0) | **Obsoleto en 2.1, fuera en 3.0** |
| D2 | Día de los agregados: UTC o hora local | **UTC**, indicado en la pantalla |
| D3 | Rellenar el histórico desde `runs.result` | **Sí**, sin modelo ni coste |
| D4 | Quién ve el coste en el detalle de ejecución | **Solo admins**; los miembros ven tokens |

### Veredicto

**GO_CONDICIONAL**

Condiciones para IMPLEMENT:

1. A2 comprobado en el proxy (con o sin cabecera de coste, se sigue; cambia el alcance de L2).
2. D1-D4 decididas.
3. La librería 2.1.0 publicada antes de subir la dependencia de la web.
4. `record` no puede fallar una ejecución (A10) y no duplica (A11), con tests.
5. OpenAPI y `schema.d.ts` regenerados en el mismo cambio; CHANGELOG de librería y web; `zensical build --strict` en
   los dos repos.

### Decisiones del mantenedor (2026-11-22)

- **A2: el proxy no manda `x-litellm-response-cost`.** Se cae **L2** entera: sin coste por llamada ni por ejecución. El
  coste solo es el gasto acumulado de la clave (`/key/info`). `ai_usage` no tiene `cost_usd` ni `cost_complete`; la
  pantalla no tiene columnas de coste por tarea, modelo o proyecto. Si un día el proxy lo manda, se añade aparte.
- D1: obsoleto en 2.1, fuera en 3.0.
- D2: **por día en hora local**, con la zona indicada en la pantalla. El navegador manda su zona IANA
  (`Intl.DateTimeFormat().resolvedOptions().timeZone`) en `?tz=`; el servidor la valida con `zoneinfo` (por defecto
  UTC) y agrupa en Python las filas del periodo (pocas filas: una por ejecución y tarea). El periodo («este mes»,
  «7 días») también se calcula en esa zona.
- D3: sí, sin modelo.
- D4: ya no aplica (sin coste por ejecución). Los tokens de la ejecución los ven sus miembros.

**Consecuencia:** la web **no depende** de doc_organize 2.1.0 (L1 solo añade avisos de obsolescencia que la web ya no
usa). L1 sale cuando toque, sin bloquear la web 2.1.0.

### Veredicto (revisado)

**GO.** Condiciones 1 y 2 cumplidas; la 3 ya no aplica; siguen la 4 y la 5.

---

## IMPLEMENT (2026-11-22)

**Librería** (`doc_organize`, rama `feature/2.1-copilot-deprecation`, sesión `2026-11-22-copilot-obsoleto`): L1 hecha.

**Web** (`feature/2.1`, junto con F3):

| Fichero | Cambio |
|---|---|
| `integrations/doc_organize/ai.py` | Sin familia ni fuente de Copilot ni sus imports; `COPILOT_ENV_VARS`; `KeyBudget`/`key_budget` desde `/key/info`; `classification_stats`/`enrichment_stats` con `model`; `DraftOutcome` con modelo, tokens y caché |
| `integrations/doc_organize/{context,agents}.py` | Semántica con `prompt_tokens` y `model`; agentes con `model` y `tokens_estimated` |
| `jobs/operations/ai.py` | El borrador guarda `model`, `prompt_tokens`, `completion_tokens`, `cached` |
| `domain/ai/settings.py`, `usage.py` | Sin validación de GitHub; `legacy_variables` con las de Copilot (`None`); una sola fuente |
| `domain/ai/usage_log.py` (nuevo) | `rows_from_result`, `record` (una fila por run y tarea, actualiza), `for_run`, `summary` (periodo y día en la zona del navegador, días vacíos con ceros) |
| `db/models.py` | `AiUsageRecord` |
| `alembic/versions/0025_drop_copilot_settings.py`, `0026_ai_usage.py` (nuevas) | Borrado de Copilot; tabla `ai_usage` y relleno con extractor congelado |
| `jobs/runner.py` | `_record_ai_usage` **antes** de cerrar el run, con `try`/log |
| `api/v1/{ai,runs,schemas}.py` | `period`/`tz`, `local`, `budget`; `RunOut.ai_usage` en el detalle; `AiLegacyVariableOut.replacement` opcional |
| Frontend | `AiUsagePage` rediseñada, `AiUsageCharts.tsx` (columnas apiladas SVG con leyenda, tooltip y tabla; paleta validada en claro y oscuro), `runs/AiUsageCard.tsx`, `useAi.ts` (periodo, zona), `AiSettingsPage` (variable sin sustituta), i18n |
| Tests | Backend: `tests/jobs/test_ai_usage.py` (nuevo), `test_ai.py`, `test_ai_domain.py`, `test_migrations.py` (`0025`); frontend: `admin/ai.test.tsx`, `runs.test.tsx`; e2e `ai.spec.ts` |
| Docs | `docs/guides/ia.md`, notas fechadas al final de ADR-014 y ADR-004, `CHANGELOG.md`; OpenAPI y `schema.d.ts` regenerados |

## AUDIT_CODE (2026-11-22)

Comprobado: backend `ruff`, `mypy`, `pytest` completo (693 passed antes de los últimos ajustes; los ficheros tocados
después, 60 + 6 passed), `export_openapi.py --check`; frontend `prettier`, `tsc -b`, `eslint`, `vitest` (171); web
`zensical build --strict`.

| Id | Hallazgo | Estado |
|---|---|---|
| C1 | El consumo se guardaba después de cerrar el run: el detalle podía recargarse sin él | Corregido: se guarda antes de `queue.finish` |
| C2 | El gráfico recibía solo los días con consumo y los ponía seguidos: el eje de tiempo engañaba | Corregido: días vacíos con ceros (hasta 400 días en «todo») |
| C3 | `github_copilot_usage_config_from_env()` emite dos avisos (la función y la configuración) | Aceptado: mismo mensaje; el test lo comprueba |
| C4 | «Todo» carga todas las filas del periodo para agregarlas | Aceptado: una fila por run y tarea |
| C5 | Gráfico sin revisar a ojo (claro, oscuro, móvil) | **Pendiente** con la app levantada |
| C6 | e2e adaptados (`ai.spec.ts`) sin ejecutar | **Pendiente** con la imagen de `feature/2.1` |

Veredicto AUDIT_CODE: **GO_CONDICIONAL** (C5 y C6).
