# PLAN — Borrar y bloquear usuarios, filtros de usuarios y exclusión de carpetas

- **Fecha**: 2026-11-25
- **Skill**: `new-feature` (PLAN + AUDIT_PLAN; detenerse antes de IMPLEMENT)
- **Base**: develop `dd2bcea` (2.6.0), doc_organize 2.5.0
- **Referencia**: util_bbdd_web ADR-013 «Borrado de usuarios sin dependencias» y su enmienda de transferencia (1.22.0)

Hay tres funcionalidades independientes. Cada una va en su propio PR a develop y las tres juntas forman la versión
**2.7.0**.

| Orden | Entrega | Tamaño | Migración |
|---|---|---|---|
| 1 | F1. Buscar usuarios por rol y estado | S | — |
| 2 | F2. Bloquear y borrar usuarios, con F0 (siempre un administrador activo) | M | `0032_audit_actor_name` |
| 3 | F3. Exclusión de carpetas (proyecto, escaneo, duplicados) | M-L | `0033_project_exclusions` |

---

## Situación actual (verificada)

### Usuarios

- **Desactivar** ya existe y funciona como un bloqueo:
    - `User.is_active`, que se cambia con el interruptor de `UserFormModal.tsx` y con `PATCH /users/{id}` `is_active`;
    - cierra las sesiones y se audita (`user.deactivate`, `user.reactivate`);
    - impide quitar el último admin de instancia y el último gestor del tenant (`users.py:288-300`).
- **Bloqueo por intentos fallidos**: `locked_until` y `failed_attempts`, con la opción `unlock` del PATCH (`user.unlock`).
- **No se puede borrar.**
    - El docstring de `User` (`models.py:97`) lo dice: «No se borra: se desactiva (la auditoría lo referencia)».
- **Claves foráneas hacia `users`** (`models.py`, 13 en total):
    - `CASCADE` solo en `sessions` y `project_members`;
    - todas las demás `SET NULL`: auditoría, `projects.created_by`, `runs.created_by`, artefactos, plantillas,
      manifiestos, propuestas, ajustes…
- **Diferencias con util_bbdd_web**, que hacen el caso más sencillo aquí:
    - no hay `projects.owner_id` con `CASCADE`;
    - no hay conexiones;
    - el workspace no cuelga del usuario.
    - Por eso **no hace falta la transferencia con movimiento de carpetas** de su enmienda.
- **Lo que sí se rompería al borrar**:
    - Si es el único `owner` de un proyecto, el `CASCADE` de `project_members` deja el proyecto sin propietario. La API
      lo impide al quitar un miembro (`projects/service.py:617,642`), pero el `CASCADE` se lo salta.
    - `audit_log.actor_user_id` pasa a `NULL` y la auditoría pierde quién hizo cada acción: hay que guardar el nombre.
    - Un run en cola o en marcha usa `created_by` como dueño de sus artefactos (`jobs/context.py:83-90`,
      `worker.py:419`).
- **Búsqueda**: `GET /users?q=` busca en usuario, nombre visible y nombre del rol (`users.py:103-121`). No hay filtro
  exacto por rol ni por estado, aunque la lista ya ordena por `status`.

### Exclusión de carpetas

| Dónde | Qué | Quién |
|---|---|---|
| Carpeta guardada | `ScannedFolder.excluded_subpaths` (≤ 50, relativas): `PUT /projects/{id}/scanned-folders/exclusions`, modal «Excluir carpetas» del escaneo | owner |
| Ubicación | `Location.ignore_patterns` (patrones `fnmatch` sobre el nombre, ≤ 30) | admin |
| Librería | `IGNORED_NAMES = {.git, __pycache__, .DS_Store}`; la carpeta de salidas siempre queda fuera | — |

- El run copia las exclusiones en `ScanParams` (`runs/service.py:172-189`), que se guardan en `run.params` y en
  `run.json`.
- El worker las pasa a `ScanOptions.exclude_paths` / `ignore_patterns` (doc_organize 2.5.0, `core/models.py:575,582`).

**Huecos**:

1. **No hay exclusión a nivel de proyecto.** Hay que repetirla en cada carpeta guardada, y los patrones solo los fija el
   admin, por ubicación.
2. **Duplicados no aplica ninguna exclusión.**
    - Lee la caché (`jobs/operations/dedup.py:59-82`).
    - Sin `force`, lo excluido sigue en `cache.db`, así que **una carpeta excluida sigue apareciendo en duplicados**.
    - La librería tampoco filtra por ruta (`find_duplicates(docs)`, `ContentDuplicateFinder.find(documents)`): hay que
      filtrar antes de llamarla.
3. **Contexto** lee también la caché (`integrations/doc_organize/context.py:684-694`), así que tiene el mismo hueco.
   Su efecto exacto está PENDIENTE DE VERIFICAR.
4. **Carpetas de sistema de NAS y Windows**: `#recycle`, `@eaDir`, `.snapshot`, `~snapshot`, `$RECYCLE.BIN`,
   `System Volume Information`, `Thumbs.db`, `desktop.ini`, `~$*`. La librería no las salta y hay que escribirlas a
   mano en cada ubicación.
5. **Quitar de la caché lo que se acaba de excluir** solo se consigue hoy con «forzar».

---

## F0. Invariante: siempre un administrador activo (transversal, va con F2)

**Regla**: en todo momento existe **al menos un administrador de instancia activo**, es decir, un usuario con
`is_instance_admin = true` e `is_active = true`. Ninguna operación de la API puede dejar la instancia sin él. Si aun así
ocurre (restauración, edición manual de la BD), la aplicación lo detecta, lo avisa y hay un camino de recuperación.

### Revisión de lo que hay hoy (verificado)

| # | Camino | Hoy | Estado |
|---|---|---|---|
| 1 | `PATCH /users/{id}` `is_active=false` (desactivar o «bloquear») | `loses_instance_admin` y `_active_instance_admins(db) <= 1` → `LastAdminError` (`users.py:292-296`) | ✅ comprobación previa |
| 2 | `PATCH` `is_instance_admin=false` | Misma comprobación | ✅ comprobación previa |
| 3 | Desactivarse, quitarse el admin o cambiar el propio rol o tenant | `SelfModificationError` (`users.py:289-290`) | ✅ |
| 4 | Mover de tenant a un admin de instancia | Conserva `is_instance_admin`, y la membresía no influye | ✅ no aplica |
| 5 | Borrar tenant | Exige que esté vacío (`tenants.py:149-160`) | ✅ no aplica |
| 6 | **`DELETE /users/{id}`** (nuevo en F2) | No existe | ➕ hay que cubrirlo |
| 7 | **Dos peticiones simultáneas** que desactivan, quitan el admin o borran a los dos últimos admins | Solo hay comprobación previa: las dos pueden contar 2 y quitar uno cada una. En SQLite WAL la segunda escritura suele fallar con «database is locked» (500), pero no está garantizado ni da un error útil | ❌ hueco |
| 8 | Bloqueo por intentos fallidos del único admin | `locked_until` temporal (`auth.py:77-80`). Cuenta como activo y caduca solo | ⚠️ aceptable, documentar |
| 9 | Restaurar una copia o editar la BD sin admins activos | No se detecta: la aplicación arranca sin aviso | ❌ hueco |
| 10 | Recuperación si el único admin pierde la contraseña o queda desactivado por la BD | `create-admin` solo crea un usuario nuevo y falla si el nombre ya existe (`cli.py:60-77`) | ⚠️ funciona, pero no recupera la cuenta |
| 11 | *Tenant*: quitar `users.manage` a un rol propio con `PUT /roles/{id}` | `update_role` no comprueba `_managers` (`roles.py:150-170`): el tenant puede quedarse sin gestores | ❌ hueco (nivel tenant) |
| 12 | *Tenant*: un admin de instancia deja un tenant sin gestores | Permitido a propósito (`not actor.is_instance_admin`, `users.py:302`): el admin de instancia sigue pudiendo gestionarlo | ✅ por diseño |

### Cambios propuestos

1. **Una función única**, `ensure_instance_admin(db)` en `domain/identity/users.py`.
    - Cuenta los admins activos **después** de aplicar el cambio (con `flush`) y, si hay 0, lanza `LastAdminError`. La
      petición hace *rollback*.
    - La llaman todas las operaciones que pueden quitar un admin: `update_user` (desactivar o quitar admin) y
      `delete_user`.
    - La comprobación previa se mantiene para dar el error antes y sin escribir.
2. **Serializar** esas operaciones.
    - Antes de contar, se escribe en la fila del usuario afectado (`UPDATE users SET updated_at`). Eso toma el bloqueo
      de escritura de SQLite, y la segunda petición espera (`busy_timeout`) en lugar de leer un recuento obsoleto.
    - Resultado: la segunda recibe un `409 last_admin` limpio, no un `500`. Lo cubre un test con dos sesiones.
3. **`DELETE /users/{id}`**: razón `last_instance_admin` en el `409` y en `deletion-check`. Aparece en la tabla de F2.
4. **Detección al arrancar y en diagnóstico**.
    - Si hay 0 admins de instancia activos, el worker y la API registran `logger.critical` con
      `extra={"event": "no_active_instance_admin"}`.
    - `GET /api/v1/admin/diagnostics` añade la comprobación `instance_admins` (`ok`/`error`, con el número), visible en
      «Diagnóstico».
    - `/api/health` **no** cambia: es público y no debe revelarlo.
5. **Recuperación por CLI**: comando nuevo `python -m app.cli recover-admin --username <u> [--password-stdin]`.
    - Sobre un usuario **existente**: lo reactiva, quita el bloqueo, lo marca como admin de instancia y, si se pide,
      cambia la contraseña con la política de siempre (tecleada o por stdin, nunca como argumento).
    - Cierra sus sesiones y se audita como `user.recover` con el actor «cli».
    - Con `create-admin`, que ya existe, cubre los casos «perdí la contraseña» y «se desactivó por la BD».
6. **Nivel tenant** (hueco 11).
    - `update_role` lanza `LastTenantManagerError` si quitar `users.manage` deja el tenant sin gestores activos y quien
      actúa no es admin de instancia, con la misma excepción que en `update_user`.
    - `delete_user` aplica la razón `last_manager` con esa misma excepción.
7. **Interfaz**.
    - En «Usuarios», las acciones «Bloquear», «Quitar admin» y «Borrar» del último admin activo salen
      **deshabilitadas**, con un aviso («Debe quedar al menos un administrador activo»).
    - Para ello `UserPage` añade `active_instance_admins: int` (solo lo ve un admin de instancia).
    - El backend sigue siendo quien decide.
8. **Documentación**: la regla, en `docs/guides/usuarios_y_sesiones.md` (sección «Recuperar el acceso de
   administrador») y en el ADR-016.

**Tests**:

- desactivar, quitar el admin y borrar al último admin → `409`;
- dos sesiones concurrentes sobre los dos últimos admins → una `200`/`204` y otra `409`, con un admin al final;
- `ensure_instance_admin` deshace el cambio;
- `recover-admin` sobre un usuario inactivo y bloqueado;
- diagnóstico con 0 admins;
- `update_role` sin gestores → `409`.

---

## F1. Buscar usuarios por rol y estado

**Objetivo**: filtrar la lista de usuarios por rol y por estado, además del texto.

**Contrato HTTP** (sin cambios incompatibles): `GET /api/v1/users` admite dos parámetros nuevos.

| Parámetro | Tipo | Efecto |
|---|---|---|
| `role_id` | `int`, opcional | Solo usuarios de ese rol del tenant. Un rol de otro tenant devuelve una lista vacía, no un error (no revela nada) |
| `status` | `active \| inactive \| locked`, opcional | `active`: activo y sin bloqueo vigente; `inactive`: desactivado; `locked`: activo con `locked_until` > ahora |
| `instance_admin` | `bool`, opcional | Solo admins de instancia (o solo los que no lo son). Lo ve solo un admin de instancia |

`status` se calcula con la misma regla que la insignia de `UsersPage.tsx:27-36`, con un único reloj (`utcnow()`).

**Rutas**:

- `backend/app/domain/identity/users.py`: `list_users(..., role_id, status, instance_admin)`.
- `backend/app/api/v1/users.py`: los parámetros.
- Contrato: `openapi/openapi.json` y `frontend/src/api/schema.d.ts`.
- `frontend/src/features/admin/UsersPage.tsx`:
    - dos `Select` («Rol», con los roles del tenant de `useRoles`, y «Estado») junto a la búsqueda;
    - «Todos» por defecto;
    - el filtro vuelve a la primera página;
    - estado «Ningún usuario coincide con los filtros», con un botón para quitarlos.
- `frontend/src/features/admin/useAdmin.ts`: `useUsers(query, filters)`.
- i18n `es`/`en`: `admin.users.filter.*`.
- Tests:
    - `tests/api/test_users.py`: cada filtro, combinados, `locked` caducado y `role_id` de otro tenant;
    - `admin.test.tsx`: los filtros envían la query y el estado vacío.

**Pantallas**: «Administración → Usuarios». Estados: carga, vacío con filtros, error y sin permiso (los de hoy).

---

## F2. Bloquear y borrar usuarios

### Decisiones propuestas

- **D1. «Bloquear» es desactivar** (recomendado).
    - No se añade un tercer estado. Desactivar ya cierra las sesiones, impide entrar, se audita y respeta las salvaguardas
      de último admin y último gestor.
    - Lo que falta es que se vea: acciones directas en cada fila, en un menú «⋯»:
        - «Bloquear» / «Desbloquear» (desactivar o reactivar), con confirmación y un **motivo** opcional que va a la
          auditoría (`details.reason`, ≤ 200 caracteres, nunca en la respuesta pública);
        - «Quitar bloqueo por intentos», solo si está bloqueado por intentos;
        - «Borrar».
    - En la interfaz, «Desactivado» pasa a llamarse «Bloqueado» y el bloqueo por intentos, «Bloqueado por intentos».
    - *Alternativa descartada*: un bloqueo temporal con fecha de fin. Sería un estado nuevo con su caducidad, y nadie lo
      ha pedido.
- **D2. Borrar solo si no deja nada huérfano.** Es la estrategia de util_bbdd_web, adaptada a este modelo de datos.
  `DELETE /users/{id}` responde `409` con `reasons` si:
    - `self`: es la propia cuenta;
    - `last_instance_admin`: es el último admin de instancia activo;
    - `last_manager`: es el último gestor activo de su tenant (la regla `_managers` que ya existe);
    - `sole_owner`: es el único `owner` de algún proyecto. Se listan esos proyectos y la solución es añadir otro
      propietario antes de borrar;
    - `active_runs`: tiene runs en cola o en marcha.

    Ser **miembro** (editor o viewer, o `owner` junto a otros) **no bloquea**: la pertenencia se borra con la cuenta y la
    confirmación enumera los proyectos afectados. Aquí no hay nada que se borre en cascada más allá de la pertenencia,
    a diferencia de util_bbdd_web.
- **D3. No hay transferencia.** No hace falta, porque no hay `owner_id` en cascada ni carpetas por usuario. La única
  dependencia (`sole_owner`) se resuelve con la gestión de miembros que ya existe.
- **D4. Se borra sin desactivar antes** (como util_bbdd_web), pero **escribiendo el nombre de usuario** en la
  confirmación. Es irreversible y el CSRF ya protege la petición.

### Contrato HTTP

| Método y ruta | Permiso | Respuesta |
|---|---|---|
| `GET /api/v1/users/{id}/deletion-check` | gestor de usuarios (`UserManager`) y `check_can_manage` | `200 UserDeletionCheck` |
| `DELETE /api/v1/users/{id}` | ídem, con CSRF | `204`; `404`; `403` (escalada); `409` problem con `reasons` y los datos de `UserDeletionCheck` |
| `PATCH /api/v1/users/{id}` | ya existe | Admite `reason: str \| None` (≤ 200) para el motivo de desactivar o reactivar |

`UserDeletionCheck` contiene:

- `can_delete: bool`;
- `reasons: list[Literal[...]]`;
- `sole_owner_projects: list[{id, name}]`;
- `memberships: list[{id, name, role}]`;
- `active_runs: int`;
- `sessions: int`.

Solo ids y nombres, nunca rutas ni secretos. Un gestor de tenant solo ve proyectos de su tenant, y el usuario lo es
siempre.

### Modelo de datos

- Migración **`0032_audit_actor_name`**:
    - `audit_log.actor_name String(64) NULL`, rellenada con el `username` de cada actor;
    - `audit.record` la escribe siempre;
    - `AuditEntryOut.actor_username` usa `actor_name` cuando el usuario ya no existe.
- `User`: actualizar el docstring («se desactiva o se borra si no deja nada huérfano»).
- Auditoría:
    - `user.delete` con el username, el rol, el tenant, cuántas sesiones se cerraron y la lista de proyectos de los que
      salió;
    - `user.deactivate`/`reactivate` con `reason`.

### Concurrencia y seguridad

- **Escribir primero en la fila del usuario** (`UPDATE users SET updated_at`), lo que toma el bloqueo de escritura de
  SQLite. Después se comprueban las razones y se hace el `DELETE`. Así nadie lo añade como único `owner` ni le encola
  un run entre la comprobación y el borrado (patrón de ADR-013 §5).
- **Tras el `DELETE`**, antes de confirmar, se vuelven a contar los admins de instancia y los gestores del tenant. Si no
  queda ninguno, se deshace.
- **El `404` y el `403` siguen el orden de hoy**: `get_user` limitado al tenant, después `check_can_manage`. Un gestor
  no borra a un admin de instancia ni a alguien con más permisos.
- **Se puede volver a dar de alta el mismo nombre de usuario.** La auditoría distingue por `target_id` y por el evento
  `user.delete`.

### Rutas

- Backend:
    - `domain/identity/users.py`: `deletion_check` y `delete_user`.
    - `domain/identity/errors.py`: `UserDeletionConflictError` con `reasons`.
    - `domain/identity/audit.py`: `USER_DELETE` y `actor_name`.
    - `api/v1/users.py` y `api/v1/schemas.py`.
    - `core/errors.py`: el problem con `reasons` (extensión RFC 9457).
    - `db/models.py` y `db/migrations/versions/0032_audit_actor_name.py` (nuevo).
- Tests:
    - `tests/api/test_users.py`: cada razón del `409`, `204` y borrado en cascada de sesiones y pertenencias,
      `SET NULL` en runs y auditoría, nombre en la auditoría, gestor contra admin `403` y tenant ajeno `404`;
    - `tests/unit/test_migrations.py`: 0032 sube y baja.
- Contrato: OpenAPI y `schema.d.ts`.
- Frontend:
    - `features/admin/UsersPage.tsx`: menú de acciones por fila.
    - `features/admin/UserBlockModal.tsx` (nuevo): bloquear o desbloquear con motivo.
    - `features/admin/UserDeleteModal.tsx` (nuevo):
        - carga `deletion-check`;
        - si no se puede borrar, muestra las razones con enlaces a los proyectos;
        - si se puede, muestra el resumen de lo que se borra y un campo para escribir el usuario.
    - `useAdmin.ts`: `useUserDeletionCheck`, `useDeleteUser` y `useSetUserActive`.
    - `AuditPage.tsx`: actor «(borrado)».
    - i18n `es`/`en`.
    - `admin.test.tsx`.
- Documentación:
    - `docs/adr/ADR-016-borrado-de-usuarios.md` (nuevo), que modifica la regla «no se borra» de ADR-003/ADR-013
      multi-tenant;
    - `docs/guides/usuarios_y_sesiones.md`.
- E2E: `e2e/users.spec.ts`: bloquear, comprobar que no entra, desbloquear y borrar.

---

## F3. Exclusión de carpetas

### Propuesta: una única «exclusión efectiva» en tres niveles

```text
exclusión efectiva = proyecto (nuevo) ∪ carpeta guardada (existe) ∪ patrones de la ubicación (existe) ∪ preset de sistema (nuevo)
```

Se aplica igual en **escaneo/conversión**, **duplicados** y **contexto**. Una carpeta excluida está fuera del proyecto
a todos los efectos.

1. **Exclusiones del proyecto** (nuevo, owner).
    - `projects.excluded_paths` JSON (≤ 100): rutas relativas a la **ubicación origen**, validadas con el resolvedor
      como `_check_exclusion` (dentro del origen, sin `..`, sin enlaces). Si no existen, se guardan tal como se
      escribieron y se marcan como «no existe».
    - `projects.ignore_patterns` JSON (≤ 30): patrones de nombre, con las mismas reglas que `check_ignore_patterns`.
      Por ejemplo `borradores`, `*.tmp` u `old_*`.
    - `projects.exclude_system_folders` bool, por defecto `true` en proyectos nuevos y `false` en los existentes para no
      cambiar resultados sin avisar. Activa un **preset** fijo de patrones: `#recycle`, `@eaDir`, `.snapshot`,
      `~snapshot`, `$RECYCLE.BIN`, `System Volume Information`, `Thumbs.db`, `desktop.ini` y `~$*`. Todos caben en
      `ignore_patterns` de la librería (nombre, sin `/`, ≤ 64 caracteres).
2. **Escaneo** (cambio menor).
    - `_validate_scan` añade a `ScanParams` las del proyecto, ya convertidas a relativas de cada carpeta guardada, junto
      con sus patrones y el preset.
    - El límite de 50 por carpeta pasa a contar la unión, y se rechaza con `422` si se supera.
    - El modal «Excluir carpetas» del escaneo muestra también, en solo lectura, las heredadas del proyecto, con un
      enlace a los ajustes.
3. **Duplicados** (nuevo).
    - `DedupParams` guarda la exclusión efectiva al encolar (copia, como en el escaneo).
    - El worker filtra los documentos de la caché **antes** de `find_duplicates` y `ContentDuplicateFinder.find` con
      `EntryFilter.covers_cached`, a través de la capa anticorrupción (`integrations/doc_organize/dedup.py`; nada fuera
      importa doc_organize).
    - El resumen del run añade `excluded: int`.
    - **Exclusión puntual en el lanzamiento**: el modal de duplicados admite `extra_excluded_paths` (≤ 50) solo para ese
      run, para casos como «no comparar contra `Archivo/2019`» sin tocar el proyecto. Se guardan en `run.params` y se
      muestran en el detalle del run.
4. **Contexto** (nuevo). La misma exclusión efectiva filtra `load_cache_entries` antes de clasificar y construir el
   contexto. Hay que verificar en IMPLEMENT que no rompe el contexto incremental: un documento que pasa a estar excluido
   debería salir del contexto en la siguiente construcción.
5. **Invalidación**:
    - si cambian las exclusiones del proyecto, la vista previa de «forzar» deja de valer, como ya pasa con las de
      carpeta (`operations.py:388-389`);
    - la pantalla de duplicados avisa de que «Las exclusiones cambiaron después del último análisis».
6. **Quitar lo excluido de la caché** (mejora; se propone **dejarla fuera de esta entrega**).
    - Hoy solo se consigue con «forzar», que reconvierte todo.
    - Lo limpio sería una operación «Purgar excluidos» con vista previa y confirmación (regla 7). Habría que comprobar si
      doc_organize puede borrar entradas de la caché por ruta, y si no, abrir un hueco en `DOC_ORGANIZE_GAPS.md`.
    - Mientras tanto, el filtro de los puntos 3 y 4 hace que lo excluido no aparezca, aunque siga ocupando la caché.

### Contrato HTTP

| Método y ruta | Permiso | Cambio |
|---|---|---|
| `GET /api/v1/projects/{id}/exclusions` | miembro | `ProjectExclusions{excluded: [{path, exists}], ignore_patterns, exclude_system_folders, system_patterns}` (nuevo) |
| `PUT /api/v1/projects/{id}/exclusions` | owner, CSRF | Body `ProjectExclusionsUpdate`; `422` si una ruta sale del origen o un patrón no es válido; audita `project.exclusions` (nuevo) |
| `POST /api/v1/projects/{id}/runs` (dedup) | editor | `DedupParams.extra_excluded_paths` opcional |
| `GET /api/v1/runs/{id}` | miembro | `params` muestra la exclusión efectiva usada (rutas relativas, nunca absolutas) |

### Modelo de datos

Migración **`0033_project_exclusions`**:

- `projects.excluded_paths JSON '[]'`;
- `projects.ignore_patterns JSON '[]'`;
- `projects.exclude_system_folders bool`, `server_default false`; el servicio de alta pone `true`.

### Rutas

- Backend:
    - `domain/projects/exclusions.py` (nuevo): validar, normalizar y colapsar, y construir la exclusión efectiva por
      carpeta.
    - `domain/scan/folders.py`: reutilizar `_check_exclusion` y `_collapse` (exportarlos sin cambiar su lógica).
    - `domain/runs/service.py` y `operations.py`: `ScanParams` y `DedupParams`.
    - `jobs/operations/dedup.py` y `jobs/operations/context*.py`: filtrar.
    - `integrations/doc_organize/dedup.py` y `context.py`: `filter_cached(documents, exclusion)` sobre `EntryFilter`.
    - `api/v1/projects.py` y `schemas.py`.
    - Migración 0033.
- Tests:
    - unit: exclusión efectiva y preset;
    - api: PUT/GET, `422` y permisos;
    - jobs: duplicados con una carpeta excluida que sigue en la caché no aparece, y lo mismo en contexto;
    - migraciones.
- Frontend:
    - `features/projects/ProjectExclusionsCard.tsx` (nuevo) en los ajustes del proyecto: explorador de carpetas del
      origen (el de `ExcludeFoldersModal`), patrones e interruptor del preset con la lista visible.
    - `ScanPage.tsx`: heredadas en solo lectura.
    - Modal de lanzar duplicados: «Excluir además en este análisis».
    - `RunDetail`: exclusiones usadas.
    - i18n `es`/`en`.
    - tests.
- Documentación:
    - `docs/guides/` (escaneo y duplicados): sección «Excluir carpetas»;
    - ADR-017 (exclusión efectiva y su alcance).
- doc_organize: **nada nuevo**. Se usa `ScanOptions.exclude_paths`/`ignore_patterns` y `EntryFilter`, verificados en
  2.5.0. Lo único que queda es el posible hueco de «purgar de la caché por ruta» (punto 6).

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Borrar al único `owner` deja proyectos huérfanos por el `CASCADE` | Razón `sole_owner` y escritura previa en la fila (bloqueo SQLite) |
| La auditoría pierde al autor | `actor_name` con relleno en la migración |
| Borrar con runs vivos deja `created_by` a `NULL` en mitad del job | Razón `active_runs` |
| Cambiar las exclusiones cambia los resultados de duplicados y contexto ya vistos | Copia en `run.params`, aviso de «las exclusiones cambiaron» y preset desactivado en los proyectos existentes |
| Patrones demasiado amplios (`*`) vacían el proyecto | Rechazar `*`, `**` y `*.*`; la vista previa de escaneo cuenta los excluidos |
| `extra_excluded_paths` con traversal | Mismo resolvedor y `_check_exclusion`; autorización antes que existencia |
| Contexto incremental incoherente al excluir | Test de jobs; si no se puede filtrar sin romperlo, el contexto queda fuera y se documenta |
| Rendimiento con unos 100 000 documentos | El filtro es por prefijo normalizado (O(n·k), k ≤ 150) y se hace una vez por run |

---

## AUDIT_PLAN

### Funcional

- Una sola exclusión para todo el proyecto es lo que se espera: «excluir» significa que no forma parte del proyecto.
  Excluir solo en duplicados, sin tocar el escaneo, queda cubierto por `extra_excluded_paths`, que solo afecta a ese
  run.
- «Bloquear» como alias de desactivar evita dos conceptos casi iguales. El cambio de nombre en la interfaz («Bloqueado»
  frente a «Bloqueado por intentos») hace falta para que no se confundan.
- F1 es independiente y pequeña: se puede adelantar.

### Técnico

- No hay dependencias nuevas.
- Dos migraciones, ambas solo con columnas nuevas (sin recrear `users`, la lección de util_bbdd_web 1.21.1).
- doc_organize no cambia y sus firmas están verificadas. Solo la capa anticorrupción usa `EntryFilter`.
- Reutilizar `_check_exclusion` y `_collapse` obliga a exportarlos. Es un cambio mínimo necesario, no un refactor.
- El límite de 50 exclusiones por carpeta se aplica a la unión; puede haber carpetas que hoy estén cerca del límite.
  Se valida al lanzar y en el PUT del proyecto, que avisa si alguna carpeta lo superaría.

### Seguridad

- **Borrado**:
    - `UserManager`, `check_can_manage` (sin escalada), CSRF y confirmación por nombre;
    - el `409` solo expone ids y nombres de proyectos de su tenant;
    - el motivo del bloqueo solo va a la auditoría, y se limita su longitud.
- **Exclusiones**:
    - pasan por el resolvedor de ubicaciones; la autorización (owner) se comprueba antes que la existencia;
    - en `run.params` y en las respuestas van rutas relativas, nunca absolutas ni de servidor (repositorio público).
- **Ningún secreto afectado.**

### Simplificaciones aplicadas

- Sin transferencia (D3), sin bloqueo temporal (D1) y sin purga de la caché (punto 6, para después).
- Sin filtro de exclusiones en el listado de documentos: lo que aparece ahí es la caché. Se puede añadir después con la
  misma función.

### Invariante de administrador (F0)

- **Cubre todos los caminos de la API** que pueden quitar un admin activo: desactivar, quitar el admin y borrar.
- **Resuelve la carrera** que hoy queda abierta: escritura previa más recuento posterior.
- **Si se llega a cero por fuera de la API**, se detecta y hay forma de recuperar la cuenta sin tocar la BD a mano.
- **El bloqueo por intentos no rompe la regla**: es temporal y `recover-admin` lo quita. Un atacante que fuerce
  intentos sobre todos los admins solo los retrasa unos minutos (`login_lockout_minutes`), y eso ya pasa hoy.
- **Riesgo**: `recover-admin` es una vía de escalada para quien tenga acceso a la consola del contenedor. Es aceptable,
  porque ese acceso ya permite `create-admin` y leer la BD. Queda auditado.
- **Simplificación descartada**: impedir el bloqueo por intentos a los admins. Abriría el paso a la fuerza bruta.

### Veredicto: **GO_CONDICIONAL**

Condiciones:

1. Confirmar que «administrador» es el **admin de instancia**, y que el gestor de tenant mantiene su regla actual,
   ampliada al hueco 11.
2. Confirmar D1 (bloquear = desactivar), D2 (miembro no bloquea el borrado; `sole_owner` y `active_runs` sí), D4
   (escribir el nombre, sin desactivar antes) y el preset de carpetas de sistema activado solo en proyectos nuevos.
3. En IMPLEMENT de F3, verificar el contexto incremental antes de incluirlo. Si no es seguro, F3 sale solo con escaneo
   y duplicados, y el contexto se documenta como pendiente.
4. Orden de entrega F1 → F2 (con F0) → F3, un PR cada una.

---

## AUDIT_PLAN (revisión 2, tras aprobar las decisiones)

**Decisiones aprobadas por el usuario (2026-11-25)**: D1, D2, D3, D4, F0, preset de carpetas de sistema solo en
proyectos nuevos, «administrador» = admin de instancia (el gestor de tenant conserva su regla, ampliada al hueco 11) y
orden F1 → F2 (con F0) → F3.

Esta revisión contrasta el plan con el código. Las correcciones **sustituyen** a lo dicho arriba.

### Hallazgos y correcciones

| # | Gravedad | Hallazgo (verificado) | Corrección |
|---|---|---|---|
| A1 | Alta | La caché no la leen solo duplicados y contexto. También `integrations/doc_organize/export.py` (ZIP, Excel, sitio, paquete IA), el índice de búsqueda (`jobs/operations/search_index.py`) y el listado de documentos (`integrations/doc_organize/cache.py`). Si solo se filtran duplicados y contexto, «excluido = fuera del proyecto» no se cumple | El filtro `apply_exclusions(entries, exclusion)` va en la capa anticorrupción y se aplica en **todos los lectores de la caché por lotes**: duplicados, contexto, exportaciones e índice de búsqueda. El **listado de documentos** se pagina en SQL dentro de doc_organize (`load_cache_page`) y no admite filtrar por lista de prefijos: se deja como está y se muestra un aviso «N documentos de la caché están excluidos y no se usan en duplicados, contexto, búsqueda ni exportaciones» (con `count_entries` y el filtro en memoria solo para contar) |
| A2 | Alta | `CacheManager` (doc_organize 2.5.0, `cache/cache_manager.py`) no tiene borrado por ruta: solo `clear()` y `save_entries()`. Quitar lo excluido exige hoy `force`, que reconvierte todo | Se abre el hueco **G47** en `DOC_ORGANIZE_GAPS.md`: «borrar de la caché las entradas excluidas (por `EntryFilter`) y filtro de exclusión en `load_cache_page`/`count_entries`». El **rodeo** es el filtro en memoria de A1. La purga sigue fuera de esta entrega |
| A3 | Media | Duplicados son dos operaciones: `DedupPreviewParams` (`operations.py:145`) y `DedupApplyParams` (`:177`), que aplica los grupos de una vista previa. No hay `DedupParams` | La exclusión efectiva y `extra_excluded_paths` se copian en **`DedupPreviewParams`**. `DedupApplyParams` usa los grupos de esa vista previa sin volver a filtrar. Si las exclusiones del proyecto cambiaron después de la vista previa, `apply` responde **`409 exclusions_changed`** y pide otra (regla 7: lo que se mueve es lo que se vio). Es lo mismo que ya pasa con «forzar» |
| A4 | Media | `ScanParams.ignore_patterns` admite como mucho 30 y `exclusions`, 50 por carpeta (`operations.py:79-84`). La unión llega a 69 patrones (30 de la ubicación + 30 del proyecto + 9 del preset) y a 150 rutas (50 de la carpeta + 100 del proyecto) | Subir los máximos de `ScanParams` a **100 patrones** y **150 exclusiones por carpeta**. Es compatible con los `run.params` guardados. `DedupPreviewParams` y `ContextBuildParams` usan los mismos máximos |
| A5 | Baja | El diagnóstico es `POST /api/v1/admin/diagnostics` (`api/v1/ai.py:253`, `domain/ai/diagnostics.py`), no `GET` | La comprobación `instance_admins` va en ese `POST`, sin IA y siempre incluida. El log crítico al arrancar no cambia |
| A6 | Baja | `check_ignore_patterns` (`locations/service.py:122`) admite `*` | Solo en el nivel de proyecto se rechazan además `*`, `**`, `*.*` y `?*` (vaciarían el proyecto). Las ubicaciones no cambian: no se refactoriza |
| A7 | Baja | El test de concurrencia de F0 necesita una SQLite **en fichero** y dos sesiones. `busy_timeout=5000` ya está configurado (`db/session.py:22`) | Test en `tests/api` con `tmp_path`, dos `Session` e hilos: una operación termina y la otra recibe `409 last_admin` |
| A8 | Info | `UserPage` (`schemas.py:148`) solo tiene `items` y `total` | `active_instance_admins: int \| None`, con valor solo para un admin de instancia |

### Comprobaciones que el plan supera

- **Compatibilidad hacia atrás**: los campos nuevos de `*Params` son opcionales y tienen valor por defecto, así que los
  `run.params` guardados se siguen leyendo. Las migraciones 0032 y 0033 solo añaden columnas.
- **Capa anticorrupción**: `EntryFilter` y `covers_cached` solo se usan en `integrations/doc_organize/`. Lo vigila el
  test de arquitectura.
- **Autorización**:
    - las exclusiones del proyecto las gestiona el owner;
    - `extra_excluded_paths` lo puede pasar un editor, porque solo reduce el alcance y no escribe;
    - borrar y bloquear exige `UserManager` y `check_can_manage`;
    - en todos los casos la autorización se comprueba antes que la existencia.
- **Sin secretos ni rutas absolutas** en respuestas, `run.params` o auditoría (el motivo del bloqueo solo va a la
  auditoría).
- **Escala** (~100 000 documentos): el filtro en memoria compara prefijos normalizados en O(n·k), con k ≤ 250, una vez
  por run. Es aceptable y no carga nada nuevo de la caché que el run no cargara ya.
- **i18n**: todos los textos nuevos van en `es` y `en`. Lo vigila `i18n.test.ts`.
- **doc_organize**: no se modifica. Todo lo que hace falta está verificado en 2.5.0, salvo la purga (G47).

### Veredicto: **GO**

Las condiciones de la revisión 1 están resueltas por las decisiones del usuario y por A1–A8. La comprobación del
contexto incremental (condición 3) se mantiene como verificación en IMPLEMENT de F3: si no es segura, el contexto sale
del filtro y se documenta.

**Siguiente paso**: IMPLEMENT de **F1** (rama `feat/usuarios-filtros`), cuando lo apruebes.
