# Despliegue

El despliegue de producción es un servidor Linux con Docker Compose (D9). Docker Desktop solo se usa para desarrollo
([entorno de desarrollo](desarrollo.md)).

## Primer arranque

```bash
git clone https://github.com/fmanza/doc_organize_web.git
cd doc_organize_web
python3 scripts/generate_secrets.py      # crea secrets/app_secret_key.txt y secrets/fernet_keys.txt (0600 recomendado)
docker compose up -d --build
curl http://127.0.0.1:8080/api/health
# primer administrador (no hay credenciales por defecto); la contraseña se pide por el terminal:
docker compose exec web python -m app.cli create-admin --username <usuario>
```

Después, entra en `http://127.0.0.1:8080` con ese usuario. Gestión de usuarios y sesiones:
[usuarios y sesiones](usuarios_y_sesiones.md).

`/api/health` responde `200` con `status: ok` cuando `config.db` responde y doc_organize está instalado; si no, `503`
con `status: degraded`. El `HEALTHCHECK` de la imagen usa el mismo endpoint.

## Qué levanta

| Servicio | Proceso | Cuándo |
|---|---|---|
| `web` | API + SPA en el puerto 8080, publicado solo en `127.0.0.1` | siempre |
| `worker` | `python -m app.jobs.worker`: ejecuta las operaciones en cola, un subproceso por operación | siempre (desde la Fase 3); arranca cuando `web` está sano |

Ambos usan la misma imagen, con usuario no root (uid 10001), sistema de ficheros de solo lectura, `tmpfs` en `/tmp`,
sin capacidades y `no-new-privileges`.

Sin `worker` la aplicación funciona, pero las ejecuciones se quedan **en cola**. `/api/health` indica su estado en
`worker` (`ok`, `stale` si dejó de latir, `none` si no hay ninguno) sin cambiar el `status` general, y
**Administración → Ajustes** lista los workers con su último latido. El worker publica también la ficha de
capacidades (GPU, audio/vídeo, LibreOffice) y sondea las ubicaciones cada `location_probe_interval_minutes`.

Las ubicaciones se montan **igual en `web` y en `worker`** (mismas rutas bajo `/mnt`): la API valida y explora y el
worker lee y escribe. Al detener el worker (`docker compose stop worker`) las operaciones en marcha se interrumpen y
quedan como fallidas («El worker se detuvo»); se pueden volver a lanzar.

## Secretos

Docker secrets montados en `/run/secrets/`:

| Secreto | Fichero | Uso |
|---|---|---|
| `dow_app_secret_key` | `secrets/app_secret_key.txt` | Firma del token CSRF de cada sesión |
| `dow_fernet_keys` | `secrets/fernet_keys.txt` | Cifrado de credenciales IA (Fase 8); lista separada por comas para rotar |

Sin ambos, la aplicación no arranca en producción. `secrets/` nunca se versiona. Guarda una copia segura: sin
`dow_fernet_keys` no se pueden descifrar las credenciales guardadas.

## Volúmenes

| Volumen | Ruta | Contenido |
|---|---|---|
| `data` | `/data` | `config.db` y `projects/<id>/` (caché e historial de doc_organize de cada proyecto). Siempre en disco local, nunca NFS/CIFS |
| `workspace` | `/workspace` | Una carpeta por ejecución (`runs/<id>/`: `run.json`, `logs/run.log`, ficheros resultado); se purga según `run_retention_days` |

Las ubicaciones de documentos (carpetas locales o montajes SMB/NFS del host) se pasan al contenedor bajo `/mnt` y se
registran en la aplicación: [Montar carpetas de red](carpetas_de_red.md) y [Ubicaciones](ubicaciones.md).

## Variables

Se ajustan en un `.env` junto a `docker-compose.yml` (plantilla en `.env.example`):

| Variable | Por defecto | Uso |
|---|---|---|
| `DOW_TAG` | `dev` | Etiqueta de la imagen |
| `DOW_PORT` | `8080` | Puerto publicado en `127.0.0.1` |
| `DOW_LOG_LEVEL` | `INFO` | Nivel de log (JSON por stdout) |
| `DOW_WORKER_MEM_LIMIT` | `6g` | Límite de memoria del worker (Docling consume mucha por documento) |

Variables de la aplicación (en `environment:` del servicio `web` en `docker-compose.yml`). Los administradores pueden
cambiarlas también desde **Administración → Ajustes** sin reiniciar; lo guardado allí tiene prioridad
([ADR-012](../adr/ADR-012-ajustes-administrables.md)):

| Variable | Por defecto | Uso |
|---|---|---|
| `DOW_SESSION_IDLE_MINUTES` | `60` | Cierre de sesión por inactividad |
| `DOW_SESSION_ABSOLUTE_HOURS` | `12` | Duración máxima de una sesión |
| `DOW_LOGIN_MAX_ATTEMPTS` | `5` | Fallos seguidos que bloquean la cuenta |
| `DOW_LOGIN_LOCKOUT_MINUTES` | `15` | Duración del bloqueo |
| `DOW_PASSWORD_MIN_LENGTH` | `12` | Longitud mínima de contraseña |
| `DOW_LOCATION_PROBE_TIMEOUT_SECONDS` | `10` | Tiempo máximo de una comprobación o listado de ubicación |
| `DOW_LOCATION_LATENCY_DEGRADED_MS` | `500` | Latencia a partir de la que una ubicación está degradada |
| `DOW_LOCATION_MIN_FREE_GB` | `5` | Espacio libre mínimo de una ubicación (0 = no se comprueba) |
| `DOW_LOCATION_PROBE_INTERVAL_MINUTES` | `5` | Cada cuánto sondea el worker las ubicaciones (0 = nunca) |
| `DOW_RUN_RETENTION_DAYS` | `30` | Días que se guardan los ficheros de las ejecuciones terminadas (el historial se conserva) |
| `DOW_USER_QUOTA_MB` | `0` | Espacio de ficheros de ejecuciones por usuario (0 = sin límite) |

Variables del worker (en `environment:` del servicio `worker`; no son administrables):

| Variable | Por defecto | Uso |
|---|---|---|
| `DOW_WORKER_QUEUES` | `cpu` | Colas que atiende (`cpu`, `gpu`; la de GPU llega con el escaneo, Fase 4) |
| `DOW_WORKER_CONCURRENCY` | `1` | Operaciones simultáneas (Docling consume mucha memoria) |
| `DOW_WORKER_HEARTBEAT_SECONDS` | `10` | Latido; un run sin latido durante 3 intervalos se da por huérfano |
| `DOW_JOB_TIMEOUT_SECONDS` | `21600` | Duración máxima de una operación (6 h) |
| `DOW_CANCEL_GRACE_SECONDS` | `30` | Plazo para atender una cancelación antes de terminar el subproceso |

## Detrás de un proxy TLS

Publica el puerto solo en `127.0.0.1` (por defecto) y pon delante un proxy inverso con TLS (nginx, Caddy, Traefik)
que reenvíe a `http://127.0.0.1:8080`. uvicorn arranca con `--proxy-headers`; ajusta `FORWARDED_ALLOW_IPS` si el
proxy no está en la misma máquina. El progreso en vivo (SSE, Fase 3) necesita el *buffering* desactivado en el proxy
para `/api/v1/runs/*/events`.

## Actualizar

```bash
git pull
docker compose up -d --build     # entrypoint.sh aplica las migraciones de config.db antes de arrancar
```

Para volver atrás: imagen anterior y, si la versión nueva añadió migraciones, `alembic downgrade <revisión>` dentro del
contenedor antes de cambiar de imagen.
