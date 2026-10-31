# PLAN + AUDIT_PLAN — Fase 1 (Identidad y multiusuario → 0.2.0)

## PLAN

### Historias y DoD

- Como **admin** creo usuarios, cambio su nombre visible y rol (`admin`/`user`), restablezco su contraseña, los
  desactivo y reactivo, y quito un bloqueo por intentos.
- Como **usuario** inicio y cierro sesión y cambio mi contraseña.
- Como **admin** veo y revoco sesiones y consulto la auditoría, con filtros.
- Sin credenciales por defecto: el primer admin se crea por CLI.

DoD común del ROADMAP: comandos en verde, OpenAPI + cliente, migración `0002` con `downgrade`, tests 401/403/404 e
IDOR, imagen + `/api/health`, CHANGELOG, guía de usuario, TRACEABILITY y filas de `PARIDAD.md` de la Fase 1 marcadas.

### Modelo de datos — Alembic `0002_identity`

| Tabla | Columnas | Notas |
|---|---|---|
| `tenants` | `id`, `slug` (único), `name`, `created_at` | Fila `default` creada por la migración; sin API hasta la Fase 9 |
| `users` | `id`, `tenant_id` → `tenants`, `username` (único global, minúsculas), `display_name`, `password_hash`, `role` (`admin`/`user`, CHECK), `is_active`, `failed_attempts`, `locked_until`, `password_changed_at`, `created_at`, `updated_at` | Nombre único global para que el login no pida tenant (revisable en ADR-013) |
| `sessions` | `id`, `token_hash` (SHA-256, único), `user_id` → `users` (CASCADE), `created_at`, `last_seen_at`, `expires_at`, `ip`, `user_agent` | El token en claro solo vive en la cookie |
| `audit_log` | `id`, `ts`, `tenant_id`, `actor_user_id` (SET NULL), `action`, `outcome`, `target_type`, `target_id`, `ip`, `details` (JSON, sin secretos) | Índices por `ts` y `action` |

Fechas con un `TypeDecorator` UTC portable (`DateTime(timezone=True)` en otros motores). `downgrade` borra las cuatro
tablas.

### Configuración (`DOW_*`)

`session_idle_minutes` (60), `session_absolute_hours` (12), `login_max_attempts` (5), `login_lockout_minutes` (15),
`password_min_length` (12). Cookie `__Host-dow_session` (`HttpOnly; Secure; SameSite=Lax; Path=/`); en `development`
`dow_session` sin `Secure` (sin TLS local).

### Contrato HTTP (`/api/v1`)

| Método | Ruta | Quién | Respuesta |
|---|---|---|---|
| GET | `/auth/csrf` | cualquiera | `{csrf_token}` (con sesión: `HMAC(dow_app_secret_key, token)`) |
| POST | `/auth/login` | anónimo | 200 `Me` + cookie; 401 genérico (no distingue usuario inexistente, contraseña mala, inactivo o bloqueado) |
| POST | `/auth/logout` | sesión | 204, borra la sesión y la cookie |
| GET | `/auth/me` | sesión | `Me` |
| POST | `/auth/password` | sesión | 204; revoca las demás sesiones del usuario |
| GET | `/users?limit&offset&q` | admin | `{items, total}` |
| POST | `/users` | admin | 201 `UserOut`; 409 si el nombre existe |
| GET | `/users/{id}` | admin | `UserOut`; 404 |
| PATCH | `/users/{id}` | admin | `UserOut`; campos `display_name`, `role`, `is_active`, `password` (restablecer), `unlock`; 409 si deja la instancia sin admin activo |
| GET | `/sessions?user_id&limit&offset` | admin (todas) / usuario (las suyas) | `{items, total}` con `current` |
| DELETE | `/sessions/{id}` | admin o dueño | 204; 404 si ajena |
| GET | `/audit?action&actor&from&to&limit&offset` | admin | `{items, total}` |

- CSRF de doble envío en todo método no seguro bajo `/api/v1` (dependencia del router), salvo `login`, que exige el
  token anónimo de `/auth/csrf`.
- Errores de dominio como `AppError` → *problem details*; 401 sin sesión, 403 sin rol, 404 recurso ajeno.
- No hay borrado de usuarios: desactivar revoca sus sesiones y conserva la auditoría (sustituye a `DELETE /api/users/{id}`
  de la web integrada; ver PARIDAD).

### Seguridad (ADR-003)

- `pwdlib[argon2]` (Argon2id), `verify_and_update` para rehash, verificación ficticia cuando el usuario no existe
  (tiempo constante); longitud 12–128, distinta del nombre de usuario y **fuera de una lista de contraseñas comunes**:
  10 000 más frecuentes de SecLists (licencia MIT, atribución en el fichero), comparación sin distinguir mayúsculas.
- Bloqueo temporal tras `login_max_attempts` fallos; se reinicia al acertar; el admin lo quita con `unlock`.
- Rotación de sesión en cada login; caducidad por inactividad (deslizante) y absoluta; `last_seen_at` se escribe como
  mucho una vez por minuto (SQLite: un escritor).
- Auditoría: `auth.login` (éxito/fallo, sin el nombre probado si no existe), `auth.logout`, `auth.password_change`,
  `user.create`, `user.update` (campos cambiados, nunca la contraseña), `session.revoke`.
- CLI: `python -m app.cli create-admin --username <u> [--display-name <n>] --password-stdin` (sin contraseña en
  argumentos ni en el historial del shell).

### doc_organize

Sin uso en esta fase (la identidad es propia de la web; `doc_organize.auth` no se importa). Firmas: no aplica.

### Frontend

- Dependencias: `react-hook-form`, `zod` (validación con un *resolver* propio de pocas líneas, sin
  `@hookform/resolvers`).
- `features/auth`: `LoginPage` (sustituye `login.html.j2`), `ChangePasswordPage` (`change_password.html.j2`),
  `useAuth` (`/auth/me`, login, logout), guardas `RequireAuth` / `RequireAdmin`, `UserMenu`.
- `features/admin`: `UsersPage` + `UserFormModal` (`admin_users.html.j2`), `SessionsPage`, `AuditPage`.
- `api/client.ts`: cabecera `X-CSRF-Token` automática en métodos no seguros; 401 → redirige a login.
- Rutas lazy por funcionalidad con `loadFeatureMessages()` (cierra el aviso de bundle > 500 kB de la Fase 0).
- Componentes compartidos: `ErrorAlert` (problem details), `NoPermission`.

### Documentación

Guía `docs/guides/usuarios_y_sesiones.md` (primer admin, alta, bloqueo, sesiones, auditoría); despliegue (crear el
admin); ADR-003 con notas de implementación; `PARIDAD.md` (filas de la Fase 1).

### Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| K1 | Bloqueo por intentos usable para bloquear a otro usuario (DoS dirigido) | Bloqueo temporal (15 min), admin puede quitarlo; rate limiting por IP en la Fase 10 |
| K2 | Enumeración de usuarios por tiempo o mensaje | 401 único y verificación ficticia |
| K3 | Escrituras de `last_seen_at` en cada petición con SQLite | Como mucho 1 por minuto y sesión |
| K4 | Cookies `Secure` en tests y E2E sobre HTTP | `TestClient` con `base_url="https://testserver"`; Chromium acepta `Secure` en `127.0.0.1` (verificado en UBW) |
| K5 | Lista de contraseñas de terceros en un repo público | SecLists es MIT; fichero con cabecera de atribución |
| K6 | Dejar la instancia sin admin | 409 al desactivar o degradar al último admin activo |
| K7 | `username` único global choca con multi-tenant (F9) | Decisión explícita en ADR-003 y revisión en ADR-013 |

### Estrategia de pruebas

- **unit**: hash/verify/rehash, política (longitud, nombre, comunes), tokens y HMAC CSRF, caducidades, bloqueo.
- **api**: login/logout/me/password (cookies y flags, rotación, 401 genérico, bloqueo y desbloqueo), CSRF (falta,
  inválido, válido), usuarios (CRUD admin, 401/403/404/409/422, último admin), sesiones (propias/ajenas → 404,
  revocación), auditoría (filtros, sin contraseñas en `details` ni en logs con `caplog`), CLI `create-admin`, migración
  up/down.
- **frontend**: login (ok, error, redirección), guardas, cambio de contraseña, admin de usuarios/sesiones/auditoría
  (carga, vacío, error, sin permiso).
- **E2E**: login, cambio de contraseña y cierre de sesión con un admin creado por CLI en el job `image`.

## AUDIT_PLAN

- **Arquitectura**: `domain/identity` sin FastAPI; routers finos; `tenant_id` desde el primer día (ADR-003); sin
  doc_organize.
- **Reglas no negociables**: secretos fuera de respuestas y logs (contraseñas solo de escritura); contrato regenerado;
  sin rutas del sistema de ficheros.
- **Paridad**: cubre `/login`, `/logout`, `/change-password`, `/admin/users` y `/api/users*`. El borrado de usuarios
  pasa a desactivación (decisión, se anota en PARIDAD). Roles personalizados y tenants siguen en la Fase 9.
- **Huecos de doc_organize**: ninguno nuevo.
- **Simplificaciones**: sin `@hookform/resolvers`; sin rate limiting por IP (F10).
- **Security Reviewer** en AUDIT_CODE (toca autenticación y secretos).

**Veredicto: `GO_CONDICIONAL`**

Condiciones:

1. Aprobar la lista de **contraseñas comunes** de SecLists (10 000, MIT) incluida en el repositorio.
2. Aprobar **`username` único global** (no por tenant) hasta la Fase 9.
3. Aprobar que **no se borran usuarios** (solo desactivar), a diferencia de la web integrada.

## Resolución de condiciones (mantenedor, 2026-10-31)

1. Lista de contraseñas comunes de SecLists (10 000, MIT) en el repositorio: aprobada.
2. `username` único global hasta la Fase 9: aprobado.
3. Sin borrado de usuarios, solo desactivar: aprobado.

Veredicto tras condiciones: **GO** — IMPLEMENT autorizado.
