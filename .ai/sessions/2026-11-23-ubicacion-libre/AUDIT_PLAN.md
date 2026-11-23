# AUDIT_PLAN — Ubicaciones libres al borrar un proyecto

## Riesgos funcionales
- **F1.** Ya no se sabe en la app qué ubicación usaba un proyecto borrado. Es aceptable: ninguna pantalla lo
  muestra, y D3 lo deja en la auditoría.
- **F2.** Borrado que se corta tras marcar el proyecto: queda borrado y sin ubicaciones (la marca va primero).
  Si la carpeta de salidas queda a medias, su ruta está en el registro del run. Igual que hoy.
- **F3.** El `dry_run` del borrado no debe soltar nada. El `UPDATE` va después del `return` del `dry_run`. Añadir
  test.
- **F4.** Se puede crear de nuevo una ubicación con el mismo nombre y ruta. No afecta a los proyectos borrados, que
  ya no la referencian.

## Riesgos técnicos
- **T1.** Con `Mapped[int]` y `nullable=True`, mypy no ve el `None`. Condiciones:
  - CHECK en la BD;
  - comentario en el modelo con la invariante: solo los proyectos borrados tienen `NULL`, y el código carga las
    ubicaciones solo de proyectos activos (`get_access` sin `include_deleted`, `require_project`).
- **T2.** Relaciones `lazy="joined"`: con la FK `nullable`, SQLAlchemy usa `LEFT OUTER JOIN`. No hay
  `innerjoin=True` en `app/` (comprobado). Probar el detalle de ejecución de un proyecto borrado.
- **T3.** Orden en la migración, dentro del batch: primero `nullable=True`, después el `UPDATE … = NULL` de los
  borrados (fuera del batch, tras él) y por último el CHECK, en un segundo batch. Así el CHECK nunca ve datos que lo
  violen. Nombre por la `naming_convention`: `ck_projects_locations`.
- **T4.** No hay test de deriva entre el modelo y las migraciones. Condición: test que compare el esquema de
  `projects` tras `upgrade head` con `Base.metadata` (nulabilidad y CHECK), o `alembic check` a mano en la
  IMPLEMENT.
- **T5.** El contrato no cambia de forma (D4). Queda obsoleto `deleted_projects`; quitarlo en una versión mayor.
- **LSP/ISP:** sin cambios de interfaces ni de contratos sync/async.

## Riesgos de seguridad
- Ninguno nuevo. No cambian los permisos: borrar o mover ubicaciones sigue siendo de `InstanceAdmin`, con CSRF y
  auditoría.
- La auditoría guarda nombres de ubicación, no rutas del contenedor, igual que `LOCATION_DELETE`.

## Simplificaciones
- **S1. Aceptada (D4).** No tocar `LocationProjects` ni el endpoint `usage`: el recuento de borrados da 0 por sí solo.
- **S2. Rechazada.** `downgrade` sin comprobación (SQLite fallaría con un error críptico). Se da un mensaje claro y se
  remite a la copia de seguridad.
- **S3. Rechazada (D1).** Soltar las ubicaciones solo al borrar la ubicación.

## Veredicto
**GO_CONDICIONAL**, con estas condiciones:
1. CHECK en la BD y en el modelo, con el comentario de la invariante (T1, T3).
2. Comprobación de deriva de `projects` (T4).
3. Tests:
   - detalle de ejecución de un proyecto borrado (T2);
   - `dry_run` sin efecto (F3);
   - migración con proyectos borrados existentes, en `upgrade` y `downgrade`.
4. Versión 2.3.1. En «Actualizar»:
   - copia de seguridad antes de actualizar;
   - aviso de que la `0029` no se puede deshacer con `downgrade` si ya hay proyectos borrados.
