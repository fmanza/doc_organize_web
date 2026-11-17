# PLAN + AUDIT_PLAN — «Probar conexión» en Configuración IA (2026-11-17)

Skill: `new-feature` (web). Solo PLAN y AUDIT_PLAN; sin implementar.

## Inputs

| Campo | Valor |
|---|---|
| Objetivo | Un botón «Probar conexión» en cada tarjeta de **IA › Configuración** que dice, sin guardar nada, si la URL, la clave y (opcional) el modelo funcionan |
| Rutas | `backend/app/integrations/doc_organize/ai.py`, `backend/app/domain/ai/connection_test.py` (nuevo), `backend/app/domain/ai/settings.py`, `backend/app/api/v1/ai.py`, `backend/app/api/v1/schemas.py`, `backend/app/domain/identity/audit.py`; `frontend/src/features/admin/AiSettingsPage.tsx`, `useAi.ts`, `ai.test.tsx`, `i18n/es/features.json`; `docs/guides/ia.md`, `CHANGELOG.md` |
| Contrato HTTP | `POST /api/v1/admin/ai-settings/{family}/test` (ver abajo) |
| Pantallas | Tarjeta de cada familia en `/admin/ai/settings`: botón, resultado en línea (correcto, error, en curso) |
| Permisos | Administrador de instancia (`InstanceAdmin`), el mismo que ve y guarda la configuración |
| doc_organize | `LiteLLMUsageClient.get_usage()` (`GET /key/info`), `GitHubCopilotUsageClient.get_usage(year, month)`, `DomainClassificationClient.classify(...)`; firmas verificadas en 1.6.0. Sin cambios en la librería |
| Restricciones | Sin dependencias nuevas, sin migración, sin colas: llamada corta en el proceso de la API, como el panel de uso |

## PLAN

### Qué se prueba en cada familia

| Familia | Prueba básica (sin coste) | Prueba del modelo (opcional, gasta tokens) |
|---|---|---|
| `litellm_classification`, `litellm_taxonomy_classification`, `litellm_taxonomy_manifest_draft`, `litellm_enrichment` | `GET /key/info` con su `base_url` y `virtual_key` (`LiteLLMUsageClient`): servidor alcanzable y clave válida. Si `/key/info` trae `models` y no incluye el modelo configurado, aviso «la clave no tiene acceso a este modelo» | Una clasificación mínima (`DomainClassificationClient.classify` con texto «Prueba de conexión» y un dominio candidato) con su URL, clave y modelo: confirma que el modelo existe y responde |
| `litellm_usage` | `GET /key/info` (lo mismo que hace el panel de uso) | — |
| `github_copilot_usage` | `get_usage` del mes en curso: usuario y PAT válidos y con permiso de facturación | — |

**Recomendación:** prueba básica siempre; la del modelo, solo si el usuario la pide con un segundo botón «Probar el
modelo». Así una prueba rutinaria no cuesta tokens, y quien acaba de cambiar el modelo puede confirmarlo.

### Qué valores se prueban

Los del **formulario**, sin guardarlos: lo que el usuario ha escrito y, para lo que no ha tocado, lo guardado o la
variable `DOC_ORGANIZE_*` (misma precedencia que `resolve`). Así se puede probar antes de guardar.

**Regla de seguridad** (condición del AUDIT_PLAN): si la `base_url` del formulario es distinta de la efectiva, la clave
guardada **no** se usa: hay que escribirla en el formulario. Si no, quien tenga una sesión de admin podría mandar la
clave guardada a un servidor suyo.

### Contrato HTTP

`POST /api/v1/admin/ai-settings/{family}/test`, con CSRF como el resto de escrituras.

```jsonc
// entrada: mismos campos que PUT (ausente = valor efectivo; "" = sin valor)
{ "fields": { "base_url": "https://litellm.example", "model": "claude-classifier" }, "model_check": false }

// salida 200 (la prueba se hizo, haya ido bien o mal)
{
  "ok": false,
  "error": "ai_auth",              // ai_auth | ai_connection | ai_error | ai_model | null
  "model_access": "unknown",       // ok | denied | unknown  (solo familias con modelo)
  "model_checked": false,
  "elapsed_ms": 412,
  "tested_at": "2026-11-17T09:00:00Z"
}
```

Errores: 400 campo ajeno o valor no válido (las mismas validaciones que `update_family`); 404 familia; 409
`ai_not_configured` (falta un obligatorio); 422 `secret_required` (cambió la URL y no se escribió la clave); 429
`ai_test_too_soon` (menos de 10 s desde la última prueba de esa familia); 401/403 como el resto de `/admin`.

### Cambios por capa

1. **Integración** (`integrations/doc_organize/ai.py`):
   - `test_connection(connection, *, model_check) -> ConnectionCheck`: elige la prueba de la tabla, mide el tiempo y
     traduce las excepciones con `_ai_error`.
   - Lee `models` del `raw` de `/key/info`, que no sale del módulo.
   - Sin URL ni clave en mensajes o logs.
2. **Dominio** (`domain/ai/connection_test.py`, nuevo):
   - Valida los campos con `_validate`, los combina con los efectivos y aplica la regla de la URL.
   - Construye la `AiConnection` con un timeout de como mucho 10 s y 0 reintentos (como `usage.py`).
   - Limita a una prueba cada 10 s por familia, en memoria y por proceso.
   - Audita `ai_settings.test` con la familia, el resultado y `model_check`; sin valores, ni siquiera los no secretos.
3. **API** (`api/v1/ai.py`, `schemas.py`): `AiTestIn` y `AiTestOut`; `def` síncrono (como `get_ai_usage`, en el
   threadpool) con `asyncio.run` dentro de la integración.
4. **Frontend** (`AiSettingsPage.tsx`, `useAi.ts`):
   - `useTestAiFamily(family)`, una mutación que no invalida nada.
   - Botones «Probar conexión» y, en las familias con modelo, «Probar el modelo».
   - Resultado en un `Alert` con `role="status"`: «Conexión correcta (412 ms)», o el error traducido con una pista.
   - Aviso «La clave no tiene acceso a este modelo».
   - Se borra el resultado al editar el formulario.
   - Botones desactivados mientras se prueba y si faltan obligatorios.
5. **Contrato**: OpenAPI exportado y `schema.d.ts` regenerado.
6. **Docs**: sección «Probar la conexión» en `docs/guides/ia.md`, CHANGELOG.

### Tests

- **Backend, integración**, con `httpx.MockTransport`, como los tests del panel de uso:
  - 200 → `ok`;
  - 401 → `ai_auth`;
  - timeout → `ai_connection`;
  - `models` sin el modelo → `model_access=denied`;
  - prueba del modelo → una sola petición a `/chat/completions`.
- **Backend, API**:
  - 403 para quien no es admin de instancia y 404 para una familia desconocida;
  - 409 si falta un obligatorio y 422 `secret_required` si cambió la URL sin escribir la clave;
  - 429 si se repite antes de 10 s;
  - no guarda nada (`ai_settings` sin cambios);
  - audita sin valores;
  - la clave no aparece en la respuesta, los logs ni la auditoría.
- **Frontend**:
  - prueba con los valores del formulario sin guardar;
  - muestra el resultado correcto y el de error;
  - la prueba del modelo solo aparece en las familias con modelo;
  - borra el resultado al editar.

## AUDIT_PLAN

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| F1 | `/key/info` no prueba el modelo: «correcto» no garantiza que la clasificación funcione | Texto claro («servidor y clave correctos») y botón aparte «Probar el modelo»; aviso si `models` no incluye el modelo |
| F2 | Algunas claves de LiteLLM no pueden leer su `/key/info` (403 por política del proxy) aunque sirvan para inferencia | `ai_auth` en la prueba básica sugiere «prueba el modelo»; la prueba del modelo es la referencia |
| F3 | El borrador de manifiesto usa un plazo largo (`ai_draft_timeout_seconds`); la prueba con 10 s puede dar timeout aunque luego funcione | La prueba básica no depende del modelo; la del modelo usa una petición mínima, que responde mucho antes que un borrador |
| F4 | Un PAT de GitHub sin permiso de facturación falla aunque sea válido | Mismo comportamiento y mensaje que el panel de uso, que ya lo necesita |
| F5 | Probar con valores sin guardar y luego no guardar confunde | El resultado dice «con los valores del formulario» y se borra al editar |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| T1 | Llamada de red en el proceso de la API | Timeout de 10 s como mucho, 0 reintentos, `def` en el threadpool; mismo patrón que `/admin/ai-usage` |
| T2 | El límite de 10 s en memoria no se comparte entre procesos | Basta para evitar dobles clics y bucles; el endpoint es solo para admins y ya está auditado. Documentarlo |
| T3 | `_validate` y `resolve` son privados o internos de `settings.py` | Exponer en `settings.py` una función `effective_values(db, settings, key, overrides)` reutilizada por `connection` y por la prueba; sin cambiar lo que devuelve `resolve` |
| T4 | Contrato: endpoint nuevo y aditivo | OpenAPI y cliente regenerados en el mismo cambio |
| T5 | La librería no tiene `test_connection`; se reutilizan clientes pensados para otra cosa | Rodeo documentado; proponer **G45** a doc_organize, un `check_connection()` por cliente que pruebe la URL, la clave y el modelo con `GET /v1/models`. Sin bloquear esta funcionalidad |

### Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| S1 | **Exfiltración de la clave**: probar con otra `base_url` usando la clave guardada | 422 `secret_required`: con una URL distinta de la efectiva, la clave tiene que venir en la petición. Test obligatorio |
| S2 | SSRF: el servidor hace peticiones a la URL que diga el admin (red interna, metadatos de la nube) | Solo admin de instancia, que ya puede guardar esa URL; misma validación (`validate_base_url`: http/https, sin credenciales en la URL). No se devuelve el cuerpo de la respuesta, solo un código, para no convertirlo en un lector de URLs internas. Documentarlo como riesgo aceptado |
| S3 | Fuga de la clave en logs, mensajes o auditoría | Errores reducidos a `AiErrorCode`; `httpx` silenciado (`core/logging.py`); auditoría sin valores; test que busca la clave en la respuesta, en `caplog` y en `audit_log` |
| S4 | Abuso: pruebas en bucle que gastan tokens con la prueba del modelo | 429 cada 10 s por familia, `model_check` explícito y auditado |
| S5 | CSRF | `POST` con el token CSRF, como el resto de `/admin` |

### Simplificaciones posibles

- **Probar solo lo guardado** (sin valores del formulario): elimina S1 y la mitad de la validación, pero obliga a guardar
  para probar, y una configuración rota queda activa mientras tanto. No recomendada.
- **Sin prueba del modelo**: solo `/key/info`. Más simple y sin coste, pero no detecta un alias de modelo mal escrito,
  que es el fallo más habitual. Válida como primera entrega si se quiere reducir alcance.
- **Sin límite de frecuencia**: aceptable con solo la prueba básica (sin coste); necesario si hay prueba del modelo.

### Veredicto: **GO_CONDICIONAL**

Condiciones:

1. S1: la clave guardada nunca va a una `base_url` distinta de la efectiva (422 `secret_required`), con test.
2. S3: ningún valor secreto en la respuesta, los logs ni la auditoría, con test.
3. Decidir con el mantenedor:
   - (a) probar con los valores del formulario (recomendado) o solo con lo guardado;
   - (b) si se incluye «Probar el modelo» en esta entrega (recomendado).

> **Estado (2026-11-17)**: implementado, sin commit. Decisiones: valores del formulario y «Probar el modelo» incluido
> (las recomendadas; el mantenedor pidió IMPLEMENT sin elegir). Cambios respecto al plan:
> - Falta un obligatorio → 422 `ai_not_configured` (el error que ya existía), no 409.
> - Con `model_check`, un 401/403 en `/key/info` no corta: decide la prueba del modelo (F2).
> - Un error genérico de la prueba del modelo (HTTP 400/404 de un alias que no existe) se informa como `ai_model`.
> - Funciones `check_connection` y `probe_family` (no `test_*`: pytest las recogería al importarlas).
> - G45 (método de prueba en doc_organize) queda como propuesta, sin abrir en `DOC_ORGANIZE_GAPS.md`.
