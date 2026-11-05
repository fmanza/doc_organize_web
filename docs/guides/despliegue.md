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
# modelos de Docling para PDF e imágenes (necesita red una vez; el worker trabaja sin Internet, ADR-011):
docker compose --profile setup run --rm models-init
```

Después, entra en `http://127.0.0.1:8080` con ese usuario. Gestión de usuarios y sesiones:
[usuarios y sesiones](usuarios_y_sesiones.md).

`/api/health` responde `200` con `status: ok` cuando `config.db` responde y doc_organize está instalado; si no, `503`
con `status: degraded`. El `HEALTHCHECK` de la imagen usa el mismo endpoint.

## Qué levanta

| Servicio | Proceso | Cuándo |
|---|---|---|
| `web` | API + SPA en el puerto 8080, publicado solo en `127.0.0.1` | siempre |
| `worker` | `python -m app.jobs.worker`: ejecuta las operaciones en cola (`cpu`), un subproceso por operación | siempre (desde la Fase 3); arranca cuando `web` está sano |
| `worker-gpu` | El mismo worker con la imagen `runtime-gpu`, cola `gpu` (escaneos con «Usar GPU») | perfil `gpu` |
| `models-init` | Descarga los modelos de Docling al volumen `models` y termina | perfil `setup`, a mano |

Ambos usan la misma imagen, con usuario no root (uid 10001), sistema de ficheros de solo lectura, `tmpfs` en `/tmp`,
sin capacidades y `no-new-privileges`.

Sin `worker` la aplicación funciona, pero las ejecuciones se quedan **en cola**. `/api/health` indica su estado en
`worker` (`ok`, `stale` si dejó de latir, `none` si no hay ninguno) sin cambiar el `status` general, y
**Administración → Ajustes** lista los workers con su último latido. El worker publica también la ficha de
capacidades (GPU, audio/vídeo, LibreOffice, modelos) y sondea las ubicaciones cada
`location_probe_interval_minutes`.

### Modelos de Docling

Los PDF y las imágenes necesitan modelos (maquetación, tablas, OCR). El worker corre con `HF_HUB_OFFLINE=1` y los lee
del volumen `models` (solo lectura); los descarga `models-init`, que sí tiene red
([ADR-011](../adr/ADR-011-modelos-sin-internet.md)):

```bash
docker compose --profile setup run --rm models-init                                   # base (~1 GB)
docker compose --profile setup run --rm models-init download --picture-description    # + visión
docker compose restart worker                                                         # vuelve a publicar las capacidades
```

Cada descarga conserva en el manifiesto los modelos opcionales que ya estaban (visión, EasyOCR). Repítelo al actualizar la aplicación si cambia la versión de Docling (CHANGELOG). Sin modelos, el resto de formatos se
convierte y los PDF e imágenes quedan como errores del escaneo.

### Worker con GPU

Para escanear con «Usar GPU» hace falta un worker de la cola `gpu` en una máquina con GPU NVIDIA, **driver ≥ 580**
(CUDA 13.0) y [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/):

```bash
docker compose --profile setup-gpu run --rm models-init-gpu   # base + EasyOCR; construye runtime-gpu (varios GB)
docker compose --profile gpu up -d --build                     # worker-gpu
```

`models-init-gpu` usa la imagen `runtime-gpu` porque EasyOCR solo está en ella; no necesita GPU. Para añadir también
la visión: `docker compose --profile setup-gpu run --rm models-init-gpu download --easyocr --picture-description`.

La imagen `runtime-gpu` lleva torch con CUDA y EasyOCR; el CI no la construye por tamaño. Probada con una RTX 5070
(Blackwell, `sm_120`) y driver 616.92: el OCR con EasyOCR en GPU tarda la mitad que RapidOCR en CPU. EasyOCR y la caché
de kernels de torch escriben en el tmpfs `/tmp` (`EASYOCR_MODULE_PATH`, `PYTORCH_KERNEL_CACHE_PATH`), porque el
contenedor es de solo lectura. Con una sola GPU, deja
`DOW_WORKER_CONCURRENCY=1` en `worker-gpu` (valor por defecto) para no agotar su memoria.

Para probar la variante en un equipo con GPU, encima de la pila E2E (carpetas sintéticas de `dev-data/e2e`):

```bash
export COMPOSE_FILE="docker-compose.yml:docker-compose.e2e.yml:docker-compose.gpu.yml"   # «;» en Windows
docker compose --profile setup-gpu run --rm models-init-gpu
docker compose --profile gpu up -d --build
docker compose exec -T worker-gpu python - --gpu < scripts/smoke_variants.py
```

`scripts/smoke_variants.py` enseña la ficha de capacidades del contenedor y convierte un HTML y un PDF escaneado
sintéticos con OCR, primero en CPU y, con `--gpu`, con EasyOCR en la GPU; sale con error si algo no cuadra.

### LibreOffice y audio/vídeo

Las imágenes no los llevan por defecto (pesan). Se añaden al construir, en las dos variantes:

```bash
DOW_WITH_LIBREOFFICE=true DOW_WITH_AV=true docker compose build
docker compose exec -T worker python - --libreoffice --av < scripts/smoke_variants.py
```

- `DOW_WITH_LIBREOFFICE=true`: `soffice` (paquete `libreoffice-calc-nogui`) para las hojas `.xls` antiguas.
- `DOW_WITH_AV=true`: `ffmpeg` y Whisper (grupo `av` de `backend/pyproject.toml`) para «Incluir audio y vídeo». El
  modelo de Whisper se descarga la primera vez que se usa: el worker necesita salida a Internet para eso, o el modelo
  en la caché de `HF_HOME` del volumen `models`.

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
| `data` | `/data` | `config.db`, `projects/<id>/` (caché e historial de doc_organize por carpeta de origen y `search.db`, el índice de la búsqueda de texto completo) y `backups/`. Siempre en disco local, nunca NFS/CIFS |
| `workspace` | `/workspace` | Una carpeta por ejecución (`runs/<id>/`: `run.json`, `logs/run.log`, ficheros resultado); se purga según `run_retention_days` |
| `models` | `/models` | Modelos de Docling (ADR-011); solo lectura en `web` y en los workers, escritura en `models-init` (que no recibe secretos ni `config.db`) |

Las ubicaciones de documentos (carpetas locales o montajes SMB/NFS del host) se pasan al contenedor bajo `/mnt` y se
registran en la aplicación: [Montar carpetas de red](carpetas_de_red.md) y [Ubicaciones](ubicaciones.md).

## Variables

Se ajustan en un `.env` junto a `docker-compose.yml` (plantilla en `.env.example`):

| Variable | Por defecto | Uso |
|---|---|---|
| `DOW_TAG` | `dev` | Etiqueta de la imagen |
| `DOW_PORT` | `8080` | Puerto publicado en `127.0.0.1` |
| `DOW_LOG_LEVEL` | `INFO` | Nivel de log (JSON por stdout) |
| `DOW_WORKER_MEM_LIMIT` | `6g` | Límite de memoria del worker (Docling consume mucha por documento). Si un escaneo largo termina con «El worker se quedó sin memoria», súbelo (p. ej. `8g`) |
| `DOW_WORKER_GPU_MEM_LIMIT` | `8g` | Límite de memoria de `worker-gpu` |
| `DOW_SCAN_RECYCLE_DOCUMENTS` | `200` | Documentos convertidos tras los que un escaneo sigue en un proceso nuevo (tramos, [Ejecuciones](ejecuciones.md#escaneos-largos-tramos)); 0 = nunca. Bájalo si aún se queda sin memoria |
| `DOW_WITH_LIBREOFFICE`, `DOW_WITH_AV` | `false` | Al construir: imagen con LibreOffice o con audio y vídeo |

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
| `DOW_CONTEXT_SITE_TIMEOUT_SECONDS` | `600` | Tiempo máximo de `zensical build` al construir el contexto; si se pasa, el contexto queda sin sitio y con un aviso |

Límites de la API (no administrables, Fase 10):

| Variable | Por defecto | Uso |
|---|---|---|
| `DOW_RATE_LIMIT_LOGIN` | `10` | Inicios de sesión por minuto e IP; al pasarse, 429 con `Retry-After`. Se suma al bloqueo por cuenta |
| `DOW_RATE_LIMIT_WRITE` | `120` | Escrituras (`POST`, `PUT`, `PATCH`, `DELETE`) a `/api/v1` por minuto e IP |
| `DOW_MAX_REQUEST_MB` | `16` | Tamaño máximo del cuerpo de una petición (413) |

Los límites se cuentan en la memoria de la API: valen mientras sea un único proceso (como en la imagen). Detrás de un
proxy, la IP es la que uvicorn toma de `X-Forwarded-For` solo si el proxy está en `FORWARDED_ALLOW_IPS`; si no, todas
las peticiones parecen venir del proxy y comparten el límite.

El sitio de contexto se sirve en `/site/<token>/…` y el token es una credencial temporal
([ADR-010](../adr/ADR-010-sitio-de-contexto-aislado.md)): la aplicación no la escribe en sus registros, y el proxy
inverso de delante tampoco debería (enmascara la ruta `/site/` en su registro de accesos).

Variables del worker (en `environment:` del servicio `worker`; no son administrables):

| Variable | Por defecto | Uso |
|---|---|---|
| `DOW_WORKER_QUEUES` | `cpu` | Colas que atiende (`cpu`, `gpu`; `worker-gpu` atiende `gpu`) |
| `DOW_WORKER_CONCURRENCY` | `1` | Operaciones simultáneas (Docling consume mucha memoria) |
| `DOW_WORKER_HEARTBEAT_SECONDS` | `10` | Latido; un run sin latido durante 3 intervalos se da por huérfano |
| `DOW_JOB_TIMEOUT_SECONDS` | `21600` | Duración máxima de una operación (6 h); al vencer se pide una parada ordenada y lo hecho se guarda |
| `DOW_CANCEL_GRACE_SECONDS` | `30` | Plazo para atender una cancelación antes de terminar el subproceso |
| `DOW_TIMEOUT_GRACE_SECONDS` | `600` | Plazo de la parada ordenada al vencer el tiempo máximo (un PDF grande con OCR tarda minutos; si no para, se pierde la caché de la carpeta en curso) |

## Copias de seguridad

`app.cli backup` copia `config.db` (usuarios, proyectos, ejecuciones, auditoría) y la caché de doc_organize de cada
carpeta de origen con la API de backup de SQLite, sin parar la aplicación, y comprueba la copia:

```bash
docker compose exec web python -m app.cli backup --keep 7          # en /data/backups/<fecha UTC>/
docker compose exec web python -m app.cli verify-backup /data/backups/20261102T030000Z
```

Cada copia lleva un `manifest.json` con el tamaño y el SHA-256 de cada base de datos; `--keep N` borra las más
antiguas y deja `N`. El índice de búsqueda (`search.db`) no se copia: se regenera con «Actualizar la búsqueda». Las
copias quedan en el mismo volumen `data`: llévalas fuera del servidor (p. ej. un `cron` del host que copie
`/var/lib/docker/volumes/<proyecto>_data/_data/backups`) y trátalas como datos sensibles, porque `config.db` contiene
los *hashes* de las contraseñas y las sesiones.

### Restaurar

```bash
docker compose stop web worker                                                      # nada en marcha
docker compose run --rm --no-deps web python -m app.cli restore /data/backups/20261102T030000Z    # vista previa
docker compose run --rm --no-deps web python -m app.cli restore /data/backups/20261102T030000Z --yes
docker compose up -d                                                                # aplica las migraciones
```

Sin `--yes` solo enseña qué bases de datos sustituiría. Con `--yes` comprueba la copia (como `verify-backup`), se
niega si hay ejecuciones en marcha o un worker vivo, guarda cada base de datos actual como
`<fichero>.pre-restore-<fecha UTC>` y vuelca encima la de la copia con la API de backup de SQLite. Solo escribe
`config.db` y las `projects/<id>/…/cache.db` del manifiesto; las cachés de proyectos que no estén en la copia no se
tocan. Al arrancar, la aplicación aplica las migraciones si la copia es de una versión anterior. Una copia que esté
fuera del volumen se monta antes en el contenedor (p. ej. `-v /ruta/copias:/restore:ro` y `restore /restore/<fecha>`).
Si algo sale mal, los `.pre-restore-*` son la base de datos de antes: se restauran copiándolos sobre la original con
la aplicación parada. Las salidas de los proyectos (Markdown, JSON) están en la ubicación de destino, no en la copia.

## Métricas

`GET /metrics` da métricas en formato Prometheus: peticiones y duración por ruta (la plantilla, sin ids), ejecuciones
por estado, cola y operación, fallidas por motivo (`out_of_memory`…), workers vivos y tamaño de `config.db`. Solo
existe con el secreto `dow_metrics_token` (sin él, 404):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))" > secrets/metrics_token.txt
```

Añádelo a `secrets:` de `web` en un `docker-compose.override.yml` (`dow_metrics_token: file: ./secrets/metrics_token.txt`)
y configura Prometheus con `authorization: { credentials_file: … }`. Como el resto de la API, mejor que no salga del
servidor: el proxy puede no publicar `/metrics`.

## Detrás de un proxy TLS

Publica el puerto solo en `127.0.0.1` (por defecto) y pon delante un proxy inverso con TLS (nginx, Caddy, Traefik)
que reenvíe a `http://127.0.0.1:8080`. uvicorn arranca con `--proxy-headers`; ajusta `FORWARDED_ALLOW_IPS` si el
proxy no está en la misma máquina. Fuera de `development` la aplicación responde con `Strict-Transport-Security` (un
año): sírvela siempre por HTTPS. El progreso en vivo (SSE, Fase 3) necesita el *buffering* desactivado en el proxy
para `/api/v1/runs/*/events`.

## Actualizar

```bash
git pull
docker compose up -d --build     # entrypoint.sh aplica las migraciones de config.db antes de arrancar
```

Para volver atrás: imagen anterior y, si la versión nueva añadió migraciones, `alembic downgrade <revisión>` dentro del
contenedor antes de cambiar de imagen.
