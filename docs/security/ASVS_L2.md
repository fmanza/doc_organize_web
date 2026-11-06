# OWASP ASVS nivel 2 — estado en la 1.0

Revisión de la Fase 10 (2026-11-05) contra [OWASP ASVS 4.0.3](https://owasp.org/www-project-application-security-verification-standard/),
nivel 2, para la aplicación tal como se despliega: un `docker compose` con la API, el worker y un proxy inverso con TLS
delante ([despliegue](../guides/despliegue.md)).

Leyenda:

- ✅ cumple, con la evidencia indicada;
- 🔶 riesgo aceptado, con su motivo;
- — no aplica.

Las evidencias son módulos y tests del repositorio.

## Hallazgos de la revisión y su remedio

| # | Severidad | Hallazgo | Remedio (Fase 10) |
|---|---|---|---|
| 1 | MEDIUM | Sin límite por IP: el bloqueo por cuenta no frena a quien prueba muchas cuentas desde una IP | `core/ratelimit.py`: 10 inicios de sesión y 120 escrituras por minuto e IP, 429 con `Retry-After` (`tests/api/test_hardening.py`) |
| 2 | MEDIUM | Respuestas JSON de la API sin `Cache-Control` (usuarios, auditoría y rutas en cachés del navegador o de un proxy) | `no-store` por defecto en `/api` (`core/middleware.py`) |
| 3 | MEDIUM | Sin límite de tamaño del cuerpo: un usuario autenticado podía agotar la memoria con un JSON enorme | `BodyLimitMiddleware`: 413 por encima de `DOW_MAX_REQUEST_MB` (16) y 411 sin `Content-Length` |
| 4 | LOW | Sin HSTS | `Strict-Transport-Security` de un año fuera de `development` |
| 5 | LOW | Sin métricas para detectar abusos y fallos (V7.1) | `/metrics` con token (`api/metrics.py`) |

No quedan hallazgos CRITICAL ni HIGH. Las revisiones de seguridad de cada fase ya resolvieron los anteriores; por
ejemplo, la fuga de la clave de LiteLLM en los registros (Fase 8) y la escalada de un admin de tenant (Fase 9).

## Por capítulo

| Capítulo | Estado | Evidencia o motivo |
|---|---|---|
| V1 Arquitectura | ✅ | Capas y reglas en `.ai/architecture.md` y en los ADR. La capa anticorrupción tiene un test de arquitectura. Contenedores `read_only`, `cap_drop: ALL` y `no-new-privileges`, con usuario sin privilegios (uid 10001) |
| V2.1 Contraseñas | ✅ / 🔶 | Mínimo 12 caracteres (`DOW_PASSWORD_MIN_LENGTH`) y máximo 128, sin reglas de composición. 🔶 **No se comprueban contra listas de contraseñas filtradas** (V2.1.7): la instancia trabaja sin Internet (ADR-011) y no se incluye un diccionario. Mitigan el bloqueo y el límite por IP |
| V2.2 Autenticación general | ✅ / 🔶 | Bloqueo tras 5 fallos (15 min), límite por IP, mensajes genéricos y auditoría `auth.login`/`auth.lockout`. 🔶 **Sin segundo factor** en la 1.0. Uso previsto: red interna detrás de un proxy, que puede añadir SSO o MFA. Queda en mejoras |
| V2.4 Almacenamiento de credenciales | ✅ | Argon2id con `pwdlib` y re-hash al iniciar sesión si cambian los parámetros (`domain/identity/auth.py`) |
| V2.5 Recuperación | ✅ | Sin autoservicio: solo un administrador restablece contraseñas. No puede hacerlo con cuentas con más permisos que él (`check_can_manage`, Fase 9) |
| V2.10 Secretos de servicio | ✅ | Docker secrets (`dow_app_secret_key`, `dow_fernet_keys`, `dow_metrics_token`). Nada en el repositorio ni en la imagen |
| V3 Sesiones | ✅ | Token aleatorio en una cookie `__Host-`, `Secure`, `HttpOnly` y `SameSite=Lax`. Se crea una sesión nueva al iniciar sesión y se borra la anterior. Caducidad por inactividad (60 min) y absoluta (12 h). Cerrar sesión la borra en el servidor. El usuario ve y cierra sus sesiones |
| V4 Control de acceso | ✅ | Permisos por rol de tenant y roles de miembro por proyecto, comprobados en el dominio. IDOR entre tenants y proyectos: 404, nunca 403 (tests de autorización de cada fase). Autorización antes que existencia en rutas (regla 5) |
| V5 Validación y codificación | ✅ | Pydantic en todo lo que cruza HTTP. Rutas solo por el resolvedor de ubicaciones, sin seguir enlaces. Markdown saneado con DOMPurify. Las celdas de los Excel no empiezan por `=` |
| V6 Criptografía | ✅ | MultiFernet para las credenciales de IA (ADR-004), con rotación (`app.cli rotate-secrets`). Tokens con `secrets`. CSRF firmado con HMAC |
| V7 Registro | ✅ | JSON con `request_id`. Sin secretos, rutas del contenedor ni el token del sitio (`/site/***/`). `httpx` en WARNING para no registrar URL con claves. Auditoría de las acciones sensibles y `/metrics`. Borrar auditoría por fechas (1.2.0): solo el admin de instancia, nunca las entradas de hoy, con vista previa y el número tecleado, y queda registrado (`audit.purge`) |
| V8 Protección de datos | ✅ | `no-store` en la API. Datos en el volumen local y nunca SQLite en red. Copias con permisos `0700` y la guía de tratarlas como sensibles. `run.log` descargable sin rutas ni trazas |
| V9 Comunicaciones | ✅ | TLS en el proxy (guía), HSTS y puerto publicado solo en `127.0.0.1`. La IA solo va a la URL configurada por el admin de instancia (ADR-014) |
| V10 Código malicioso | ✅ | Dependencias fijadas con hash (`uv.lock`, `package-lock.json`), con la regla de 14 días reactivada. Imágenes base con versión exacta. Dependabot con *cooldown* |
| V11 Lógica de negocio | ✅ | Una escritura por proyecto a la vez, tope de runs activos por usuario y presupuesto de IA por run. Las operaciones que mueven o borran tienen vista previa y confirmación (regla 7) |
| V12 Ficheros | ✅ | Sin subida de ficheros (la subida es una mejora futura con antivirus). Descargas con `Content-Disposition`, `nosniff` y tamaño máximo. ZIP en *streaming*. El sitio de contexto, aislado con CSP `sandbox` (ADR-010) |
| V13 API | ✅ | CSRF de doble envío en todo método no seguro de `/api/v1`. Errores RFC 9457 sin detalles internos. Paginación acotada. Cuerpo acotado (413/411). OpenAPI y `/docs` desactivados en producción |
| V14 Configuración | ✅ | CSP sin `unsafe-inline` en scripts. `frame-ancestors 'none'`, COOP/CORP, `Referrer-Policy` y `Permissions-Policy`. Sin cabecera `Server`. Producción exige los secretos (falla al arrancar sin ellos) |

## Fuera de alcance de la aplicación

- **TLS, WAF y el registro de accesos del proxy**: son del despliegue. La guía pide enmascarar `/site/`.
- **Seguridad de las carpetas de red** (permisos SMB/NFS): las monta el host. La aplicación solo ve lo que se monta en
  `/mnt` y respeta `ro`/`rw` de cada ubicación.
