# Paridad con la web integrada de doc_organize (L-0)

Inventario de la web integrada de doc_organize (`src/doc_organize/web/`, versión 0.9.3) con la fase de
doc_organize_web que la sustituye. Gobierna la retirada de la web integrada: deprecación en doc_organize 0.12.0 (L-10)
cuando todas las filas hasta la Fase 8 estén cubiertas, y eliminación en 1.0.0 (L-11) tras la Fase 10.

> **Estado**: inventario generado el 2026-10-31 desde el código (decoradores de rutas y carpeta `templates/`), pendiente
> de revisión del mantenedor (criterio de L-0). Una fila se marca ✅ al cerrar la fase que la cubre, con la versión.

Totales: 65 rutas HTTP + 4 WebSocket en 15 módulos, 20 plantillas Jinja (6 de macros compartidas).

## Pantallas (plantillas Jinja)

| Plantilla | Ruta actual | Fase | Sustituto en doc_organize_web | Estado |
|---|---|---|---|---|
| `base.html.j2`, `_nav_macros.html.j2`, `_shared_scripts.html.j2` | — | 0 | `Layout` (AppShell con navegación por fases) | ✅ 0.1.0 |
| `login.html.j2` | `/login` | 1 | Página de inicio de sesión |✅ 0.2.0 |
| `change_password.html.j2` | `/change-password` | 1 | Cambio de contraseña |✅ 0.2.0 |
| `admin_users.html.j2` | `/admin/users` | 1 | Admin de usuarios y sesiones |✅ 0.2.0 |
| `_folder_browser_macros.html.j2` | — | 2 | Componente explorador de carpetas |✅ 0.3.0 |
| `_semaforo_macros.html.j2`, `_status_banner_macros.html.j2` | — | 2 | Semáforo de estado y ficha de capacidades |✅ 0.3.0 |
| `project_selector.html.j2` | `/` | 3 | Lista y selector de proyectos |✅ 0.4.0 |
| `dashboard.html.j2` | `/projects/{name}` | 3 | Dashboard de proyecto |✅ 0.4.0 |
| `folder_selector.html.j2`, `_example_modal_macros.html.j2` | `/projects/{name}/scan` | 4 | Pantalla de escaneo con ayuda contextual |✅ 0.5.0 |
| `scan_errors.html.j2` | `/projects/{name}/scan-errors` | 4 | Errores de escaneo |✅ 0.5.0 |
| `duplicates_resolver.html.j2` | `/projects/{name}/duplicates` | 6 | Resolutor de duplicados en dos pasos | ⬜ |
| `context.html.j2` | `/projects/{name}/context` | 7 | Página de contexto | ⬜ |
| `taxonomy_templates_admin.html.j2` | `/admin/plantillas-taxonomia` | 7 | Admin de plantillas de taxonomía | ⬜ |
| `ai_settings.html.j2` | `/admin/configuracion-ia` | 8 | Configuración IA por familia | ⬜ |
| `admin_roles.html.j2` | `/admin/roles` | 9 | Admin de roles | ⬜ |
| `admin_tenants.html.j2` | `/admin/tenants` | 9 | Admin de tenants | ⬜ |

## Rutas HTTP y WebSocket

Las rutas de página (HTML) ya figuran arriba con su plantilla; aquí van las de API y descargas. Los WebSocket pasan a
ejecuciones encoladas con progreso por SSE (ADR-008): el run sobrevive al cierre de la pestaña.

| Módulo | Método | Ruta actual | Fase | Sustituto previsto | Estado |
|---|---|---|---|---|---|
| `auth.py` | POST | `/login` | 1 | `POST /api/v1/auth/login` |✅ 0.2.0 |
| `auth.py` | POST | `/logout` | 1 | `POST /api/v1/auth/logout` |✅ 0.2.0 |
| `change_password.py` | POST | `/change-password` | 1 | `POST /api/v1/auth/password` |✅ 0.2.0 |
| `admin.py` | GET, POST | `/api/users` | 1 | `/api/v1/users` |✅ 0.2.0 |
| `admin.py` | GET, PATCH, DELETE | `/api/users/{user_id}` | 1 | `/api/v1/users/{id}` (desactivar en lugar de borrar) |✅ 0.2.0 |
| `filesystem.py` | GET | `/api/fs/browse` | 2 | `GET /api/v1/fs/browse?location=&path=` (sin `Path.home()`) |✅ 0.3.0 |
| `projects.py` | GET, POST | `/api/projects` | 3 | `/api/v1/projects` |✅ 0.4.0 |
| `projects.py` | GET, DELETE | `/api/projects/{name}` | 3 | `GET /api/v1/projects/{id}`; borrado como run `project_delete` auditado |✅ 0.4.0 |
| `projects.py` | GET | `/api/projects/{name}/impact` | 3 | Vista previa: run con `dry_run` de la operación |✅ 0.4.0 |
| `projects.py` | POST | `/api/projects/{name}/move` | 3 | Run `project_move` |✅ 0.4.0 |
| `projects.py` | POST | `/api/projects/{name}/clear-history` | 3 | Run `history_clear` |✅ 0.4.0 |
| `scan.py` | WEBSOCKET | `/api/projects/{name}/scan` | 4 | Run `scan` + SSE |✅ 0.5.0 |
| `scan.py` | GET, POST, DELETE | `/api/projects/{name}/folders/library` | 4 | `/api/v1/projects/{id}/scanned-folders` |✅ 0.5.0 |
| `scan.py` | POST | `/api/projects/{name}/folders/validate` | 4 | Validación por el resolvedor de ubicaciones |✅ 0.5.0 |
| `cache.py` | GET | `/api/projects/{name}/cache` | 5 | `/api/v1/projects/{id}/documents` paginado | ⬜ |
| `downloads.py` | GET | `/downloads/projects/{name}/export-preview` | 5 | Vista previa de tamaño del ZIP | ⬜ |
| `downloads.py` | GET | `/downloads/projects/{name}/export.zip` | 5 | Run `export_zip` + artefacto | ⬜ |
| `downloads.py` | GET | `/downloads/projects/{name}/cache-export.xlsx` | 5 | Run `export_xlsx` (caché) | ⬜ |
| `downloads.py` | GET | `/downloads/projects/{name}/scan-errors-export.xlsx` | 5 | Run `export_xlsx` (errores) | ⬜ |
| `scan.py` | WEBSOCKET | `/api/projects/{name}/scan/deduplicate` | 6 | Run `dedup_preview` + SSE | ⬜ |
| `duplicates.py` | GET | `/api/projects/{name}/duplicates` | 6 | Artefacto de vista previa con grupos | ⬜ |
| `duplicates.py` | POST | `/api/projects/{name}/duplicates/resolve` | 6 | Run `dedup_apply` con grupos confirmados | ⬜ |
| `context.py` | GET, POST, DELETE | `/api/projects/{name}/context` | 7 | `/api/v1/projects/{id}/context` | ⬜ |
| `context.py` | WEBSOCKET | `/api/projects/{name}/context/build` | 7 | Run `context_build` + SSE | ⬜ |
| `context.py` | WEBSOCKET | `/api/projects/{name}/context/delete` | 7 | Run `context_delete` + SSE | ⬜ |
| `context.py` | PUT | `/api/projects/{name}/context/taxonomy-manifest` | 7 | Manifiesto de taxonomía del proyecto | ⬜ |
| `context.py` | GET | `/projects/{name}/context/site`, `/projects/{name}/context/site/{file_path}` | 7 | Sitio Zensical aislado (ADR-010) | ⬜ |
| `taxonomy_templates.py` | GET | `/api/taxonomy-templates` | 7 | `/api/v1/taxonomy-templates` | ⬜ |
| `taxonomy_templates.py` | GET, PUT, DELETE | `/api/taxonomy-templates/{template_name}` | 7 | `/api/v1/taxonomy-templates/{name}` | ⬜ |
| `context.py` | POST | `/api/projects/{name}/context/taxonomy-manifest-draft` | 8 | Run `taxonomy_draft` | ⬜ |
| `ai_settings.py` | GET | `/api/admin/ai-settings` | 8 | `/api/v1/admin/ai-settings` (sin secretos en claro) | ⬜ |
| `ai_settings.py` | PUT | `/api/admin/ai-settings/{family_key}` | 8 | `/api/v1/admin/ai-settings/{family}` | ⬜ |
| `admin.py` | GET, POST | `/api/roles` | 9 | `/api/v1/roles` | ⬜ |
| `admin.py` | GET, PATCH, DELETE | `/api/roles/{role_id}` | 9 | `/api/v1/roles/{id}` | ⬜ |
| `tenants.py` | GET, POST | `/api/tenants` | 9 | `/api/v1/tenants` | ⬜ |
| `tenants.py` | DELETE | `/api/tenants/{tenant_id}` | 9 | `/api/v1/tenants/{id}` | ⬜ |
| `tenants.py` | GET, POST | `/api/tenants/{tenant_id}/users` | 9 | Usuarios por tenant | ⬜ |
| `tenants.py` | PATCH, DELETE | `/api/tenants/{tenant_id}/users/{user_id}` | 9 | Usuarios por tenant | ⬜ |

## Fuera de paridad (decisión explícita)

| Elemento actual | Motivo |
|---|---|
| Escaneo que se cancela al cerrar la pestaña (WebSocket) | Sustituido a propósito: el run sigue en el worker (ADR-008) |
| Deduplicar dentro del escaneo moviendo en el origen | Sustituido por vista previa + aplicar grupos confirmados (ADR-009, G6) |
| Quitar de la lista una carpeta ya escaneada (prohibido en la web integrada) | Permitido al propietario con aviso: sus salidas siguen en el destino (decisión de la Fase 4) |
| Carpetas guardadas libres (cualquier subcarpeta del origen) | Las carpetas guardadas son las carpetas de origen del proyecto, sin anidar: la ruta de cada salida depende de la carpeta escaneada (Fase 4) |
| Rutas libres desde `Path.home()` en el explorador | Sustituido por ubicaciones registradas por un admin (ADR-007) |
| Registro de proyectos en `~/.doc_organize/projects.json` | Proyectos en `config.db`, empezando limpio (D4) |
| Borrar usuarios (`DELETE /api/users/{user_id}`) | Se desactivan: la auditoría conserva quién hizo cada cosa (decisión de la Fase 1) |
| Carpeta del proyecto = `<base>/<nombre>` y crear proyectos solo admin | La carpeta de salidas es nueva o vacía y no lleva el nombre (renombrar no la toca); cualquier usuario crea proyectos (decisión de la Fase 3) |
| Mover, vaciar o borrar con un modal de confirmación | Vista previa (`dry_run`) obligatoria + nombre tecleado + auditoría (regla 7, Fase 3) |
