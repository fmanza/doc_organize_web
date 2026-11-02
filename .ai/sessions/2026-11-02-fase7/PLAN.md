# PLAN — Fase 7: Contexto y taxonomías (0.8.0)

## 1. Historias y DoD

| ID | Historia | Hecho cuando |
|---|---|---|
| WB-7.1 | Como admin de instancia, gestiono **plantillas de taxonomía**: veo las incluidas en doc_organize y creo, edito y borro las personalizadas | Tabla `taxonomy_templates` (solo personalizadas; las incluidas se leen de la librería); CRUD admin con validación de doc_organize; cualquier usuario las lista para elegir una |
| WB-7.2a | Como editor, **construyo el contexto** del proyecto: clasificación por dominios (descubiertos, catálogo propio, plantilla o manifiesto del proyecto), copia reorganizada y sitio | Run `context_build` con progreso SSE (clasificar → reorganizar → sitio); documentos que no se copian, como avisos; resumen en `config.db` |
| WB-7.2b | Veo el contexto: dominios, documentos por dominio y sin clasificar, paginados | `GET /projects/{id}/context` y listados paginados en servidor, con rutas relativas |
| WB-7.2c | Como propietario, **borro el contexto** (copia reorganizada, `context.json`, `domains/`, sitio) | Run `context_delete` con vista previa (`dry_run`), nombre tecleado, rol `owner` y ubicación `rw` (regla 7) |
| WB-7.2d | Edito el **manifiesto de taxonomía** del proyecto (`taxonomy_manifest.md`) | `GET/PUT /projects/{id}/context/taxonomy-manifest`, validado con `parse_taxonomy_template` |
| WB-7.3 | Navego el **sitio Zensical** sin que sus scripts corran en el origen de la app | Sitio servido por URL con token firmado, CSP `sandbox` propia e iframe `sandbox`; ADR-010 redactado |
| WF-7.1 | Páginas: contexto del proyecto, admin de plantillas, visor del sitio | Vitest + E2E: construir (plantilla incluida) → ver dominios → abrir sitio → borrar |
| M-EXP (opcional) | Descargo e importo plantillas como Markdown | `GET /taxonomy-templates/{name}/download` y botón «Importar .md» que rellena el editor (validación en el servidor) |

DoD común del ROADMAP: migración con `downgrade`, tests de autorización (401/403/404 e IDOR), OpenAPI y cliente
regenerados, imagen y `/api/health` 200, E2E, guía de usuario, CHANGELOG, `TRACEABILITY.md` y filas de PARIDAD.

## 2. doc_organize

El ROADMAP pedía 0.11.0 (L-8). L-8 se aplazó y salió, junto con L-8a…L-8c, en la **0.13.0** (publicada el
2026-11-02; wheel `sha256:381ce668…c728`). La fase se cierra con esa versión, y la columna «Requiere» se corrige a
`0.13.0 (L-8, L-8a…L-8c)`. Firmas **verificadas** en el tag `v0.13.0` (CHANGELOG, «Firmas finales»):

- `ContextBuilder().build(project, documents: list[ConversionResult], candidate_domains=None, threshold=…,
  ai_classification_enabled=False, ai_classification_client=None, output_folder_name="organizado",
  on_ai_progress=None, taxonomy_manifest=None, taxonomy_classification_client=None, taxonomy_template_name=None, *,
  on_progress=None, cancel_token=None) -> Context`. Con manifiesto clasifica en dos ejes sin IA. La IA queda
  desactivada hasta la Fase 8.
- `ContextRegistry().load_context/save_context/delete_context(project)`: `context.json` y `domains/<slug>/` en
  `project.root_path`.
- `Reorganizer().reorganize(project, context, on_document_copied=None, *, on_document_failed=None) -> Path`, con los
  callbacks `(index, total, source_path[, error])`.
  - Copia sin seguir enlaces (`O_NOFOLLOW`).
  - Un documento que falla no para al resto.
  - `delete_output(project, context)` y `check_output_root(path)`.
- `SiteGenerator().generate(project, context, *, build=True, site_dir=None, timeout=None) -> SiteResult`, más
  `build_site(project, *, timeout)` y `delete_site(project, *, site_dir)`.
  - Lanza `SiteBuildError` si falta zensical, el build falla o se pasa de tiempo.
  - Ejecuta `python -m zensical` del mismo entorno.
  - `zensical.toml` y `.cache/` quedan en la raíz.
- `ProjectLayout`: `context_file`, `domains_dir`, `taxonomy_manifest_file`, `site_dir`, `site_config_file`,
  `site_cache_dir`, `legacy_mkdocs_config_file` y `reorganized_dir(name)`. También `RESERVED_OUTPUT_FOLDER_NAMES` y
  `validate_output_folder_name(name)`.
- `parse_taxonomy_template(text, *, source=…) -> TaxonomyManifest`, que lanza `TaxonomyTemplateError`.
- `render_taxonomy_template(manifest, body="") -> str`, `list_builtin_templates() -> list[TaxonomyTemplateSummary]` y
  `load_builtin_template(name)`.
- `load_taxonomy_manifest(project)` y `save_taxonomy_manifest(project, raw)`.
- `ConversionResult(source_path, markdown_path, json_path, images_dir, success)`.
  - La web los reconstruye desde la caché de cada carpeta: entradas `SUCCESS` cuyo original exista.
  - Rutas de salida con `resolve_output_paths`/`resolve_images_dir` (ya usado en `cache.output_paths`).
  - `PENDIENTE DE VERIFICAR` en IMPLEMENT: el campo de estado de `CacheEntry` en 0.13.0.

### Huecos nuevos

| ID | Hueco | Rodeo |
|---|---|---|
| G30 | `Reorganizer` sobrescribe en `organizado/` dos documentos con el mismo `stem` en el mismo dominio y tipo (limitación conocida de doc_organize) | La web cuenta las colisiones antes de reorganizar y las muestra como aviso en el run y en la página. Pedir L-8d (desambiguar) para una versión posterior; no bloquea, porque los originales no se tocan |

## 3. Contrato HTTP (`/api/v1`)

| Método | Ruta | Rol | Notas |
|---|---|---|---|
| GET | `/taxonomy-templates` | autenticado | Incluidas y personalizadas: `name`, `title`, `description`, `builtin`, `updated_at` |
| GET | `/taxonomy-templates/{name}` | autenticado | `markdown` y resumen (dominios y tipos de material) |
| PUT | `/taxonomy-templates/{name}` | admin | Crea o sustituye `{markdown}`. 422 problem si no valida, 409 si el nombre es de una incluida, nombre `[a-z0-9-]{1,64}` y ≤ 256 KiB. Auditado |
| DELETE | `/taxonomy-templates/{name}` | admin | 409 si es incluida. Auditado |
| GET | `/taxonomy-templates/{name}/download` | autenticado | `text/markdown`, `Content-Disposition: attachment` (M-EXP) |
| GET | `/projects/{id}/context` | viewer | Resumen: carpeta, dominios con recuentos, sin clasificar, fallidos, colisiones, `site_built`, plantilla y run que lo construyó. 404 `context-not-found` |
| GET | `/projects/{id}/context/domains/{slug}/documents` | viewer | `limit/offset`; título, tipo, tipo de material, ruta relativa del original y de la copia |
| GET | `/projects/{id}/context/unclassified` | viewer | `limit/offset` |
| GET, PUT | `/projects/{id}/context/taxonomy-manifest` | viewer / editor | PUT valida y escribe con `save_taxonomy_manifest`. Exige destino `rw` y que no haya ninguna escritura activa en el proyecto (409); se audita |
| POST | `/projects/{id}/context/site-session` | viewer | Devuelve `{url, expires_at}` con un token firmado. 404 si no hay sitio construido |
| GET | `/site/{token}/{path}` (fuera de `/api`) | token | Ficheros del sitio con su propia CSP (ver §6) |
| POST | `/projects/{id}/runs` | — | Operaciones nuevas `context_build` y `context_delete` (abajo) |

- `context_build` (`editor`, cola `cpu`, escritura):
  - `output_folder_name`: solo en la primera construcción; luego se rechaza si difiere (como la web integrada).
  - `catalog`:
    - `{"kind": "discover"}`;
    - `{"kind": "domains", "domains": [...]}` (≤ 100);
    - `{"kind": "template", "name"}`;
    - `{"kind": "manifest"}` (el del proyecto).
  - `threshold`, `build_site: bool = True`.
  - Las combinaciones incompatibles, como las rechaza la web integrada, devuelven 422.
- `context_delete` (`owner`, destructiva): `dry_run`, `preview_run_id`, `confirm_name`. La vista previa cuenta los
  ficheros y bytes de la carpeta reorganizada, `domains/` y el sitio.
- Eventos SSE: los del motor actual, con las fases `prepare`, `classify`, `reorganize` (progreso por documento),
  `site` y `save`. Los documentos que fallan llegan como avisos con la ruta relativa.

## 4. Modelo de datos — migración `0007_context`

- `taxonomy_templates`: `id`, `tenant_id` (FK, `default`), `name` (único por tenant), `title`, `description`,
  `markdown` (Text), `created_by`, `created_at`, `updated_at`. Las incluidas no se copian a la BD.
- `project_contexts` (PK `project_id`, cascada): `output_folder_name`, `catalog_kind`, `taxonomy_template_name`,
  `domains_count`, `documents_count`, `unclassified_count`, `failed_count`, `collisions_count`, `site_built`,
  `built_by_run_id`, `built_at`.
- `context_documents` (PK `project_id` + `seq`; índice `project_id, domain_slug`): `domain_slug`, `domain_name`,
  `material_type`, `title`, `document_type`, `source_rel` (`<carpeta>/<ruta>`), `organized_rel`. Si `domain_slug`
  es NULL, el documento está sin clasificar.
- Las tablas del contexto son una proyección de `context.json` para paginar a 100 000 documentos sin leer la red en
  cada petición:
  - `context_build` las reescribe en una transacción al terminar;
  - `context_delete` las borra;
  - borrar o vaciar el proyecto también las borra.
- `downgrade` borra las tres tablas.

## 5. Rutas del sistema de ficheros

- Origen (lectura de originales) y destino (todo lo demás): siempre `project_paths`/`resolve_in`, con raíces reales
  resueltas una vez (doc_organize ≥ 0.12.1 falla con enlaces). Escribir exige destino `rw` (`require_rw`).
- El `Project` de doc_organize se construye con `root_path` en la carpeta del proyecto en el destino. En ella quedan
  `context.json`, `domains/`, `<organizado>/`, `zensical.toml`, `.cache/` y `site/`. La caché se lee del estado local
  (`ProjectLayout(state_root=…)`, ADR-005).
- `context.json` guarda rutas absolutas del contenedor. La web las convierte en relativas a la carpeta de origen o a
  la reorganizada antes de que lleguen a la BD; si alguna no cae dentro, la omite y lo registra en el log.
- Sitio:
  - `/site/{token}/{path}` resuelve `path` con `resolve_within` sobre `<proyecto>/site` real y rechaza `..`, enlaces
    (`_no_links`) y directorios; un directorio sirve su `index.html`.
  - Tipos MIME con lista blanca (html, css, js, json, svg, png, jpg, gif, webp, woff2, ico, txt, xml).
  - El resto se sirve como `application/octet-stream` con `attachment`.

## 6. Sitio aislado (WB-7.3, ADR-010)

La cookie de sesión es `SameSite=Lax`. Un documento en `sandbox` (origen opaco) no la envía al pedir sus CSS y JS,
así que el sitio no se puede servir con la sesión. Propuesta:

- **URL con capacidad**: `POST site-session` devuelve `/site/{token}/`.
  - El token es HMAC-SHA256 con `app_secret_key` sobre `project_id`, el hash del id de sesión y la caducidad (≤ 1 h).
  - En cada petición se comprueban la firma, la caducidad, que la sesión sigue activa y que el usuario sigue siendo
    miembro (una consulta indexada).
  - Las rutas relativas del sitio conservan el prefijo del token.
- **Cabeceras propias** en `/site/`:
  - `Content-Security-Policy: sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox; default-src 'self';
    script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;
    connect-src 'self'; form-action 'none'; base-uri 'self'; frame-ancestors 'self'`;
  - `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: no-referrer` (el token no sale en enlaces externos),
    `Cache-Control: private, max-age=300`;
  - sin `allow-same-origin`: los scripts del sitio no leen cookies ni `localStorage` de la app ni llaman a la API con
    credenciales.
- **Frontend**: `<iframe sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox" src=…>` y «Abrir en
  pestaña nueva», que sigue en sandbox por la cabecera CSP.
- `PENDIENTE DE VERIFICAR` en la E2E: que el buscador y la navegación de Zensical funcionen con origen opaco
  (`'self'` y `fetch` del índice). Si el buscador no funciona, se documenta y se considera `allow-same-origin` solo
  con un origen distinto (`DOW_SITE_ORIGIN`, opcional; queda para la Fase 10).

## 7. Integración y jobs

- `integrations/doc_organize/context.py` (importa doc_organize dentro de cada función, G15):
  - `converted_documents(folders, state_root, output_root)` → `ConversionResult`, sin los originales que no existan;
  - `build_context(request, on_event, is_cancelled)` (builder → reorganizer → site con `timeout`);
  - `delete_context(...)` (`delete_output`, `delete_site`, `delete_context`) y `preview_delete(...)`;
  - `parse_template`, `render_template`, `builtin_templates()`, `builtin_template(name)`;
  - `load_manifest`/`save_manifest`;
  - `collisions(context)` (G30).
- `jobs/operations/context.py`: `run_build` y `run_delete`.
  - La cancelación se une con el `CancelToken`.
  - Avisos sin rutas absolutas y resumen en `public_params`/resultado.
- La plantilla elegida se lee de la BD (personalizada) o de la librería (incluida) **en la API** al encolar y se
  guarda en `params` como Markdown (≤ 256 KiB): el run usa la versión validada en ese momento.
- Ajuste `DOW_CONTEXT_SITE_TIMEOUT` (600 s por defecto).
- Dependencias:
  - `doc_organize[ai,context,export,site]==0.13.0` (añade zensical, unos 9 MB);
  - zensical sale del grupo `docs` (pasa a runtime);
  - `uv lock` con el hash del wheel.

## 8. Frontend

| Pantalla | Ruta | Sustituye a |
|---|---|---|
| `features/context/ContextPage` | `/projects/:id/context` | `context.html.j2` |
| `features/context/SiteViewerPage` | `/projects/:id/context/site` | `/projects/{name}/context/site` |
| `features/admin/TaxonomyTemplatesPage` | `/admin/plantillas-taxonomia` | `taxonomy_templates_admin.html.j2` |

- `ContextPage`:
  - estado (sin contexto, construyendo con el progreso del run, construido);
  - formulario de construcción: nombre de la carpeta la primera vez y catálogo (descubrir, lista, plantilla o
    manifiesto);
  - tabla de dominios con documentos paginados y lista de sin clasificar;
  - avisos (fallidos, colisiones G30, sitio sin construir);
  - editor del manifiesto con la validación del servidor;
  - borrar en dos pasos (vista previa y nombre tecleado).
- `TaxonomyTemplatesPage`: incluidas (solo lectura, descargar, «Duplicar como personalizada») y personalizadas
  (crear, editar, borrar, descargar, importar `.md`).
- Botón «Contexto» en el proyecto, enlace desde el run y tipos de run traducidos.
- Estados de carga, vacío, error y sin permiso, textos i18n `es` y consultas por rol y texto.

## 9. Riesgos

- **Seguridad del sitio**:
  - HTML incrustado en el Markdown de los documentos (contenido no confiable) → CSP `sandbox` + token (§6);
  - fuga del token por `Referer` o historial → `no-referrer`, caducidad corta y ligado a la sesión;
  - recorrido de rutas → resolvedor + `_no_links`.
- **Enlaces**: la 0.13.0 no los sigue al reorganizar (G27). La web pasa raíces reales.
- **Escala**: con 100 000 documentos, `context.json`/`index.json` son grandes y se leen solo en el worker; las
  listas salen de la BD paginadas.
  - Memoria del `build`: en IMPLEMENT se mide un proyecto sintético de 5 000 documentos.
  - Zensical sobre 100 000 páginas puede tardar → timeout configurable y aviso, sin fallar el contexto.
- **Concurrencia**: `context_build` y `context_delete` son escrituras y respetan el bloqueo de una a la vez por
  proyecto.
  - PUT del manifiesto: 409 si hay una escritura activa.
  - `project_move`/`history_clear` ya bloquean.
- **Red (SMB/NFS)**:
  - `zensical build` escribe `site/` y `.cache/` en el destino de red, más lento → timeout;
  - escrituras atómicas de doc_organize sobre SMB: se comprueban en la prueba de integración (fuera del CI).
- **Destructivas**: `context_delete` borra solo lo que gestiona el contexto. `output_folder_name` se valida con
  `validate_output_folder_name` y no puede pisar `Conversión/` ni `duplicados/`.
- **Colisiones (G30)**: avisadas, sin pérdida de originales.
- **Imagen**: +9 MB (zensical), sin mkdocs.

## 10. Pruebas

- **Unitarias**:
  - validación de nombres de plantilla y del catálogo;
  - token del sitio (firma, caducidad, otra sesión, otro proyecto);
  - lista blanca de tipos MIME;
  - relativización de rutas y colisiones.
- **API**:
  - CRUD de plantillas (admin 200, usuario 403, incluida 409, Markdown inválido 422, auditoría);
  - contexto y listados con 401/403/404 e IDOR entre proyectos;
  - manifiesto (`ro` → 409/422, escritura activa → 409);
  - `site-session` y `/site/` (token inválido, caducado o de otra sesión → 404, `..` → 404, enlace → 404, cabeceras
    CSP);
  - runs (roles, vista previa de `context_delete`).
- **Jobs** (doc_organize sustituido en la capa anticorrupción y otra variante con la librería real sin zensical, con
  `build_site=False`):
  - proyección a la BD, documentos fallidos, cancelación;
  - `context_delete` con `dry_run` y real;
  - un enlace en un artefacto → aviso (solo Linux, imagen `backend-dev`).
- **Frontend (Vitest)**: página de contexto (estados), formulario, admin de plantillas (importar, exportar, validar)
  y visor.
- **E2E**: construir con la plantilla incluida `calidad` sobre la carpeta E2E → dominios visibles → abrir el sitio en
  el iframe (que cargue y que `document.cookie` esté vacío dentro) → borrar con confirmación.
- **Integración** (fuera del CI): `zensical build` real sobre un proyecto sintético de 5 000 documentos (tiempo y
  memoria).

## AUDIT_PLAN

- **Arquitectura y reglas**:
  - Solo `integrations/doc_organize/context.py` importa la librería (regla 3).
  - Construir y borrar el contexto son jobs (regla 4).
  - Todas las rutas pasan por el resolvedor y SQLite no va a la red, porque la proyección vive en `config.db`
    (reglas 5 y ADR-005).
  - Sin secretos: el token del sitio está firmado y no se guarda.
  - `context_delete` sigue la regla 7.
  - El cambio de contrato regenera `openapi.json` y `schema.d.ts` en el mismo cambio (regla 8).
- **ADRs**: se redacta ADR-010 (sitio aislado, §6). Cumple ADR-002 (subproceso por job; zensical es un subproceso
  más), ADR-005 (salidas del contexto en el destino) y ADR-008 (progreso SSE).
- **Huecos**: G30 nuevo (colisiones de `stem`, no bloquea). G10 y G27–G29 pasan a «Resueltos» con 0.13.0.
- **PARIDAD**: filas `context.html.j2`, `taxonomy_templates_admin.html.j2`, `context.py` (GET/POST/DELETE, build,
  delete, taxonomy-manifest y site) y `taxonomy_templates.py` (las dos). `taxonomy-manifest-draft` sigue en la
  Fase 8.
- **Condiciones** (decide el mantenedor):
  - C1: sitio con URL con token firmado + CSP `sandbox` en el mismo host (sin subdominio), con el buscador por
    verificar en la E2E.
  - C2: las plantillas personalizadas no pueden usar el nombre de una incluida (409); para cambiar una incluida, se
    duplica.
  - C3: contexto proyectado en `config.db` (`project_contexts`, `context_documents`) para paginar.
  - C4: G30 avisado en la web y L-8d pedido más adelante, sin bloquear la fase.
- **Veredicto**: `GO_CONDICIONAL` (C1–C4).

### Decisiones del mantenedor (2026-11-02)

- C1: token firmado + CSP `sandbox` en el mismo host.
- C2: una personalizada no puede usar el nombre de una incluida; se duplica con otro nombre.
- C3: proyección del contexto en `config.db`.
- C4: G30 se avisa en la web y L-8d se pide más adelante.

**Veredicto tras las decisiones: `GO`**, a la espera de la aprobación de IMPLEMENT.
