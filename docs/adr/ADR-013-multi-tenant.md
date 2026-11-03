# ADR-013 — Multi-tenant y roles

- **Estado**: Aceptado (implementado en la Fase 9, 0.10.0)
- **Fecha**: 2026-11-03

## Contexto

Desde la Fase 1 hay columna `tenant_id` en usuarios, auditoría, ubicaciones, proyectos y plantillas, pero solo se usa
el tenant `default`. La autorización era `admin`/`user` en toda la instancia, más los miembros de cada proyecto.

La web integrada tiene otro modelo: tenants, un admin de instancia y roles que son «admin del tenant» o una lista de
proyectos visibles. Copiarlo chocaría con los miembros por proyecto (`owner`/`editor`/`viewer`), que ya cubren el
acceso fino.

## Decisión

1. **Dos niveles de permiso**:
   - El **admin de instancia** (`users.is_instance_admin`) gestiona lo que es del servidor: tenants, ubicaciones,
     ajustes, IA, workers y capacidades. Tiene todos los permisos en cualquier tenant.
   - El **rol del tenant** (`users.role_id`, uno por usuario) da permisos de administración dentro de su tenant:
     `users.manage`, `roles.manage`, `audit.read`, `templates.manage`, `projects.create` y `projects.all`.
     Cada tenant tiene los roles base «Administrador» (todos) y «Usuario» (`projects.create`).
   - El acceso a cada proyecto sigue siendo por miembros. `projects.all` equivale a `owner` en todos los proyectos del
     tenant.
2. **Aislamiento en el dominio, no en los routers**:
   - El usuario autenticado lleva su **tenant activo** (`User.scope_tenant_id`): el suyo o, si es admin de instancia,
     el que eligió.
   - Las consultas de proyectos, ubicaciones, plantillas, usuarios, sesiones, roles y auditoría filtran por él. Lo que
     cuelga de un proyecto (runs, documentos, duplicados, contexto, sitio) hereda el filtro por el proyecto.
   - Un recurso de otro tenant responde **404**.
   - Un test de arquitectura impide volver a comparar con `role == "admin"` y fijar `DEFAULT_TENANT_ID` fuera de los
     módulos previstos.
3. **El tenant activo va en la sesión** (`sessions.acting_tenant_id`, `PUT /auth/tenant`), no en una cabecera por
   petición (decisión E2): el SSE, las descargas y el sitio aislado lo usan sin cambios. La auditoría de cada petición
   va al tenant activo, y la de un job, al tenant de su proyecto.
4. **Las ubicaciones las registra el admin de instancia** en un tenant (decisión E1). Una ubicación solo cambia de
   tenant si ningún proyecto la usa.
5. **Nombres de usuario únicos en la instancia**: el login no cambia.
6. **Un tenant solo se borra vacío** (decisión E3). Se llevan con él sus roles, y su auditoría pasa a `default`.
7. **Salvaguardas**:
   - nadie da un permiso que no tiene, ni se modifica su propio rol o su condición de admin;
   - siempre queda un admin de instancia activo y alguien que gestione los usuarios de cada tenant;
   - cambiar el rol, quitar permisos o mover a alguien de tenant cierra sus sesiones.
8. **Migración `0009`**: los `admin` pasan a admin de instancia con el rol «Administrador» de `default`, y los `user`,
   a «Usuario». En SQLite, `alembic/env.py` desactiva las claves foráneas durante las migraciones (recrear `users`
   dispararía los `ON DELETE` de sesiones, miembros y auditoría) y comprueba `PRAGMA foreign_key_check` al terminar.

## Consecuencias

- `GET /auth/me` deja de devolver `role` (`admin`/`user`). Ahora trae `tenant`, `acting_tenant`, `is_instance_admin`,
  `role` (el del tenant) y `permissions` (decisión E5).
- `ai_settings`, `app_settings` y los workers siguen siendo de la instancia.
- Fuera de alcance: cuotas por tenant, login con elección de tenant, SSO e IA por tenant.
