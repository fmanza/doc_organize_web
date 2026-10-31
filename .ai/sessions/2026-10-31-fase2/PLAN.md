# PLAN + AUDIT_PLAN — Fase 2 (Ubicaciones locales/red y ajustes administrables → 0.3.0)

## PLAN

### Historias y DoD

- Como **admin** registro ubicaciones (origen/destino/ambas, local/red, `ro`/`rw`) eligiendo la carpeta bajo `/mnt`,
  las sondeo y veo su estado (`ok`/`degraded`/`unavailable`).
- Como **usuario** veo las ubicaciones y exploro sus carpetas (solo dentro de ellas).
- Como **admin** cambio ajustes sin reiniciar y veo la ficha de capacidades de la instancia (GPU, audio/vídeo,
  LibreOffice).

DoD común: comandos en verde, OpenAPI + cliente, migración `0003` con `downgrade`, tests 401/403/404 y de rutas
(escape, enlace simbólico, UNC/absoluta, ubicación caída → 503), imagen + `/api/health`, CHANGELOG, guías,
TRACEABILITY y `PARIDAD.md` (`/api/fs/browse`, macros del explorador y del semáforo).

### Modelo de datos — Alembic `0003_locations_settings`

| Tabla | Columnas | Notas |
|---|---|---|
| `locations` | `id`, `tenant_id`, `name` (único por tenant), `container_path` (único, **inmutable**), `display_path`, `kind` (`local`/`network`), `usage` (`source`/`destination`/`both`), `access` (`ro`/`rw`), `visibility` (`global`), `status` (`unknown`/`ok`/`degraded`/`unavailable`), `status_reasons` (JSON), `latency_ms`, `free_bytes`, `writable`, `probed_at`, `created_at`, `updated_at` | `container_path` se guarda resuelto y debe quedar bajo `DOW_LOCATIONS_ROOT` |
| `app_settings` | `key` (PK), `value` (JSON), `updated_by` (SET NULL), `updated_at` | Solo claves conocidas, nunca secretos (ADR-012) |

### Resolvedor de rutas (`domain/locations/paths.py`, núcleo de seguridad)

- Entrada: `location_id` + ruta **relativa** con `/`. Se rechazan (400) rutas absolutas, UNC (`\\`, `//`), letras de
  unidad, `\`, bytes nulos y componentes `..`; después `resolve(strict=True)` + `is_relative_to(raíz_resuelta)`, de
  modo que un enlace simbólico que sale de la ubicación se rechaza.
- Autorización antes que existencia: ubicación invisible → 404; ruta que escapa o no existe → el mismo 404
  «Carpeta no encontrada» (sin oráculo).
- Ubicación `unavailable` o error de E/S del montaje → **503** *problem details* (nunca 500, sin la ruta del contenedor
  en el mensaje).
- Devuelve un `ResolvedPath` (ubicación + ruta absoluta + relativa); ninguna función de dominio recibe un `str` de ruta
  del usuario.
- Registro de ubicaciones: `container_path` debe existir, ser directorio y quedar bajo `DOW_LOCATIONS_ROOT` tras
  resolver enlaces; no puede contener ni estar contenida en otra ubicación (evita solapes); nunca el propio
  `DOW_DATA_DIR`/`DOW_WORKSPACE_DIR`.

### Sondeo (`domain/locations/probe.py`)

Existe y es legible (`os.scandir` de la raíz), latencia de `stat` (ms), espacio libre (`shutil.disk_usage`) y, si la
ubicación es `rw`, escritura de un fichero temporal `.dow-probe-<uuid>` que se borra. Estado: `unavailable` si no existe
o no es legible; `degraded` si latencia > umbral, espacio libre < mínimo, o `rw` sin escritura; si no, `ok`. Se ejecuta
en un hilo con timeout (`location_probe_timeout_seconds`): un montaje colgado da `unavailable` sin bloquear la petición.
En F2 el sondeo es **bajo demanda** (al crear/editar y con el botón «Comprobar»); el periódico llega con el worker en
la Fase 3.

### Ajustes administrables (ADR-012, `domain/settings/`)

Precedencia BD > `DOW_*` > valor por defecto; se leen en cada uso (sin reiniciar). Claves de esta fase:

| Clave | Por defecto | Rango |
|---|---|---|
| `session_idle_minutes`, `session_absolute_hours`, `login_max_attempts`, `login_lockout_minutes`, `password_min_length` | los de la Fase 1 | los de `Settings` |
| `location_probe_timeout_seconds` | 10 | 1–120 |
| `location_latency_degraded_ms` | 500 | 10–60 000 |
| `location_min_free_gb` | 5 | 0–100 000 |

La identidad pasa a leer los ajustes efectivos (`effective_settings`). Auditoría `settings.update` con clave, valor
anterior y nuevo.

### Capacidades de la instancia (rodeo de G12)

Importar cualquier detector de doc_organize 0.9.3 carga **Docling y torch** (~4 300 módulos, 49 s en frío medido en
Windows): no se hace en la API. La capa anticorrupción expone `probe_capabilities()`, que lanza un **subproceso**
`python -m app.integrations.doc_organize.capabilities` (timeout 180 s) que llama a `detect_gpu_status`,
`detect_av_status` y `detect_office_status` y devuelve JSON. La API cachea el resultado en memoria (1 h) y lo
recalcula en segundo plano; mientras tanto responde `status: pending`. En la Fase 3 lo publicará cada worker (la GPU
que importa es la del worker). Hueco nuevo **G15**: el `__init__` del paquete importa el conversor (Docling) y
cualquier import de la librería cuesta lo mismo.

### Contrato HTTP (`/api/v1`)

| Método | Ruta | Quién | Respuesta |
|---|---|---|---|
| GET | `/locations` | sesión | `{items, total}`; usuario: sin `container_path` |
| POST | `/locations` | admin | 201; 400 ruta no válida/solape; 409 nombre o ruta repetidos |
| GET | `/locations/{id}` | sesión | `LocationOut` (admin) / `LocationPublic` |
| PATCH | `/locations/{id}` | admin | nombre, `display_path`, `kind`, `usage`, `access` (no la ruta) |
| DELETE | `/locations/{id}` | admin | 204 (en F3: 409 si un proyecto la usa) |
| POST | `/locations/{id}/probe` | admin | `LocationOut` con el estado nuevo |
| GET | `/fs/browse?location_id&path&limit&offset` | sesión | `{location_id, path, parent, items:[{name, path}], total}`; 404/503 |
| GET | `/admin/mounts?path` | admin | carpetas bajo `DOW_LOCATIONS_ROOT` para elegir `container_path` (mismo resolvedor, raíz = `/mnt`) |
| GET, PATCH | `/admin/settings` | admin | `{items:[{key, value, default, source}]}`; `null` vuelve al valor por defecto |
| GET | `/instance/capabilities` | sesión | `{status, checked_at, gpu, av, office, doc_organize_version}` |
| POST | `/admin/capabilities/refresh` | admin | 202 |

`/api/health` añade `locations: none|ok|degraded|unavailable` (agregado, sin nombres ni rutas); no cambia el `status`
de la app.

### Frontend

- Nav «Ubicaciones» habilitada. `features/locations`: lista con **semáforo de estado** (color + texto + icono, no solo
  color), detalle con explorador; admin: alta/edición con el **explorador de montajes**, «Comprobar» y borrado con
  confirmación que repite el nombre.
- `components/FolderBrowser` reutilizable (migas, subir, lista paginada de carpetas, estados de carga/vacío/error/503),
  sustituye a `_folder_browser_macros`; `components/StatusLight` sustituye a `_semaforo_macros`.
- `features/admin/SettingsPage`: ajustes con su origen (BD/entorno/defecto) y «Restablecer»; ficha de capacidades.

### Documentación

ADR-007 (ubicaciones) y ADR-012 (ajustes administrables) aceptados; guía de operación «Montar carpetas de red» (Linux:
`/etc/fstab` con CIFS/NFS, credenciales en fichero `0600` del host, *bind mount* bajo `/mnt` con `:ro` si procede;
servidores ficticios `//nas.example.internal/...`); guía de usuario «Ubicaciones»; despliegue; PARIDAD.

### Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| K1 | Escape de la raíz por `..`, enlaces simbólicos o rutas absolutas/UNC | Rechazo sintáctico + `resolve(strict)` + `is_relative_to`; tests (los de enlaces se saltan en Windows sin permiso de symlink; en el CI Linux corren) |
| K2 | Oráculo de existencia de carpetas | Mismo 404 para escape y no existe |
| K3 | Montaje de red colgado bloquea la API | Sondeo y listado con timeout en hilo; 503 |
| K4 | Directorios enormes (miles de subcarpetas) | `os.scandir` + paginación (`limit` ≤ 500) |
| K5 | Importar doc_organize en la API (memoria, 49 s) | Subproceso y caché (G15) |
| K6 | Solape entre ubicaciones o con `data`/`workspace` | Validación al registrar |
| K7 | Rutas del contenedor expuestas a usuarios | `container_path` solo en respuestas de admin; errores sin rutas |

### Estrategia de pruebas

- **unit**: resolvedor (vacía, `.`, `..`, absoluta, UNC, `C:\`, `\`, nulo, enlace que escapa, enlace interno),
  clasificación del sondeo, precedencia de ajustes, validación de solapes.
- **api**: CRUD de ubicaciones (401/403/404/409/422), visibilidad de `container_path`, browse (paginado, 404 sin
  oráculo, 503 con ubicación caída), mounts, settings (origen, `null`, rango → 422, efecto sin reiniciar en el
  bloqueo), capacidades (subproceso sustituido en tests), health.
- **frontend**: lista con semáforo, alta con explorador, explorador (subir, paginar, 503), ajustes, capacidades.
- **E2E**: el admin registra `/mnt/e2e` (carpeta creada en el contenedor del CI) y un usuario la explora.

## AUDIT_PLAN

- **Arquitectura**: `domain/locations` y `domain/settings` sin FastAPI; capacidades solo en la capa anticorrupción y en
  subproceso; reglas 5 (resolvedor) y 6 (sin secretos en `app_settings`) aplicadas.
- **ADRs**: ADR-007 y ADR-012 nuevos; ADR-005 sin cambios (SQLite fuera de ubicaciones: `data`/`workspace` vetados).
- **Huecos**: G12 confirmado (rodeo en subproceso); **G15** nuevo (`__init__` importa Docling).
- **Paridad**: `/api/fs/browse`, `_folder_browser_macros`, `_semaforo_macros`, `_status_banner_macros`.
- **Security Reviewer** en AUDIT_CODE (rutas del sistema de ficheros).

**Veredicto: `GO_CONDICIONAL`**

Condiciones:

1. Ficha de capacidades en **subproceso** desde la API con caché (y en F3, la publica el worker).
2. Claves administrables de esta fase: **identidad + umbrales del sondeo** (cuota y retención llegan con las
   ejecuciones en F3).
3. `container_path` **inmutable** tras crear la ubicación (cambiarla = nueva ubicación).
4. Sondeo **bajo demanda** en F2; periódico con el worker en F3.

## Resolución de condiciones (mantenedor, 2026-10-31)

1. Capacidades en subproceso con caché desde la API: aprobado.
2. Ajustes administrables: identidad + umbrales del sondeo: aprobado.
3. `container_path` inmutable: aprobado.
4. Sondeo bajo demanda en F2: aprobado.

Veredicto tras condiciones: **GO** — IMPLEMENT autorizado.
