# PLAN — Fase 9: Multi-tenant y roles (0.10.0)

## 1. Historias y DoD

| ID | Historia | Hecho cuando |
|---|---|---|
| WB-9.1a | Como **admin de instancia**, creo, renombro y borro tenants | `GET/POST /tenants`, `PATCH/DELETE /tenants/{id}`; solo se borra un tenant vacío (409 con usuarios, proyectos, ubicaciones o plantillas); `default` no se borra |
| WB-9.1b | Como admin de instancia, actúo en el tenant que elija | El tenant activo va en la sesión (`user_sessions.acting_tenant_id`); `PUT /auth/tenant` lo cambia; el resto de usuarios siempre actúan en el suyo |
| WB-9.1c | Ningún usuario ve ni toca recursos de otro tenant | Proyectos (y todo lo que cuelga de ellos: runs, documentos, duplicados, contexto, sitio), ubicaciones, plantillas, usuarios, sesiones y auditoría filtrados por tenant **en el dominio**; tests IDOR entre tenants: 404, nunca 403 |
| WB-9.1d | Las ubicaciones son de un tenant | Las registra el admin de instancia y las asigna a un tenant (los montajes son del servidor); un proyecto solo usa ubicaciones de su tenant |
| WB-9.2a | Como administrador de un tenant, creo roles con permisos | Tabla `roles` por tenant y catálogo fijo de permisos; `GET/POST /roles`, `GET/PATCH/DELETE /roles/{id}`; un rol en uso no se borra (409) |
| WB-9.2b | Los usuarios `admin`/`user` siguen funcionando | Migración: `users.role` → `users.role_id` con los roles base «Administrador» y «Usuario» de cada tenant; los `admin` actuales pasan además a admin de instancia |
| WF-9.1 | Pantallas: Tenants, Roles, Usuarios por tenant, selector de tenant | Sustituyen a `admin_tenants.html.j2` y `admin_roles.html.j2`; el menú y las guardas usan permisos, no `role === 'admin'`; Vitest + E2E de aislamiento |

DoD común del ROADMAP: migración con `downgrade`, tests de autorización (401/403/404 e IDOR), OpenAPI y cliente
regenerados, imagen y `/api/health` 200, E2E, guía de usuario, CHANGELOG, `TRACEABILITY.md` y filas de PARIDAD.

## 2. doc_organize

La fase no pide nada de la librería (columna «Requiere»: —). Está fijada la **0.14.0**. Los proyectos de la web no
usan `tenant_id` de doc_organize (obsoleto desde 0.10.0, G4): no cambia nada en la capa anticorrupción. La web
integrada (`doc_organize.web`, `auth/`) es solo la referencia funcional (obsoleta desde 0.14.0, L-10).

Huecos nuevos: ninguno previsto.

## 3. Modelo de permisos

Dos niveles, sin mezclar con los miembros de proyecto:

- **Admin de instancia** (`users.is_instance_admin`): todo lo que es del servidor y no de un tenant:
  - tenants;
  - ubicaciones (registrar, asignar a un tenant, explorar `/mnt`);
  - ajustes administrables, configuración y uso de IA, workers y capacidades;
  - auditoría de todos los tenants.

  Puede actuar en cualquier tenant con el selector.
- **Rol del tenant** (`users.role_id`, un rol por usuario): permisos dentro de su tenant.

| Permiso | Qué permite | Antes |
|---|---|---|
| `users.manage` | Usuarios y sesiones del tenant (alta, edición, desactivar, desbloquear, revocar) | admin |
| `roles.manage` | Roles del tenant | — |
| `audit.read` | Auditoría del tenant | admin |
| `templates.manage` | Plantillas de taxonomía personalizadas del tenant | admin |
| `projects.create` | Crear proyectos | todos |
| `projects.all` | Ver y administrar como `owner` todos los proyectos del tenant (el «bypass» que hoy tiene `admin`) | admin |

- Roles base de cada tenant (no se borran ni cambian sus permisos):
  - **Administrador**: todos los permisos;
  - **Usuario**: `projects.create`.
- Los miembros de proyecto (`owner`/`editor`/`viewer`) no cambian. Un miembro tiene que ser del mismo tenant que el
  proyecto.
- Salvaguardas: siempre queda un admin de instancia activo y, en cada tenant con usuarios, un usuario activo con
  `users.manage`. Nadie se asigna a sí mismo un rol o un permiso que no tiene. Solo el admin de instancia marca a
  otro como admin de instancia.

## 4. Contrato HTTP (`/api/v1`)

| Método | Ruta | Quién | Notas |
|---|---|---|---|
| GET | `/auth/me` | sesión | Añade `tenant {id, slug, name}`, `acting_tenant`, `is_instance_admin`, `role {id, name}` y `permissions: [...]`. Se quita `role: admin\|user` (el frontend pasa a permisos) |
| PUT | `/auth/tenant` | admin de instancia | `{tenant_id}` → cambia el tenant activo de la sesión; auditado (`session.tenant_switch`) |
| GET, POST | `/tenants` | admin de instancia | Listado paginado con recuentos (usuarios, proyectos, ubicaciones); alta con `slug` (`^[a-z0-9][a-z0-9-]{1,62}$`) y `name`. El alta crea sus roles base |
| PATCH, DELETE | `/tenants/{id}` | admin de instancia | Renombrar. Borrar solo si está vacío (409 `tenant_not_empty`); `default` → 409 `tenant_protected` |
| GET, POST | `/roles` | `roles.manage` | Roles del tenant activo con `permissions` y nº de usuarios |
| GET, PATCH, DELETE | `/roles/{id}` | `roles.manage` | Base: 409 `role_builtin`; en uso: 409 `role_in_use`; otro tenant: 404 |
| GET | `/permissions` | `roles.manage` | Catálogo con etiquetas |
| GET, POST, PATCH | `/users…` | `users.manage` | Igual que hoy, pero del tenant activo: `role_id` en lugar de `role`; `is_instance_admin` solo lo cambia un admin de instancia |
| GET | `/tenants/{id}/users` | admin de instancia | Usuarios de un tenant (paridad con `tenants.py`); alta, edición y movimiento entre tenants con `POST/PATCH /users` y `tenant_id` |
| — | Resto | — | Mismas rutas. Por debajo: `TenantScope` en cada consulta del dominio. Otro tenant → 404 |

Cambiar un usuario de tenant (solo el admin de instancia): se le quitan sus membresías de proyecto y se le asigna el
rol «Usuario» del tenant nuevo; se revocan sus sesiones; auditado.

## 5. Modelo de datos — migración `0009_tenants_roles`

- `roles`:
  - `id`, `tenant_id` FK, `name` (único por tenant), `builtin` (`admin`/`user`/`NULL`), `permissions` (JSON con las
    claves del catálogo, validadas);
  - `created_by`, `created_at` y `updated_at`.
- `users`: + `role_id` FK `roles.id` (NOT NULL), + `is_instance_admin` (bool), − `role` (y su `CHECK`).
- `user_sessions`: + `acting_tenant_id` FK nullable (solo para admins de instancia).
- `tenants`: + `updated_at`.
- Datos:
  - crea los roles base de cada tenant existente (solo `default`);
  - `admin` → «Administrador» + `is_instance_admin = true`;
  - `user` → «Usuario».
- `downgrade`: reconstruye `users.role` (`admin` si tiene `projects.all` o es admin de instancia; si no, `user`) y
  borra lo nuevo.

## 6. Aislamiento (ADR-013)

- `domain/tenancy/scope.py`: `TenantScope(tenant_id, user, permissions, instance_admin)`. Lo construye una dependencia
  (`ScopeDep`) a partir de la sesión y lo reciben los servicios de dominio en lugar de `User`.
- Las consultas filtran por `tenant_id` en el dominio, no en el router:
  - en las tablas con columna: `projects`, `locations`, `taxonomy_templates`, `users`, `audit_entries`, `roles`;
  - el resto (runs, artefactos, eventos, documentos, duplicados, contexto, miembros, carpetas escaneadas) por su
    proyecto.
- Los `DEFAULT_TENANT_ID` fijos de `locations/service.py` y del resto pasan a `scope.tenant_id`.
- Un recurso de otro tenant se trata como inexistente (404) para no revelar que existe.
- Worker: no cambia (recibe el `run_id` y el proyecto ya está ligado a su tenant). Las comprobaciones al encolar
  validan que las ubicaciones del proyecto son de su tenant.
- Sitio de contexto (ADR-010): el token ya lleva el proyecto; la validación de miembro usa el scope.
- **Test de arquitectura nuevo**: ningún router usa `user.role` ni filtra por `tenant_id`. Toda consulta a
  `Project`/`Location`/`TaxonomyTemplate`/`User`/`AuditEntry` en `domain/` pasa por `scoped(...)`. Es una
  comprobación estática por AST, como la de la capa anticorrupción.

## 7. Rutas del sistema de ficheros

No hay rutas nuevas. Las ubicaciones siguen bajo `DOW_LOCATIONS_ROOT` y pasan por el resolvedor. El cambio es de
**autorización**: el explorador `/fs/browse` y los proyectos solo aceptan ubicaciones del tenant activo
(autorización antes que existencia, regla 5). Explorar `/mnt` (`/admin/mounts`) sigue siendo solo del admin de
instancia.

## 8. Frontend

| Pantalla | Sustituye a | Contenido |
|---|---|---|
| `/admin/tenants` | `admin_tenants.html.j2` | Tabla con recuentos, alta, renombrar, borrar (deshabilitado si no está vacío), enlace a sus usuarios |
| `/admin/roles` | `admin_roles.html.j2` | Roles del tenant con casillas de permisos; los base, en solo lectura |
| `/admin/users` | (Fase 1) | Selector de rol (del tenant), «admin de instancia» (solo lo ve un admin de instancia), mover de tenant |
| Cabecera | — | Selector de tenant para el admin de instancia (cambia la sesión e invalida todas las consultas) y nombre del tenant para el resto |
| Guardas y menú | — | `can(permission)` y `isInstanceAdmin` desde `/auth/me`; fuera `role === 'admin'` (9 sitios) |

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Fuga entre tenants (IDOR) por una consulta sin filtrar | Scope obligatorio en el dominio y test de arquitectura. Batería IDOR con dos tenants para cada familia de recursos (proyectos y derivados, ubicaciones, plantillas, usuarios, roles, sesiones, auditoría, runs, artefactos, SSE, sitio) |
| Escalada de privilegios con roles | Validación del catálogo; nadie da un permiso que no tiene; solo el admin de instancia crea admins de instancia; salvaguardas del último admin |
| Migración de usuarios existentes | Migración con datos y `downgrade` probados sobre una BD con usuarios `admin`/`user`, proyectos y miembros |
| Sesión con tenant activo de un admin al que le quitan el rol | `acting_tenant_id` se ignora si el usuario ya no es admin de instancia; quitar el permiso revoca sus sesiones |
| Ubicación compartida por error entre tenants | Una ubicación pertenece a un solo tenant; al asignarla, 409 si algún proyecto de otro tenant la usa |
| Volumen de cambios (≈ 40 puntos de autorización) | Primero el scope y los tests IDOR (que fallan), después la migración router a router |

## 10. Pruebas

- **Unit**: catálogo y validación de permisos; salvaguardas (último admin de instancia, último gestor de usuarios);
  migración `0009` arriba y abajo con datos; test de arquitectura del scope.
- **API**:
  - CRUD de tenants y roles con 401/403/404/409;
  - `PUT /auth/tenant` (solo admin de instancia; auditado);
  - IDOR entre dos tenants para cada recurso; usuarios con roles personalizados (p. ej. solo `audit.read`);
  - mover un usuario de tenant (pierde membresías y sesiones).
- **Jobs**: un run de un proyecto del tenant B no es visible ni cancelable desde el A.
- **Frontend**: Vitest de Tenants, Roles, Usuarios (selector de rol), selector de tenant y guardas por permiso.
- **E2E**: el admin crea el tenant B y un usuario de B; ese usuario no ve los proyectos ni las ubicaciones de
  `default`; el admin cambia a B con el selector y sí los ve.

## AUDIT_PLAN

**Contraste con la arquitectura y las reglas**

- **Regla 1** (no tocar doc_organize): no se toca.
- **Regla 2** (no inventar APIs): no se usa API nueva de la librería.
- **Regla 3** (capa anticorrupción): sin cambios.
- **Regla 4** (operaciones pesadas como jobs): no hay operaciones pesadas nuevas. Borrar un tenant exige que esté
  vacío, así que no mueve datos.
- **Regla 5** (ubicaciones): la autorización por tenant va antes que el resolvedor y que la existencia.
- **Regla 6** (secretos): sin secretos nuevos. `ai_settings` sigue siendo de instancia (decisión del mantenedor).
- **Regla 7** (operaciones que borran): borrar un tenant o un rol solo se hace sin dependencias y no borra ficheros.
- **Regla 8** (contrato primero): `export_openapi` y `gen:api` en el mismo cambio. `/auth/me` cambia de forma
  incompatible (`role` → `permissions`); el frontend se adapta en el mismo PR.
- **ADR-003**: la unicidad global del nombre de usuario se confirma (decisión del mantenedor) y el login no cambia.
- **ADR-012**: los ajustes siguen siendo de instancia.
- **ADR-013** (propuesto, «aislamiento en repositorios, no en routers»): se redacta en esta fase.
- **Security Reviewer obligatorio**: la fase toca autorización y sesiones.

**Huecos de doc_organize**: ninguno.

**Filas de PARIDAD que cierra**: las 8 de la Fase 9:
- `admin_roles.html.j2` y `admin_tenants.html.j2`;
- `/api/roles` y `/api/roles/{role_id}`;
- `/api/tenants` y `/api/tenants/{tenant_id}`;
- `/api/tenants/{tenant_id}/users` y `/api/tenants/{tenant_id}/users/{user_id}`.

Con ellas, la paridad queda completa.

**Fuera de alcance**:
- IA por tenant;
- cuotas por tenant;
- login con selección de tenant;
- SSO.

**Decisiones a confirmar por el mantenedor**

- **E1**: las **ubicaciones las registra solo el admin de instancia** y las asigna a un tenant (los montajes son del
  servidor; un admin de tenant podría apuntar a carpetas de otro). Los usuarios del tenant las ven y las usan; no
  hay permiso `locations.manage`.
- **E2**: el **tenant activo del admin de instancia va en la sesión** (`PUT /auth/tenant`) y no en una cabecera por
  petición: así el SSE, las descargas y el sitio usan el mismo contexto sin cambios.
- **E3**: **borrar un tenant solo si está vacío** (sin usuarios, proyectos, ubicaciones ni plantillas). No hay borrado
  en cascada; los usuarios se mueven o se desactivan antes. Un tenant con usuarios desactivados no está vacío: la
  auditoría los referencia.
- **E4**: **los `admin` actuales pasan a admin de instancia y a «Administrador» de `default`**. Los `user` pasan a
  «Usuario».
- **E5**: `/auth/me` deja de devolver `role` (cambio incompatible del contrato, sin consumidores externos todavía).

**Veredicto: `GO_CONDICIONAL`**: listo para implementar cuando se confirmen E1–E5. No hay bloqueos de versión.
