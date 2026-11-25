# ADR-016 — Bloquear y borrar usuarios, y siempre un administrador activo

- **Estado**: Aceptado (web 2.7.0)
- **Fecha**: 2026-11-25
- **Modifica**: [ADR-003](ADR-003-autenticacion-sesiones.md) («los usuarios no se borran»)

## Contexto

Hasta la 2.6 un usuario no se borraba: solo se desactivaba, porque la auditoría lo referencia. Los administradores
necesitan dos cosas: eliminar las cuentas creadas por error o de personas que ya no usan la aplicación, y bloquear una
cuenta de forma visible.

util_bbdd_web ya resolvió lo mismo (su ADR-013 y la enmienda de transferencia). Aquí el modelo de datos es más sencillo.
Las claves foráneas hacia `users` son `CASCADE` solo en `sessions` y `project_members`; el resto son `SET NULL`
(auditoría, `projects.created_by`, `runs.created_by`, artefactos, plantillas, manifiestos…). No hay un `owner_id` en
cascada ni carpetas del workspace por usuario, así que **no hace falta transferir nada**.

Lo que sí se rompería al borrar:

- **Proyectos sin propietario**: si el usuario es el único `owner` de un proyecto, el `CASCADE` de `project_members`
  lo deja sin propietario. La API lo impide al quitar un miembro, pero el `CASCADE` se lo salta.
- **Auditoría sin autor**: `audit_log.actor_user_id` pasa a `NULL`.
- **Runs sin dueño**: un run en cola o en marcha usa `created_by` como dueño de sus artefactos.

La revisión de la regla «siempre un administrador activo» encontró además cinco huecos:

- solo había comprobación previa, así que dos peticiones simultáneas podían quitar a los dos últimos administradores;
- no se detectaba una base de datos sin administradores (por ejemplo, tras restaurar una copia);
- no había forma de recuperar una cuenta existente;
- `PATCH /roles/{id}` podía dejar un tenant sin gestores de usuarios;
- el borrado nuevo también tenía que respetar la regla.

## Decisión

1. **Bloquear es desactivar** (`is_active = false`). No hay un tercer estado.
    - En la interfaz, «Bloqueado» es la cuenta desactivada y «Bloqueado por intentos» es el bloqueo temporal
      (`locked_until`).
    - `PATCH /api/v1/users/{id}` admite `reason` (como mucho 200 caracteres), que solo va a la auditoría
      (`details.reason` de `user.deactivate` y `user.reactivate`).
2. **Borrar solo si no deja nada huérfano.** `DELETE /api/v1/users/{id}` (gestor de usuarios, con `check_can_manage` y
   CSRF) responde `204`, o `409` con `code: user_has_dependencies` y `reasons`:
    - `self`: es la propia cuenta;
    - `last_instance_admin`: es el último admin de instancia activo;
    - `last_manager`: es el último gestor activo de su tenant, salvo que actúe un admin de instancia, igual que al
      desactivar;
    - `sole_owner`: es el único `owner` de algún proyecto. La solución es añadir otro propietario;
    - `active_runs`: tiene runs en cola o en marcha.

    Ser miembro, incluso `owner` junto a otros, no impide borrar: la pertenencia se borra con la cuenta.
    `GET /api/v1/users/{id}/deletion-check` devuelve lo mismo que el `409` (ids, nombres y recuentos; nunca rutas ni
    secretos) para la confirmación, en la que hay que **teclear el nombre de usuario**.
3. **Qué se borra**: sus sesiones y pertenencias (`CASCADE`). Runs, artefactos, plantillas y auditoría quedan sin
   usuario (`SET NULL`). El borrado se audita como `user.delete`, con el nombre, el rol, las sesiones cerradas y los
   proyectos de los que salió.
4. **Auditoría con nombre**: la migración `0032` añade `audit_log.actor_name`, rellenada con el `username` de cada
   actor. `audit.record` la escribe siempre, y la API la muestra (y busca por ella) cuando el usuario ya no existe.
5. **Siempre un administrador de instancia activo (F0)**:
    - **Serializar**: antes de contar, la operación escribe en la fila del usuario afectado, lo que toma el bloqueo de
      escritura de SQLite. Una segunda petición espera (`busy_timeout`) y cuenta ya con el cambio de la primera.
    - **Segunda barrera**: `ensure_instance_admin` vuelve a contar después del cambio (`flush`) y, si no queda ninguno,
      responde `409 last_admin` y la petición se deshace. Se aplica al desactivar, al quitar el admin de instancia y al
      borrar.
    - **Detección**: al arrancar, la API y el worker registran un `logger.critical` (`event: no_active_instance_admin`)
      si no hay ninguno. `POST /api/v1/admin/diagnostics` incluye la comprobación `instance_admins`. `/api/health` no
      lo dice, porque es público.
    - **Recuperación**: `python -m app.cli recover-admin --username <u> [--reset-password | --password-stdin]` sobre un
      usuario existente. Lo reactiva, quita el bloqueo, lo marca como admin de instancia y, si se pide, cambia la
      contraseña (con la política; tecleada o por stdin, nunca como argumento). Cierra sus sesiones y se audita como
      `user.recover`.
    - **Nivel tenant**: `PATCH /roles/{id}` responde `409 last_tenant_manager` si quitar `users.manage` deja el
      tenant sin gestores activos, salvo que actúe un admin de instancia.
    - **Interfaz**: las acciones «Bloquear» y «Borrar» del último admin activo salen deshabilitadas, con un aviso.
      `UserPage.active_instance_admins` solo se rellena para un admin de instancia.

## Consecuencias

- **Positivas**:
    - se pueden limpiar cuentas sin perder datos de otros;
    - la auditoría sigue atribuyendo las acciones;
    - no hay ningún camino de la API que deje la instancia sin administrador, ni siquiera con peticiones simultáneas.
- **Negativas**:
    - Un nombre de usuario borrado puede volver a darse de alta. La auditoría lo distingue por `target_id` y por el
      evento `user.delete`, pero `actor_name` solo guarda el nombre.
    - El bloqueo por intentos del único administrador lo deja fuera unos minutos (`login_lockout_minutes`). Es
      temporal y `recover-admin` lo quita; impedir el bloqueo a los admins abriría el paso a la fuerza bruta.
    - `recover-admin` es una vía de escalada para quien tiene consola en el contenedor. Ese acceso ya permite
      `create-admin` y leer la base de datos, y queda auditado.

## Alternativas descartadas

- **Borrado lógico**: equivale a desactivar, que ya existe.
- **Bloqueo temporal con fecha de fin**: sería un estado más con su caducidad, y nadie lo ha pedido.
- **Transferir proyectos antes de borrar** (como util_bbdd_web): aquí no hay `owner_id` en cascada ni carpetas por
  usuario. `sole_owner` se resuelve con la gestión de miembros que ya existe.
- **Impedir borrar a cualquier miembro**: la pertenencia no deja nada huérfano si hay otros propietarios.
