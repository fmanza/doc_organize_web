# PLAN — Opción (a) de C1: al borrar un proyecto, sus ubicaciones quedan libres

## Objetivo
Al borrar un proyecto, poner a `NULL` sus claves ajenas a las ubicaciones (`source_location_id`,
`destination_location_id`). Así una ubicación que solo usaban proyectos borrados se puede eliminar o pasar a otro
tenant. Hoy da `409 location_in_use` («Solo la usan N proyecto(s) borrado(s)…»).

## Hechos comprobados
- Los proyectos borrados no usan sus ubicaciones:
  - `get_access` los excluye salvo con `include_deleted`, que solo usa el detalle de ejecución, y este solo lee el rol.
  - `list_projects` y `check_destination_free` filtran `status == "active"`.
  - El worker corta con `require_project` (`project_missing`) antes de tocar ubicaciones.
- No hay restauración de proyectos borrados.
- El historial de ejecuciones va por `project_id` y `project_name`, no por ubicación. `project_move` guarda el nombre
  del destino como texto.
- Las migraciones en SQLite corren con `PRAGMA foreign_keys=OFF` y `foreign_key_check` (`alembic/env.py`): recrear
  `projects` con `batch_alter_table` no dispara cascadas.

## Decisiones (recomendadas)
- **D1. Cuándo se sueltan:** al borrar el proyecto, en el mismo `UPDATE` que pone `status="deleted"`
  (`jobs/operations/project_delete.py`). La migración hace lo mismo con los proyectos ya borrados.
  - Alternativa descartada: soltarlas solo al borrar la ubicación. Habría que repetirlo al cambiar de tenant, y la
    regla «borrado ⇒ sin ubicaciones» quedaría menos clara.
- **D2. Tipado:** columnas `nullable=True`, manteniendo `Mapped[int]` y `Mapped[Location]`, más un CHECK:
  `status = 'deleted' OR (source_location_id IS NOT NULL AND destination_location_id IS NOT NULL)`.
  - La invariante «activo ⇒ con ubicaciones» la garantiza la BD.
  - El código solo carga ubicaciones de proyectos activos. Así se evitan unos 30 `if location is None` sin valor
    (política: no refactorizar).
- **D3. Rastro:** la auditoría `PROJECT_DELETE` añade `source_location` y `destination_location` (`{id, name}`) antes
  de soltarlas. `PROJECT_CREATE` ya guarda los ids.
- **D4. Contrato:**
  - `LocationUsageOut.deleted_projects` se mantiene para no romper el contrato; será siempre 0 y su descripción lo
    marca como obsoleto.
  - El dominio (`LocationProjects`) se queda igual: `projects_on_location` ya no encuentra borrados.
  - Se quita la rama de mensaje «solo proyectos borrados» de `_in_use_message` y de la UI (`inUse.onlyDeleted`,
    `inUse.alsoDeleted`).
- **D5. `ondelete`:** sigue en `RESTRICT`; protege a los activos.
- **D6. Versión:** 2.3.1 (corrección de C1, sin funcionalidad nueva). Lleva la migración `0029`, avisada en
  «Actualizar».

## Rutas afectadas
- **Backend**
  - `backend/app/db/models.py` (`Project`: `nullable=True` y el CHECK `locations`).
  - `backend/alembic/versions/0029_deleted_projects_release_locations.py`
    - upgrade: `UPDATE … SET … = NULL WHERE status = 'deleted'` (con la columna ya `nullable` en el batch) y el CHECK.
    - downgrade: falla con un mensaje claro si hay proyectos sin ubicación; si no, revierte. El rollback real es la
      copia de seguridad.
  - `backend/app/jobs/operations/project_delete.py`: `UPDATE` con las dos FK a `NULL` y auditoría con las ubicaciones.
  - `backend/app/domain/locations/service.py`: docstrings de `LocationProjects` y `delete_location`; quitar la rama
    «solo borrados» de `_in_use_message`.
  - `backend/app/api/v1/schemas.py`: descripción de `deleted_projects` (obsoleto, siempre 0) y `can_delete`.
  - `backend/app/api/v1/locations.py`: texto del `409` («algún proyecto activo»).
  - `openapi/openapi.json` y `frontend/src/api/schema.d.ts` (regenerados).
- **Frontend**
  - `frontend/src/features/locations/LocationsPage.tsx`: sin las ramas de borrados.
  - `frontend/src/i18n/es/features.json`: sin las claves `inUse.onlyDeleted` e `inUse.alsoDeleted`.
  - `frontend/src/features/locations/locations.test.tsx`
- **Docs y versión:** guía de ubicaciones y proyectos (borrar una ubicación) y CHANGELOG.

## Pruebas
- **Backend**
  - Borrar un proyecto deja sus FK a `NULL`, la auditoría lleva las ubicaciones y el detalle de sus ejecuciones sigue
    respondiendo.
  - Tras borrarlo, `DELETE /locations/{id}` da `204`, `usage` da `can_delete: true` y el cambio de tenant funciona.
  - Con un proyecto activo sigue dando `409`.
  - La BD rechaza un proyecto activo con FK `NULL` (CHECK).
  - Migración `0029`: suelta las ubicaciones de los borrados existentes y no toca los activos; `downgrade` vuelve
    atrás sin borrados y falla con mensaje si los hay.
  - Run en cola de un proyecto borrado: `project_missing` (ya existe; comprobar que sigue verde).
- **Frontend:** modal de borrado sin textos de proyectos borrados.

## Riesgos
- Se pierde en la BD qué ubicación usaba un proyecto borrado (queda en la auditoría: D3).
- Si algún código carga ubicaciones de un proyecto borrado → `AttributeError` sobre `None`. Mitigación:
  `require_project` y `get_access`, más tests del detalle de ejecución.
- Migración que recrea `projects` (tabla padre de `runs`, `project_members`…), cubierta por `foreign_keys=OFF` y
  `foreign_key_check`.
