# ROADMAP — doc_organize_web (parte web)

Mismo formato que `util_bbdd_web/docs/plan/ROADMAP.md`: cada fase se implementa con `/phase <n>` y se cierra con una
MINOR `0.<n+1>.0`. Orden: de **solo lectura** a **escritura** (escaneo → duplicados → reorganización), para que roles,
ubicaciones `ro`, confirmaciones y auditoría estén probados antes de mover ficheros.

| Fase | Nombre | Versión | Requiere de doc_organize |
|---|---|---|---|
| 0 | Fundaciones | 0.1.0 | 0.9.x (wheel) |
| 1 | Identidad y multiusuario | 0.2.0 | — |
| 2 | Ubicaciones locales/red y ajustes | 0.3.0 | — |
| 3 | Proyectos y motor de ejecuciones | 0.4.0 | 0.10.0 (L-1, L-4, L-5) |
| 4 | Escaneo y conversión | 0.5.0 | 0.10.0 (L-2, L-6b) |
| 5 | Caché, resultados y descargas | 0.6.0 | 0.11.0 (L-7) |
| 6 | Duplicados | 0.7.0 | 0.10.0 (L-6) |
| 7 | Contexto y taxonomías | 0.8.0 | 0.11.0 (L-8) |
| 8 | IA: clasificación, manifiestos y uso | 0.9.0 | 0.10.0 (L-3) |
| 9 | Multi-tenant y roles | 0.10.0 | — |
| 10 | Endurecimiento y release | 1.0.0 | 1.0.0 |

**DoD común**: comandos de desarrollo en verde (backend y frontend), OpenAPI exportado y cliente regenerado, migración
Alembic con `downgrade`, tests de autorización (401/403/404 e IDOR), imagen construida y `/api/health` 200, CHANGELOG,
guía de usuario de lo implementado, `TRACEABILITY.md` de la sesión y fila de `PARIDAD.md` marcada.

---

## Fase 0 — Fundaciones

**Backend**
- WB-0.1 Estructura `backend/app` (capas de `ARQUITECTURA_PROPUESTA.md`), `pyproject.toml` con uv, `exclude-newer`.
- WB-0.2 `core/`: ajustes `DOW_*` con pydantic-settings + Docker secrets, logging JSON con `request_id`, RFC 9457.
- WB-0.3 `db/`: engine SQLite (WAL, `synchronous=NORMAL`, `busy_timeout`, `foreign_keys`), Alembic `0001` vacía.
- WB-0.4 `/api/health` (BD, worker, ubicaciones y modelos en fases siguientes) y SPA servida en `/`.
- WB-0.5 `integrations/doc_organize/` con `version.py` y test de arquitectura «solo esta carpeta importa doc_organize».
- WB-0.6 `scripts/export_openapi.py --check`.

**Frontend**
- WF-0.1 Vite + React + TS estricto, Mantine (tema claro/oscuro), React Router, TanStack Query, i18next `es`.
- WF-0.2 Cliente `openapi-fetch` + `schema.d.ts` generado; layout con navegación por fases; 404; página de salud.
- WF-0.3 ESLint, Prettier, Vitest + Testing Library, Playwright con un E2E de humo.

**Infra / gobierno**
- WD-0.1 Dockerfile multi-stage (`frontend-build`, `runtime`, `backend-dev`), compose `web` + `worker`, secretos,
  endurecimiento, healthcheck.
- WD-0.2 CI (backend, frontend, imagen + health), Dependabot con *cooldown* 14 días.
- WD-0.3 Configuración IA completa (ver `INSTRUCCIONES_IA.md`), ADR-001…006, ROADMAP, `DOC_ORGANIZE_GAPS.md`,
  `PARIDAD.md` (L-0); documentación con Zensical (`zensical.toml`, `zensical build --strict` en CI).
- WD-0.4 **Repositorio público** (adelantado el 2026-10-31: ramas protegidas, *secret scanning*, Dependabot, CodeQL, `SECURITY.md` y CI `docs` ya activos; queda añadir `backend`/`frontend`/`image` como checks obligatorios): `.gitignore` de secretos desde el primer commit, *secret scanning* + *push
  protection*, CodeQL (Python y TS), Dependabot *alerts*, `SECURITY.md` con reporte privado, protección de
  `main`/`develop`, fixtures sintéticos (detalle en `DECISIONES_Y_RIESGOS.md`).
- WD-0.5 `docker-compose.dev.yml` para Docker Desktop con carpetas locales como ubicaciones de prueba.

## Fase 1 — Identidad y multiusuario

**Historias**: como admin creo, desactivo y reactivo usuarios y asigno `admin`/`user`; como usuario inicio y cierro
sesión y cambio mi contraseña; como admin veo y revoco sesiones y consulto la auditoría.

- WB-1.1 Modelos `tenants` (fila `default`), `users`, `sessions`, `audit_log`; `pwdlib[argon2]`; cookie `__Host-` +
  CSRF (ADR-003); bloqueo por intentos; contraseñas comunes; `app.cli create-admin`.
- WB-1.2 Dependencias `current_user` / `require_admin`; endpoints `/api/v1/auth/*`, `/users`, `/sessions`, `/audit`.
- WF-1.1 Login (sustituye `login.html.j2`), guardas de ruta, menú de usuario, cambio de contraseña
  (`change_password.html.j2`), admin de usuarios (`admin_users.html.j2`) y sesiones.
- Tests: hash, bloqueo, CSRF, flags de cookie, IDOR, E2E de login.

## Fase 2 — Ubicaciones locales/red y ajustes administrables

**Historias**: como admin registro ubicaciones (origen/destino, local/red, `ro`/`rw`), las pruebo y veo su estado;
como usuario exploro carpetas dentro de las ubicaciones a las que tengo acceso; como admin cambio ajustes sin reiniciar.

- WB-2.1 Modelo `locations` + validación contra `DOW_LOCATIONS_ROOT`, resolución segura de rutas (enlaces, `..`,
  autorización antes que existencia), sondeo `ok/degraded/unavailable` (lectura, escritura temporal, latencia, espacio).
- WB-2.2 `GET /api/v1/fs/browse?location=&path=` (sustituye `/api/fs/browse`, ya no parte de `Path.home()`), paginado.
- WB-2.3 `app_settings` con precedencia BD > entorno > defecto (ADR-012 de util_bbdd_web); ficha «capacidades de la
  instancia» (GPU, AV, LibreOffice, modelos presentes) desde `doc_organize.diagnostics` (L-9b).
- WF-2.1 Admin de ubicaciones con semáforo de estado; componente **explorador de carpetas** reutilizable
  (sustituye `_folder_browser_macros`); admin de ajustes; ficha de capacidades.
- Docs: guía «Montar carpetas de red» en el servidor Linux (`/etc/fstab` con CIFS/NFS, credenciales en fichero
  `0600` del host, *bind mount* bajo `/mnt`); en desarrollo (Docker Desktop) solo carpetas locales.
- Tests: escape de raíz con enlace simbólico, ruta UNC/relativa rechazada, ubicación caída → 503 problem details.

## Fase 3 — Proyectos y motor de ejecuciones

**Historias**: creo proyectos eligiendo origen(es) y destino; invito miembros; lanzo una ejecución, sigo su progreso
aunque cierre la pestaña, la cancelo y veo el historial **agrupado por ejecución**.

- WB-3.1 `projects` (origen = ubicación + subrutas; destino = ubicación `rw` + subruta), `project_members`; layout de
  estado en `/data/projects/<id>/` con `ProjectLayout` (L-4).
- WB-3.2 Cola sobre `runs` (`queue` cpu/gpu), worker con subproceso *spawn*, latido, cancelación, timeouts,
  huérfanos; SSE `GET /api/v1/runs/{id}/events` con `Last-Event-ID`; bloqueo de una escritura por proyecto.
- WB-3.3 Workspace por ejecución (`run.json`, `logs/run.log`, `outputs/`), `artifacts`, retención y cuotas; job `noop`.
- WB-3.4 Mover/renombrar/borrar proyecto (equivalente a `move_project_root`, `delete_project`) como runs auditados.
- WF-3.1 Selector y lista de proyectos (`project_selector.html.j2`), dashboard de proyecto (`dashboard.html.j2`),
  miembros, historial de ejecuciones, detalle con progreso en vivo (`aria-live`) y cancelación.

## Fase 4 — Escaneo y conversión

**Historias**: escaneo una o varias carpetas del origen con las opciones actuales (OCR, GPU, audio/vídeo, extraer
imágenes, descripción de imágenes, forzar); guardo carpetas frecuentes; veo errores de escaneo y el historial.

- WB-4.1 Operación `scan` → `ScanCommand.run_streaming` con `on_progress` y `cancel_token` (L-2); la opción GPU
  enruta a la cola `gpu`; validación de opciones contra las capacidades de la instancia.
- WB-4.2 Carpetas guardadas (`scanned_folders` en BD, sustituye `ScannedFoldersStore` JSON para la web).
- WB-4.3 Historial de escaneos y errores (`ScanRunReport`, `ScanErrorReport`) leídos de los ficheros que escribe la
  librería y resumidos en `runs`; endpoint de errores paginado.
- WF-4.1 Pantalla de escaneo (`folder_selector.html.j2`) con explorador, opciones con ayuda contextual
  (`_example_modal_macros`), progreso por documento y fase; página de errores (`scan_errors.html.j2`).
- Tests: escaneo incremental (sin cambios = 0 conversiones), cancelación a mitad, documento que supera el timeout.

## Fase 5 — Caché, resultados y descargas

- WB-5.1 Lectura paginada y con búsqueda de `cache.db` (`CacheManager.count_entries`/`load_cache_page`).
- WB-5.2 Vista de un documento convertido (Markdown/JSON/imágenes) servida con rutas seguras y `Content-Type` fijo.
- WB-5.3 Exportaciones como runs: ZIP del proyecto (vista previa de tamaño), Excel de caché y de errores (L-7).
- WF-5.1 Tabla virtualizada de caché con filtros, visor Markdown saneado (DOMPurify) y JSON, descargas.

## Fase 6 — Duplicados

**Historias**: veo los grupos de duplicados detectados (exactos y difusos), elijo qué conservar por grupo y aplico
con confirmación; si el origen es `ro` solo puedo generar informe o copiar a cuarentena.

- WB-6.1 `dedup_preview` (artefacto con grupos e id estable) y `dedup_apply` con los grupos revisados (L-6); modo seco
  obligatorio y caducidad de la vista previa (si el origen cambió, se recalcula); auditoría por fichero movido.
- WF-6.1 Resolutor de duplicados (`duplicates_resolver.html.j2`): comparación lado a lado, umbral difuso, política
  de conservación, confirmación explícita, informe final; aviso si la última ejecución ya resolvió los duplicados (hoy la página de revisión dice «no se detectaron duplicados» cuando el escaneo ya los movió).

## Fase 7 — Contexto y taxonomías

- WB-7.1 `taxonomy_templates` (incluidas + personalizadas en BD), CRUD admin de instancia.
- WB-7.2 Runs `context_build` / `context_delete`; contexto del proyecto (`GET/DELETE`).
- WB-7.3 Sitio Zensical (L-8) servido **aislado** (ADR-007 de util_bbdd_web: subdominio o `iframe sandbox` + CSP propia),
  sin ejecutar scripts del sitio en el origen de la app.
- WF-7.1 Página de contexto (`context.html.j2`), admin de plantillas (`taxonomy_templates_admin.html.j2`), visor del
  sitio.

## Fase 8 — IA: clasificación, manifiestos y uso

- WB-8.1 `ai_settings` por familia (LiteLLM uso, clasificación de dominio, clasificación de taxonomía, borrador de
  manifiesto, GitHub Copilot) cifrado con Fernet, nunca devuelto en claro (solo «configurado» + últimos 4).
- WB-8.2 Integración con los clientes `ai/` pasando `*Config` (L-3); timeouts, reintentos y presupuesto por run.
- WB-8.3 Panel de uso (LiteLLM, Copilot) con caché corta.
- WF-8.1 Configuración IA (`ai_settings.html.j2`), lanzamiento de clasificaciones y borradores de manifiesto, panel
  de uso.
- **Cierre de paridad** → doc_organize L-10 (deprecar la web integrada).

## Fase 9 — Multi-tenant y roles

- WB-9.1 Tenants activos (la columna `tenant_id` ya existe desde F1), admin de instancia, aislamiento en todas las
  consultas (test IDOR entre tenants), ubicaciones por tenant.
- WB-9.2 Roles personalizados con permisos (`admin_roles.html.j2`), migración de `admin`/`user` a roles base.
- WF-9.1 Admin de tenants (`admin_tenants.html.j2`), usuarios por tenant, roles; selector de tenant para el admin de
  instancia.

## Fase 10 — Endurecimiento y release 1.0

- OWASP ASVS L2 (`/security-review` completo) y remediación; cabeceras, CSP, rate limiting, `/metrics`.
- Backup/restauración de `config.db` y de `data/projects/*/cache.db` (`sqlite3 .backup`).
- E2E de todos los flujos; prueba de carga con el objetivo de diseño (100 000 documentos, listados paginados de
  caché y duplicados a ese tamaño); variantes GPU, LibreOffice y AV verificadas en el servidor Linux.
- doc_organize 1.0.0 publicada (L-11…L-15) y fijada en `uv.lock`.

## Mejoras opcionales (decidir al planificar)

Ejecuciones programadas (re-escaneo nocturno por proyecto), notificaciones al terminar, subida de documentos desde el
navegador (con antivirus), tokens de API personales, búsqueda de texto completo (SQLite FTS5) sobre el Markdown
convertido, migración de `config.db` a PostgreSQL.
