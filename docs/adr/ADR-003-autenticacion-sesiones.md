# ADR-003 — Autenticación y sesiones

- **Estado**: Aceptado (implementado en la Fase 1, 0.2.0)
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

## Notas de implementación (Fase 1)

- **Tablas** (`0002_identity`): `tenants` (fila `default`), `users` (`tenant_id`, `username` único en toda la instancia
  y en minúsculas, `role` `admin`/`user`), `sessions` (solo el SHA-256 del token) y `audit_log` (`tenant_id`). La
  unicidad global del nombre de usuario se revisará en ADR-013 (Fase 9).
- **Contraseñas**: Argon2id con `pwdlib` y rehash al iniciar sesión si cambian los parámetros; 12–128 caracteres,
  distinta del nombre de usuario y fuera de las 10 000 más frecuentes de SecLists (MIT,
  `app/domain/identity/data/common_passwords.txt`). Como casi ninguna entrada de la lista llega a 12 caracteres, también
  se compara su núcleo sin dígitos ni símbolos en los extremos (`Password1234!` → `password`).
- **Login**: `401` único para usuario inexistente, desactivado, bloqueado o contraseña errónea, con verificación
  ficticia para igualar tiempos. La auditoría solo guarda el nombre probado si el usuario existe (uno inexistente puede
  ser una contraseña tecleada en el campo equivocado).
- **Bloqueo**: `DOW_LOGIN_MAX_ATTEMPTS` (5) fallos seguidos bloquean `DOW_LOGIN_LOCKOUT_MINUTES` (15); el admin lo
  quita con `PATCH /users/{id}` `{"unlock": true}`, al reactivar o al restablecer la contraseña.
- **Sesión**: cookie `__Host-dow_session` y CSRF `__Host-dow_csrf` (`dow_session`/`dow_csrf` en `development`);
  inactividad `DOW_SESSION_IDLE_MINUTES` (60) y absoluta `DOW_SESSION_ABSOLUTE_HOURS` (12); `last_seen_at` se escribe
  como mucho una vez por minuto. El token CSRF con sesión es `HMAC(dow_app_secret_key, token_de_sesión)`.
- **Sesiones**: el admin ve y revoca todas; cada usuario, solo las suyas (las ajenas dan `404`).
- **Usuarios**: no se borran; desactivar cierra sus sesiones. Ni el último admin activo ni uno mismo pueden perder el
  rol o desactivarse (`409`).
- **CLI**: `python -m app.cli create-admin --username <u> --password-stdin`.
