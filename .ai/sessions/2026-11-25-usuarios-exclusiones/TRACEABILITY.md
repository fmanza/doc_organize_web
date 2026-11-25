# TRACEABILITY

## Session metadata
- id: 2026-11-25-usuarios-exclusiones
- fecha: 2026-11-25 / 2026-11-26
- rama:
    - `feat/usuarios-filtros` (PR #126)
    - `feat/usuarios-borrado` (PR #127)
    - `feat/exclusiones-carpetas` (PR #128)
    - `release/2.7.0` → `main`
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN (2 revisiones) + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued

> «Poder eliminar usuarios y bloquearlos, en util_bbdd_web ya se ha implementado, mira las decisiones tomadas, analiza
> este proyecto y propón mejor estrategia; excluir carpetas, tanto en duplicados, como en escaneo, como dato general
> del proyecto, proponer mejoras; en usuario poder buscar también por ROL y estado. PLAN y AUDIT_PLAN».
>
> Después: «Añadir que como mínimo tiene que existir un administrador y que esté activo, revísalo».

## Context supplied
- util_bbdd_web: ADR-013 «Borrado de usuarios sin dependencias» y su enmienda de transferencia (1.22.0).
- Modelo `User` y claves foráneas hacia `users` (`backend/app/db/models.py`) y `domain/identity/users.py`.
- `domain/projects/service.py` (último `owner`), `domain/tenancy/roles.py` y `domain/scan/folders.py`.
- `domain/runs/operations.py` y `jobs/operations/` (escaneo, duplicados, contexto y exportaciones).
- doc_organize 2.5.0: `ScanOptions.exclude_paths`/`ignore_patterns`, `EntryFilter` y `CacheManager`.

## AI output summary
- **Análisis**:
    - Aquí borrar usuarios es más sencillo que en util_bbdd_web: no hay `owner_id` en cascada, ni conexiones, ni
      carpetas del workspace por usuario. Por eso no hace falta transferir.
    - Duplicados y contexto leían la caché sin aplicar exclusiones.
    - No existían exclusiones a nivel de proyecto.
- **PLAN** en esta carpeta, con tres entregas: F1 filtros, F2 bloquear y borrar, F3 exclusiones.
- **F0 «siempre un administrador activo»**: revisión de 12 caminos. Huecos encontrados:
    - la carrera entre dos peticiones simultáneas;
    - el borrado nuevo;
    - no se detectaba una instancia sin admins;
    - no había forma de recuperar una cuenta existente;
    - `update_role` podía dejar un tenant sin gestores.
- **AUDIT_PLAN, revisión 2**, contrastada con el código. Hallazgos:
    - A1: hay más lectores de la caché;
    - A2: G47, doc_organize no borra de la caché por ruta;
    - A3: duplicados son vista previa y aplicación;
    - A4: los límites de `ScanParams` se quedaban cortos;
    - A5–A8: detalles menores.

  Veredicto **GO**, con las decisiones D1–D4 aprobadas por el usuario.
- **F1** (PR #126, `725c843`):
    - `GET /users` con `role_id`, `status` e `instance_admin`;
    - desplegables en la URL y «Quitar filtros».
- **F2 y F0** (PR #127, `64b65cc`), implementados con un subagente y revisados:
    - `deletion-check` y `DELETE /users/{id}`, que responde `409` con motivos;
    - migración `0032` `audit_log.actor_name`;
    - `ensure_instance_admin` y `_lock_user_row`;
    - CLI `recover-admin`;
    - aviso en el diagnóstico y al arrancar;
    - `update_role` con `last_tenant_manager`;
    - menú «Más acciones» en la interfaz;
    - ADR-016.
- **F3** (PR #128, `6ff88c7`), implementada con un subagente:
    - migración `0033` con las exclusiones del proyecto y el preset de carpetas de sistema;
    - exclusión efectiva aplicada en escaneo, duplicados (más exclusiones solo para un análisis y `409
      exclusions_changed`), contexto y exportaciones;
    - ADR-017 y hueco G47.
- **CI**: en verde los cuatro trabajos (backend, frontend, docs e image con E2E) de los PR #126, #127 y #128.
- **VERSION**:
    - 2.7.0 sincronizada en CHANGELOG, `pyproject.toml`, `app/__init__.py`, `package.json` y su lock, `uv.lock`,
      `openapi.json` y `DOW_TAG`;
    - actualizados `.ai/product.md`, la fila de borrado de usuarios de `PARIDAD.md` e `INDEX.md`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN y AUDIT_PLAN | `.ai/sessions/2026-11-25-usuarios-exclusiones/PLAN.md` | emitido (GO) |
| ADR-016 | `docs/adr/ADR-016-borrado-de-usuarios.md` | aceptado |
| ADR-017 | `docs/adr/ADR-017-exclusion-efectiva.md` | aceptado |
| Migraciones | `backend/alembic/versions/0032_audit_actor_name.py`, `0033_project_exclusions.py` | fusionadas |
| Hueco G47 | `docs/plan/DOC_ORGANIZE_GAPS.md` | abierto |
| Release | CHANGELOG `[2.7.0]` | preparada |

## Directrices para Futuras IAs
- **[usuarios]**: Bloquear equivale a desactivar (`is_active = false`). En la interfaz se muestra como «Bloqueado», y
  el bloqueo temporal por intentos fallidos como «Bloqueado por intentos». No existe un tercer estado.
- **[usuarios]**: `DELETE /api/v1/users/{id}` solo borra si `deletion_check` no da motivos (`self`,
  `last_instance_admin`, `last_manager`, `sole_owner` o `active_runs`). Ser miembro de un proyecto no lo impide.
  Sesiones y pertenencias se borran en cascada y lo demás queda en `SET NULL` (ADR-016).
- **[auditoría]**: `audit_log.actor_name` guarda el nombre del actor al registrar el evento. Cualquier acción nueva
  debe pasar por `audit.record`, que lo rellena.
- **[admin]**: Toda operación que pueda quitar un admin de instancia activo debe:
    - llamar antes a `_lock_user_row` y comprobar;
    - llamar a `ensure_instance_admin(db)` antes del `commit`.

  El test de concurrencia (`tests/api/test_user_deletion.py`) necesita SQLite en fichero.
- **[admin]**: Para recuperar el acceso se usa `python -m app.cli recover-admin --username <u> [--reset-password |
  --password-stdin]`. Sin opción de contraseña, no la cambia.
- **[exclusiones]**: La exclusión efectiva es la unión de las exclusiones del proyecto, las de la carpeta guardada, los
  patrones de la ubicación y `SYSTEM_PATTERNS`. La calcula `domain/projects/exclusions.py`. Todo lector nuevo de la
  caché por lotes debe filtrar con `exclusion_filter` (`jobs/operations/_files.py`).
- **[exclusiones]**: `PathFilter` replica el criterio de `EntryFilter` de doc_organize, porque este es interno y no
  está en `__all__`. No hay que importarlo.
- **[exclusiones]**: El índice de búsqueda no aplica las exclusiones, porque recorre `Conversión/*.md`. Lo excluido
  sigue en `cache.db` hasta que doc_organize permita borrar por ruta (G47).
- **[exclusiones]**: Si cambian las exclusiones propias del proyecto, cambia `projects.updated_at`, y aplicar una vista
  previa de duplicados anterior responde primero `422 duplicates_preview_required`. `409 exclusions_changed` salta
  cuando cambian las exclusiones de una carpeta o los patrones de la ubicación.

## Veredicto final
Veredicto: CLOSED (pendiente de publicar la 2.7.0)

Pendientes al cierre:
- Revisión humana del inglés nuevo (F2 y F3).
- G47 en doc_organize: borrar de la caché por ruta y filtrar en `load_cache_page`.
- Las exclusiones en el índice de búsqueda.
