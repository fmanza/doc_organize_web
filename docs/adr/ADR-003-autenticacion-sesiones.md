# ADR-003 — Autenticación y sesiones

- **Estado**: Aceptado (se implementa en la Fase 1)
- **Fecha**: 2026-10-31

## Contexto

La aplicación es multiusuario en una red interna, detrás de un proxy TLS, con frontend y API en el mismo origen
(ADR-001). La identidad se introduce por fases (D2): primero `admin`/`user` y miembros por proyecto; multi-tenant en la
Fase 9.

## Decisión

1. **Contraseñas** con Argon2id (`pwdlib[argon2]`), longitud mínima (`DOW_PASSWORD_MIN_LENGTH`) y rechazo de
   contraseñas comunes; **bloqueo temporal** tras intentos fallidos (`DOW_LOGIN_*`).
2. **Sesión de servidor**: identificador opaco aleatorio en la cookie `__Host-dow_session`
   (`HttpOnly; Secure; SameSite=Lax; Path=/`), con su hash en la tabla `sessions`; caducidad por inactividad y
   absoluta (`DOW_SESSION_*`), rotación al iniciar sesión y revocación por el admin. En `development` la cookie pierde
   el prefijo `__Host-` (sin TLS local).
3. **CSRF** de doble envío firmado con `dow_app_secret_key` (cookie legible + cabecera `X-CSRF-Token`) en todo método
   no seguro. Sin CORS y sin tokens en `localStorage`.
4. **Sin credenciales por defecto**: el primer admin se crea con `python -m app.cli create-admin`.
5. **`tenant_id` desde el primer día**: `users`, `projects` y `locations` llevan `tenant_id` con una fila `default`,
   para que la Fase 9 (ADR-013) no exija migrar datos.
6. Auditoría (`audit_log`) de inicio y cierre de sesión, cambios de usuarios y acciones administrativas.

## Consecuencias

- `dow_app_secret_key` es obligatorio en producción desde la Fase 0 (la aplicación no arranca sin él).
- Recurso ajeno → `404`, sin revelar existencia.
