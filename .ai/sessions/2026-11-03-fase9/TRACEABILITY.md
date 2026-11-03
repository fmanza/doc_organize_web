# TRACEABILITY

## Session metadata
- id: 2026-11-03-fase9
- fecha: 2026-11-03
- rama: `feature/fase-9` (desde develop `1b36411`: 0.9.0 + doc_organize 0.14.0); sin commit todavía
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
`/phase 9`, con limpieza previa de ramas locales (solo quedan `develop` y `main`). Inputs del mantenedor
([00_REQUEST.md](00_REQUEST.md)):
- alcance completo;
- roles como permisos de administración del tenant;
- nombres de usuario únicos en la instancia;
- sin mejoras opcionales.

«IMPLEMENT» se tomó como aprobación de E1–E5 tal como estaban en el [PLAN](PLAN.md).

## Context supplied
- ROADMAP (Fase 9), PARIDAD (8 filas de la Fase 9), ADRS_PROPUESTOS (013), ADR-003 y TRACEABILITY de la Fase 8.
- Web integrada de doc_organize como referencia funcional, en solo lectura: `web/routes/tenants.py`,
  `web/routes/admin.py` (roles) y los modelos `Tenant`/`Role` de `core/models.py`. Su modelo (rol = admin del tenant o
  lista de proyectos) no se copia.
- Código propio: ~40 puntos de autorización con `role == "admin"` y `DEFAULT_TENANT_ID` fijo en ubicaciones,
  proyectos y auditoría.

## AI output summary
- **PLAN + AUDIT_PLAN**: `GO_CONDICIONAL`. E1–E5 quedaron aceptadas.
- **IMPLEMENT backend**:
  - migración `0009_tenants_roles`: tabla `roles`, `users.role_id`, `users.is_instance_admin`,
    `sessions.acting_tenant_id` y `tenants.updated_at`, con migración de datos y `downgrade`;
  - `domain/tenancy/` (`permissions`, `roles`, `tenants`, `errors`);
  - `User.scope_tenant_id`, `User.can()` y `User.permissions`; `sessions.acting_user()`;
  - dependencias `InstanceAdmin` y `require_permission(...)`;
  - routers `tenancy.py`, `PUT /auth/tenant` y `/auth/me` nuevo;
  - usuarios con `role_id`, `is_instance_admin` y `tenant_id`, con sus salvaguardas;
  - ubicaciones, proyectos, runs, plantillas, sesiones y auditoría filtrados por el tenant activo;
  - auditoría por tenant: `db.info["tenant_id"]` en la API y `bind_tenant` en el job;
  - CLI `create-admin`: admin de instancia.
- **IMPLEMENT frontend**:
  - `TenantsPage`, `RolesPage`, `TenantSwitcher` en la cabecera y `RequireAccess` por permiso;
  - formulario de usuario con rol, admin de instancia y tenant;
  - menú por permisos; traducciones.
- **Desviación del PLAN**: el `TenantScope` del PLAN no es un objeto aparte. Va en el propio `User` autenticado
  (`scope_tenant_id` y `can()`, fijados por `acting_user`) para no reescribir la firma de todos los servicios. El test
  de arquitectura `test_authorization_uses_permissions_and_the_active_tenant` cubre la regla.
- **Hallazgos al implementar**:
  - Recrear `users` en SQLite disparaba los `ON DELETE CASCADE/SET NULL`: se borraban las sesiones y la auditoría
    perdía el actor; con `project_members` habría pasado lo mismo. `alembic/env.py` desactiva ahora las claves
    durante las migraciones y comprueba `PRAGMA foreign_key_check`. Lo cubre
    `test_0009_keeps_users_sessions_and_audit`.
  - FastAPI ejecuta las dependencias síncronas con una copia del contexto, así que un `contextvar` no llega al
    endpoint. El tenant de la petición va en `db.info`.
  - `Result.tuples()` está obsoleto en SQLAlchemy 2.1, y los tests convierten los avisos en errores.
- **AUDIT_CODE** (revisión propia con los checklists de Code Auditor, Frontend Reviewer y Security Reviewer):
  - **HIGH corregido**: alguien con `users.manage` sin ser admin de instancia podía restablecer la contraseña de un
    admin de instancia (o de quien tuviera más permisos) y quedarse con su cuenta. Ahora `check_can_manage` exige
    tener todo lo del otro para editarlo o cerrar sus sesiones. Test:
    `test_a_tenant_admin_cannot_take_over_a_stronger_account`.
  - Batería IDOR entre dos tenants: 404 en proyectos y derivados, runs y SSE, ubicaciones, explorador, usuarios,
    plantillas y roles. Listados vacíos de lo ajeno en proyectos, runs, ubicaciones, usuarios, búsqueda, sesiones y
    auditoría.
- **VERSION**:
  - 0.10.0 en backend, frontend, OpenAPI, `uv.lock`, `package-lock.json` y `.env.example`;
  - CHANGELOG, que incluye la adopción de doc_organize 0.14.0 que estaba en «Unreleased»;
  - ROADMAP, PARIDAD (completa: 8 filas de la Fase 9 en ✅) y ADRS_PROPUESTOS;
  - ADR-013, guía `tenants_y_roles.md`, `usuarios_y_sesiones.md`, `docs/README.md` y `product.md`.
- **Validación**:
  - backend en Linux (`backend-dev`): ruff, mypy, pytest y OpenAPI `--check`;
  - frontend: format, lint, typecheck, 85 tests y build;
  - `zensical build --strict`;
  - imagen con `/api/health` 200;
  - E2E 15/15 con `tenancy.spec.ts`, contra la BD del E2E migrada desde la 0.9.0 con datos reales de fases
    anteriores.
  - En Windows siguen fallando los mismos tests de rutas que antes de la fase (comparado con `git stash` sobre
    `develop`: 18 en `tests/jobs`, sin fallos nuevos).

## Artefactos generados
- `backend/alembic/versions/0009_tenants_roles.py`, `backend/alembic/env.py`, `backend/app/domain/tenancy/`,
  `backend/app/api/v1/tenancy.py`
- `backend/tests/api/test_tenancy.py`; tests nuevos en `tests/unit/test_architecture.py` y
  `tests/unit/test_migrations.py`
- `frontend/src/features/admin/{TenantsPage,RolesPage,useTenancy,tenancy.test}.tsx?`,
  `frontend/src/app/TenantSwitcher.tsx`, `frontend/e2e/tenancy.spec.ts`
- `docs/guides/tenants_y_roles.md`, `docs/adr/ADR-013-multi-tenant.md`
- `build/logs/fase9-*.txt` (local, ignorado por git)

## Directrices para Futuras IAs
- **[tenancy]**: toda autorización parte de `sessions.acting_user(session)` o de `CurrentUser`. Nunca uses
  `session.user` directamente: perderías el tenant activo del admin de instancia.
- **[tenancy]**: filtra por `user.scope_tenant_id`, nunca por `user.tenant_id` (es el tenant al que pertenece, no en
  el que actúa) ni por `DEFAULT_TENANT_ID`. Lo vigila `test_authorization_uses_permissions_and_the_active_tenant`.
- **[tenancy]**: un recurso de otro tenant responde 404 (`*NotFoundError`), nunca 403.
- **[permisos]**: autoriza con `user.can("<permiso>")`, `require_permission(...)` o `InstanceAdmin`. El catálogo vive
  en `domain/tenancy/permissions.py` y en la migración `0009`; si añades un permiso, cambia los dos y el
  `PERMISSIONS` del frontend.
- **[permisos]**: antes de modificar a un usuario o cerrar sus sesiones llama a `check_can_manage(actor, target)`.
  Antes de dar un rol o un permiso, a `check_grant(actor, permisos)`.
- **[auditoría]**: el tenant de un evento sale de `db.info["tenant_id"]` en la API y de `bind_tenant` en el job.
  Pasa `tenant_id=` explícito solo cuando el evento es de otro tenant (p. ej. el borrado de un tenant va a
  `default`).
- **[migraciones]**: en SQLite, una migración «batch» que recrea una tabla referenciada es segura porque `env.py`
  desactiva las claves y comprueba `PRAGMA foreign_key_check`. No quites eso. Prueba la migración con datos en las
  tablas hijas.
- **[fastapi]**: no uses `contextvars` para datos de la petición fijados en una dependencia síncrona: FastAPI la
  ejecuta en un hilo con una copia del contexto. Usa `db.info` o el propio objeto.
- **[frontend]**: las guardas y el menú van por `can(me, permiso)` y `me.is_instance_admin`. El `Select` de Mantine
  tiene rol `combobox` en Playwright y Testing Library.

## Pendientes (no bloquean)
- Cuotas por tenant, login con elección de tenant, SSO e IA por tenant (fuera de alcance).
- `users.update_user` tiene una complejidad cognitiva alta (aviso de Sonar). Conviene partirla en un refactor.
- Los enlaces deshabilitados «Fase N» del menú siguen pendientes de retirar (vienen de la Fase 8).

## Veredicto final
GO — Fase 9 cerrada en 0.10.0 con doc_organize 0.14.0. Paridad completa con la web integrada.
