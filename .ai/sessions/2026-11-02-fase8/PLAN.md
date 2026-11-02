# PLAN — Fase 8: IA, clasificación, manifiestos y uso (0.9.0)

## 1. Historias y DoD

| ID | Historia | Hecho cuando |
|---|---|---|
| WB-8.1 | Como admin de instancia, configuro las **5 familias de IA** (clasificación de dominio, clasificación de taxonomía, borrador de manifiesto, uso de LiteLLM, uso de GitHub Copilot) | Tabla `ai_settings` con los secretos cifrados (MultiFernet); `GET/PUT /admin/ai-settings[/{family}]` nunca devuelve un secreto (solo `configured` + últimos 4); origen `db`/`env`/`none`; auditoría sin valores secretos; CLI `rotate-secrets` |
| WB-8.2a | Como editor, **construyo el contexto con IA**: lo que las reglas dejan sin clasificar se envía al servicio de IA | `context_build` con `ai_classification: true`; el job descifra solo la familia que necesita (1 eje → `litellm_classification`, plantilla o manifiesto → `litellm_taxonomy_classification`) y la pasa como `*Config` (L-3, G3); timeout, reintentos y **presupuesto** de documentos por run; recuento en el resultado |
| WB-8.2b | Como editor, pido un **borrador de manifiesto con IA** a partir de una muestra de documentos | Run `taxonomy_draft` (sustituye a `POST .../taxonomy-manifest-draft`); el borrador va en el resultado del run y **no se guarda solo**: lo reviso en el editor y lo guardo con el `PUT` de la Fase 7 |
| WB-8.3 | Como admin, veo el **uso y coste** de LiteLLM y Copilot | `GET /admin/ai-usage` con caché corta en el proceso; una fuente sin configurar o que falla no rompe a la otra |
| WF-8.1 | Pantallas: configuración IA, panel de uso, interruptor «Clasificar con IA» y botón «Borrador con IA» en la página de contexto | Vitest (estados de carga/vacío/error/sin permiso) + E2E con servicio de IA sustituido |
| Paridad | Se cierran las tres últimas filas de la Fase 8 en `PARIDAD.md` | Queda pedir L-10 (deprecar la web integrada) en el repositorio de doc_organize |

DoD común del ROADMAP: migración con `downgrade`, tests de autorización (401/403/404 e IDOR), OpenAPI y cliente
regenerados, imagen y `/api/health` 200, E2E, guía de usuario, CHANGELOG, `TRACEABILITY.md` y filas de PARIDAD.

## 2. doc_organize

La fase pide **0.10.0 (L-3)**; está fijada la **0.13.0** (`doc_organize[ai,context,export,site]`, el extra `ai` ya
trae `httpx`). No hacen falta rodeos de versión. Firmas **verificadas** en el clon local (`v0.13.0-1-g8a0e35a`,
`src/doc_organize/ai/` y `core/models.py`):

- `LiteLLMClassificationConfig(base_url, virtual_key, model="claude-classifier", timeout_s=30.0)`,
  `LiteLLMTaxonomyClassificationConfig(...)` (mismos campos), `LiteLLMTaxonomyManifestDraftConfig(...,
  timeout_s=60.0)`, `LiteLLMUsageConfig(base_url, virtual_key, timeout_s=30.0)`,
  `GitHubCopilotUsageConfig(username, personal_access_token, timeout_s=30.0)`: modelos Pydantic de
  `doc_organize.core.models`.
- Clientes (`async with`, todos con `transport: httpx.AsyncBaseTransport | None = None`):
  - `DomainClassificationClient(config).classify(*, chunks_text, title, candidate_domains) -> DomainClassificationResult`.
  - `TaxonomyClassificationClient(config).classify(*, chunks_text, title, candidate_domains, candidate_material_types)
    -> TaxonomyClassificationResult`.
  - `TaxonomyManifestDraftClient(config).propose_manifest(*, documents: list[SampledDocument]) ->
    TaxonomyManifestDraftResult` (`domains`, `material_types`, `reasoning`).
  - `LiteLLMUsageClient(config).get_usage(*, key=None)` y `GitHubCopilotUsageClient(config).get_usage(*, year=None,
    month=None)` → `UsageSnapshot(source, period_start, period_end, items: list[UsageLineItem], raw)`;
    `UsageLineItem(date, product, sku, quantity, unit_type, cost_usd)`.
- Errores: `DomainClassification{,Auth,Connection}Error`, `TaxonomyClassification{,Auth,Connection}Error`,
  `TaxonomyManifestDraft{,Auth,Connection}Error`, `UsageSource{,Auth,Connection}Error` (`core.exceptions`). Sus
  mensajes llevan `base_url`, nunca la clave.
- `ContextBuilder().build(..., ai_classification_enabled=False, ai_classification_client=None, ...,
  taxonomy_manifest=None, taxonomy_classification_client=None, ...)`: con manifiesto usa solo el cliente de taxonomía;
  sin él, solo el de un eje y solo para lo que quedó sin clasificar. El progreso por documento llega por
  `on_progress` (fase `classification`).
- `select_document_sample(documents, sample_size) -> list[SampledDocument]` (`context.taxonomy_manifest_sampler`) y
  `render_taxonomy_manifest_markdown(manifest, *, reasoning, sample_document_count, total_document_count) -> str`
  (`context.taxonomy_manifest`).
- **No se usan** las `*_config_from_store_or_env` (obsoletas, se retiran en 1.0.0) ni `doc_organize.auth`: la web
  construye los `*Config` (G3).

### Huecos nuevos (para `DOC_ORGANIZE_GAPS.md`)

| G | Hueco | Rodeo en la web | Pedir |
|---|---|---|---|
| G33 | `ContextBuilder` captura los errores de IA **por documento** y sigue: con una clave mala o el proxy caído hace una petición por cada documento pendiente (coste, tiempo, log lleno) | El cliente que se le pasa es un envoltorio (subclase en la capa anticorrupción) que corta tras el primer `*AuthError` y tras N errores de conexión seguidos: devuelve «sin dominio» sin llamar | Parar la Sub-fase B ante `*AuthError` (o un `max_failures`) y avisar en el resultado |
| G34 | Los clientes no reintentan ni tienen presupuesto (número de llamadas o tokens por operación) | Reintentos de conexión con `httpx.AsyncHTTPTransport(retries=n)` por el parámetro `transport`; el mismo envoltorio cuenta las llamadas y deja de llamar al llegar al presupuesto | `max_calls`/presupuesto y reintentos con *backoff* en `AiHttpClientBase` |
| G35 | `ContextBuilder` no dice cuántos documentos clasificó la IA ni cuántos fallaron (solo lo escribe en el log) | Lo cuenta el envoltorio; `classified_by == "ai"` de cada documento se proyecta en `context_documents` | Recuento de la Sub-fase B en `Context` |

## 3. Contrato HTTP (`/api/v1`)

Errores en *problem details* (RFC 9457); todo lo de `admin/` exige admin de instancia (401 sin sesión, 403 sin rol).

| Método | Ruta | Quién | Notas |
|---|---|---|---|
| GET | `/admin/ai-settings` | admin | `{encryption_configured, families: [{key, label, configured, fields: [{name, env_var, secret, required, source: db\|env\|none, value (solo no secretos), hint (solo secretos: «…ab12» o «***»)}]}]}` |
| PUT | `/admin/ai-settings/{family}` | admin + CSRF | `{fields: {name: str \| null}}`: ausente = no tocar; `null` o `""` = borrar el valor guardado. 404 familia desconocida; 422 campo ajeno o `base_url` no válida; 409 `encryption_not_configured` al guardar un secreto sin `DOW_FERNET_KEYS`. Audita `ai_settings.update` con los **nombres** de los campos cambiados (valores no secretos antes/después; secretos nunca) |
| GET | `/ai/status` | cualquier usuario | `{families: {key: configured}}` sin valores: lo usa la página de contexto para activar el interruptor y el botón |
| GET | `/admin/ai-usage?refresh=` | admin | `{sources: [{source: litellm\|github_copilot, configured, fetched_at, period_start, period_end, items: [...], total_cost_usd, error: null \| ai_auth \| ai_connection \| ai_error}]}`. Caché en el proceso de 5 min por fuente (`refresh=true` la salta, como mucho 1 vez/30 s); `raw` nunca se devuelve. Timeout 10 s |
| POST | `/projects/{id}/runs` `context_build` | editor | Parámetro nuevo `ai_classification: bool = false`. Si es `true`, al encolar se comprueba que la familia que toca está configurada (422 `ai_not_configured`) |
| POST | `/projects/{id}/runs` `taxonomy_draft` | editor | `{sample_size: 1–60 = 25}`; 422 `ai_not_configured`. No escribe en el proyecto (no toma el bloqueo de escritura) |
| GET | `/runs/{id}` | miembro | El resultado de `taxonomy_draft` trae `{manifest_markdown, reasoning, sample_documents, total_documents, domains, material_types}`; el de `context_build` añade `{ai: {enabled, calls, classified, failed, stopped: null \| auth \| connection \| budget}}` |

Validación de `base_url` (lado servidor): esquema `http`/`https`, con host, sin usuario/contraseña, sin *query* ni
fragmento, ≤ 2048. Copilot no tiene `base_url` (la API de GitHub es fija en el cliente).

SSE: sin eventos nuevos; `context_build` ya emite progreso de la fase `context_classify` y `taxonomy_draft` emite
`ai_sample` → `ai_request` → hecho.

## 4. Modelo de datos — migración `0008_ai`

`ai_settings` (de instancia, como en la web integrada; los tenants llegan en la Fase 9):

| Columna | Tipo | Notas |
|---|---|---|
| `family` | `String(64)` PK | una de las 5 claves |
| `field` | `String(32)` PK | `base_url`, `virtual_key`, `model`, `username`, `pat` |
| `value` | `Text` nullable | solo campos no secretos |
| `ciphertext` | `Text` nullable | token Fernet; solo secretos (`CHECK` exactamente uno de los dos) |
| `updated_by_id` | FK `users.id` nullable | |
| `updated_at` | `UTCDateTime` | |

`context_documents.classified_by` (`String(8)`, nullable: `rules`/`ai`) para mostrar qué decidió la IA.
Ajustes administrables nuevos (ADR-012, `app_settings`): `ai_timeout_seconds` (5–300, 30), `ai_retries` (0–5, 2),
`ai_max_documents_per_run` (1–100 000, 500). `downgrade` borra la tabla y la columna.

## 5. Rutas del sistema de ficheros

Ninguna ruta nueva llega por la API. `taxonomy_draft` reúne los documentos con el mismo `source_folders` +
`converted_documents` de `context_build` (resolvedor de ubicaciones, origen `ro` basta: no escribe nada).
`context_build` con IA no cambia sus rutas. Las rutas que vuelven en el resultado son relativas (el `folder` de
`SampledDocument` lo calcula la librería sobre `source_path`: se reescribe a relativo con `DocumentNamer`).

## 6. Secretos (ADR-004)

- `core/crypto.py`: `MultiFernet` de `DOW_FERNET_KEYS` (la primera cifra, todas descifran); `cryptography` como
  dependencia directa fijada en `uv.lock`.
- Precedencia: valor en `ai_settings` > variable `DOC_ORGANIZE_*` del entorno (mismos nombres que la web integrada).
- La API descifra solo para calcular el `hint` y para el panel de uso. El subproceso del job descifra solo la familia
  de su operación y construye el `*Config` dentro de la capa anticorrupción. Nunca van a `runs.params`, `run.json`,
  `run.log`, eventos SSE ni respuestas.
- Errores: solo `type(exc).__name__` y un código (`ai_auth`, `ai_connection`, `ai_error`) en el run y en el log; el
  mensaje de la librería (lleva `base_url`) no se guarda.
- Un token que no descifra (clave rotada sin volver a cifrar) → la familia sale como «no configurada» con aviso
  `undecryptable`, sin 500.
- `python -m app.cli rotate-secrets`: vuelve a cifrar todas las filas con la primera clave (`MultiFernet.rotate`).

## 7. Integración y jobs

- `integrations/doc_organize/ai.py` (único punto que importa `doc_organize.ai`): `FAMILIES` (spec de campos y
  variables de entorno), constructores de `*Config`, `GuardedDomainClient`/`GuardedTaxonomyClient` (subclases con
  presupuesto, corte por `AuthError` y por errores de conexión seguidos, contadores: G33–G35), `draft_manifest(...)`,
  `fetch_usage(...)`. Transporte `httpx.AsyncHTTPTransport(retries=ai_retries)`.
- `integrations/doc_organize/context.py`: `ContextRequest.ai` (`AiClassification | None` con el `*Config`, no
  serializable) → `build(..., ai_classification_enabled=True, ai_classification_client=… |
  taxonomy_classification_client=…)` y `ContextDoc.classified_by`.
- `domain/ai/`: `settings.py` (leer/guardar/borrar, `hint`, origen, auditoría), `usage.py` (caché TTL en el proceso
  con candado), `errors.py`.
- `jobs/operations/context.py`: con `ai_classification` construye la config en el subproceso; `taxonomy_draft` nueva
  en `jobs/operations/ai.py` (`min_role="editor"`, cola `cpu`, sin artefactos, no es escritura).
- Operaciones `context_build` con IA y `taxonomy_draft`: aviso en la UI de que se envía el contenido de los
  documentos al servicio de IA configurado.

## 8. Frontend

| Pantalla | Sustituye a | Contenido |
|---|---|---|
| `/admin/ai-settings` | `ai_settings.html.j2` | Una tarjeta por familia: estado, campos con origen (BD/entorno/sin valor), secretos con `PasswordInput` vacío + «configurado …ab12» y «Borrar valor guardado»; aviso si el cifrado no está configurado (no deja guardar secretos) |
| `/admin/ai-usage` | — (nuevo) | Una tarjeta por fuente: periodo, coste total, tabla de líneas (fecha, producto, cantidad, unidad, coste); «Actualizar»; estados sin configurar / error |
| `ContextPage` | `context.html.j2` (toggle IA, botón de borrador) | Interruptor «Clasificar con IA» (desactivado con explicación si la familia no está configurada) en el formulario de construir; columna «IA» en la lista de documentos; botón «Borrador con IA» → run con progreso → el borrador se carga en el editor del manifiesto, sin guardar |
| Menú admin | — | Enlaces «Configuración IA» y «Uso de IA» |

Hooks en `features/admin/useAi.ts` y `features/context/useContext.ts`; textos en `i18n/es`.

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Fuga de secretos (respuestas, logs, `run.json`, errores) | Solo `hint`; tests que buscan la clave en respuestas, BD sin cifrar, `run.log`, `run.json` y eventos |
| SSRF por `base_url` (admin) | Solo admin de instancia; validación de URL; la clave solo viaja a esa URL; aceptado como riesgo de admin (documentado en ADR-014) |
| Salida de datos: el contenido de los documentos sale al servicio de IA | Opt-in por run, aviso en la UI y en la guía; nunca por defecto |
| Coste descontrolado (100 000 documentos) | `ai_max_documents_per_run` (500), corte por error de autenticación, cancelación entre documentos (L-2) |
| Pérdida de `DOW_FERNET_KEYS` | Documentado: hay que reintroducir las credenciales; `rotate-secrets` para rotar |
| Panel de uso en la API (no es un job) | Lectura HTTP ligera con timeout 10 s, caché 5 min y límite de refresco: no es una «operación pesada» (regla 4); ADR-014 |
| `config.db` y clave en el mismo backup | El backup de `config.db` no incluye `secrets/`; la guía de backup lo dice |

## 10. Pruebas

- **Unit**: cifrado/rotación/token inválido; `hint` (≤ 4 caracteres → `***`); precedencia BD > entorno; validación
  de `base_url`; envoltorios con presupuesto, corte por auth y por conexión (`httpx.MockTransport`, sin red).
- **API**: GET/PUT de ajustes (401/403, 404 familia, 422, 409 sin cifrado, auditoría sin secretos, la clave nunca en
  la respuesta ni en `config.db` en claro); `/ai/status` para un usuario normal; `/admin/ai-usage` con clientes
  sustituidos (caché, error de una fuente); `context_build` y `taxonomy_draft` con 422 `ai_not_configured`, rol
  `viewer` → 403, IDOR → 404; jobs con la capa anticorrupción sustituida y transporte falso.
- **Frontend**: Vitest de las dos páginas admin y del interruptor y el borrador en `ContextPage`.
- **E2E**: Playwright con un servidor LiteLLM falso local (respuestas fijas) configurado como `base_url`: guardar
  configuración → construir contexto con IA → pedir borrador → guardarlo como manifiesto. Documentos sintéticos.

## AUDIT_PLAN

**Contraste con la arquitectura y las reglas**

- Regla 1 (no tocar doc_organize): G33–G35 van a `DOC_ORGANIZE_GAPS.md` con su rodeo.
- Regla 2 (no inventar APIs): firmas leídas en el clon `v0.13.0`. El `.whl` instalado es esa misma versión.
- Regla 3 (capa anticorrupción): `doc_organize.ai` solo en `integrations/doc_organize/ai.py`. Los envoltorios son
  subclases de los clientes de la librería y viven en esa misma carpeta.
- Regla 4 (operaciones pesadas como jobs): clasificar y hacer el borrador son jobs. El panel de uso, no: es una
  lectura corta con caché (decisión a confirmar).
- Regla 5 (resolvedor de ubicaciones): sin rutas nuevas.
- Regla 6 (secretos): cubierta por la §6 y sus tests.
- Regla 7 (mover o borrar): no aplica, nada mueve ni borra ficheros.
- Regla 8 (contrato primero): `export_openapi` + `gen:api` van en el mismo cambio.
- ADR-004 se implementa entero (MultiFernet, precedencia, `rotate-secrets`, nada en claro). ADR-012 suma tres
  ajustes nuevos. ADR-006 no cambia.
- **ADR-014 nuevo** «Uso de servicios de IA»: opt-in por run, presupuesto, `base_url` solo de un admin, panel de uso
  en la API con caché, los secretos solo se descifran en el subproceso.
- Security Reviewer **obligatorio** en AUDIT_CODE, porque la fase toca secretos.

**Huecos nuevos de doc_organize**: G33, G34 y G35 (§2). Ninguno bloquea la fase.

**Filas de `PARIDAD.md`**: `ai_settings.html.j2`, `GET /api/admin/ai-settings`,
`PUT /api/admin/ai-settings/{family_key}` y `POST .../context/taxonomy-manifest-draft` (run `taxonomy_draft`). Con
ellas, todas las filas de las fases 0–8 quedan cerradas. Las de la Fase 9 (roles y tenants) siguen abiertas, así que
L-10 (deprecar la web integrada) **no** se puede pedir aún si «cierre de paridad» significa todas las filas. Ver la
decisión D1.

**Fuera de alcance**: tenants y ajustes IA por tenant (Fase 9); cifrado de otros secretos; rate limiting general
(Fase 10).

**Decisiones a confirmar por el mantenedor**

- D1: el «cierre de paridad → L-10» del ROADMAP se entiende así: la Fase 8 cierra la paridad **funcional**
  (documentos, contexto e IA), y L-10 se pide ya en doc_organize con las filas de la Fase 9 como pendientes. ¿O se
  espera a la Fase 9?
- D2: el panel de uso es **solo para admin**, en la API y con caché (no es un job).
- D3: presupuesto por defecto: 500 documentos con IA por run, con el ajuste administrable
  `ai_max_documents_per_run`.
- D4: `taxonomy_draft` y `context_build` con IA exigen el rol `editor` (como `context_build`), no `owner`.

**Veredicto: `GO_CONDICIONAL`**: listo para implementar cuando se confirmen D1–D4. No hay bloqueos de versión ni
de seguridad.
