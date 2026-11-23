# TRACEABILITY

## Session metadata
- id: 2026-11-23-ubicacion-libre
- fecha: 2026-11-23
- rama: fix/2.3.1-ubicacion-libre
- skill: new_feature (corrección C1, versión 2.3.1)
- fase: PLAN + AUDIT_PLAN (ficheros en esta carpeta) + IMPLEMENT + AUDIT_CODE

## Prompt issued
- «Opción (a) de C1: que al borrar un proyecto su ubicación quede libre para poder eliminarla. PLAN y AUDIT_PLAN».
- «Acepto recomendaciones, empieza el IMPLEMENT por la web 2.3.1».

## Context supplied
- [PLAN.md](PLAN.md) y [AUDIT_PLAN.md](AUDIT_PLAN.md); sesión `2026-11-23-ia-duplicados-2.2` (C1 de la 2.1.1).

## AI output summary
- **Migración `0029`**:
  - las claves de `projects` a las ubicaciones pasan a admitir `NULL`;
  - los proyectos ya borrados sueltan sus ubicaciones;
  - nuevo CHECK `ck_projects_locations` (solo un proyecto borrado puede quedarse sin ubicaciones);
  - `downgrade` falla con un mensaje claro si algún proyecto se ha quedado sin ubicación.
- **Modelo**: `nullable=True` sin cambiar `Mapped[int]` (D2), con un comentario sobre la invariante y el CHECK.
- **`project_delete`**: pone a `NULL` las dos claves en el mismo `UPDATE` que marca el proyecto como borrado; la
  auditoría `project.delete` añade `source_location` y `destination_location` (`{id, name}`).
- **Ubicaciones**: se quita el mensaje «solo la usan proyectos borrados»; `LocationUsageOut.deleted_projects` queda
  obsoleto (siempre 0, `deprecated` en OpenAPI).
- **UI**: el aviso del borrado solo lista los proyectos activos; se quitan las claves `inUse.alsoDeleted` y
  `inUse.onlyDeleted`.
- **Guía**: `docs/guides/ubicaciones.md`. **CHANGELOG**: `[Unreleased]`, Fixed.
- **Condiciones del AUDIT_PLAN cumplidas**:
  - CHECK en la BD y en el modelo;
  - `test_projects_schema_matches_the_model` (deriva de `projects`);
  - tests de la `0029` en `upgrade` y `downgrade`, con y sin proyectos sueltos;
  - `dry_run` del borrado sin efecto;
  - detalle de ejecución de un proyecto borrado;
  - ubicación liberada: borrar y cambiar de tenant;
  - un proyecto activo no puede quedarse sin ubicaciones.
- **Verificación local**:
  - ruff, mypy y la comprobación de `openapi.json` sin errores;
  - backend con 715 passed. Falla solo `test_swapped_output_folder_is_not_touched` (Windows, `WinError 1314`, ya
    conocido);
  - tsc y eslint sin errores;
  - Vitest con 188 passed más 1 que falla por tiempo con carga y pasa aislado;
  - `zensical build --strict` sin avisos.

## AUDIT_CODE
- Bugs: ninguno visto. Tras el `UPDATE`, el objeto `project` del worker ya está desligado de la sesión, con las
  ubicaciones cargadas antes. El runner (`usage_log.record`) solo lee `id`, `name` y `tenant_id`.
- Edge cases:
  - un borrado cortado tras marcar el proyecto lo deja borrado y sin ubicaciones (la marca va primero);
  - un run en cola de un proyecto borrado sigue fallando con `project_missing` antes de leer ubicaciones.
- Performance: sin cambios; la migración recrea `projects` una vez por cada batch (dos).
- Seguridad: sin cambios de permisos; la auditoría guarda nombres, no rutas del contenedor.
- Tipado: `Mapped[int]` con `nullable=True` es una decisión consciente (D2), respaldada por el CHECK.
- Deuda: `deleted_projects` y `LocationProjects.deleted` se pueden quitar en la próxima versión mayor.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Migración | `backend/alembic/versions/0029_deleted_projects_release_locations.py` | nueva |
| PLAN / AUDIT_PLAN | `.ai/sessions/2026-11-23-ubicacion-libre/` | guardados |

## Directrices para Futuras IAs
- **[migraciones/tests]**: insertar con `text()` y parámetros (ruff `S608` rechaza f-strings con SQL).
  `locations.visibility` es obligatoria.
- **[tests]**: `admin_client` y `user_client` comparten el cliente. Para las dos sesiones en un test, usar
  `login_as(user_client, admin.username, ADMIN_PASSWORD)`.
- **[backend/tests]**: sin `pytest-xdist`, no hay `-n auto`.

## Veredicto final
Veredicto: PENDING (falta commit, PR y CI).
