# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/). Hasta la 1.0.0, una MINOR por fase del
ROADMAP (`0.<fase+1>.0`).

## [Unreleased]

## [1.4.2] - 2026-11-07

### Fixed

- **backend**: cuando el worker GPU se queda sin memoria, el error de la ejecución nombra su límite,
  `DOW_WORKER_GPU_MEM_LIMIT`, en lugar de `DOW_WORKER_MEM_LIMIT` (el del worker de CPU), que no le afecta. El worker
  elige la variable según su cola (`gpu` → la del worker GPU).

## [1.4.1] - 2026-11-07

Patrones de nombre también al registrar y al editar una ubicación.

### Added

- **backend**, **frontend**: el formulario de «Nueva ubicación» y el de «Editar ubicación» tienen el campo «Patrones
  (uno por línea)», con los ejemplos y el aviso de que afectan a todos los proyectos de la ubicación. Solo aparece
  si el uso es «Origen» u «Origen y destino»; en una de destino ni se muestra ni se envía (los guardados se
  conservan). La tarjeta de la ficha de la ubicación sigue igual.
  - `POST /api/v1/locations` acepta `ignore_patterns` opcional con las mismas reglas que el `PATCH` (400
    `invalid_ignore_patterns` si no se cumplen, también en una ubicación de destino) y la auditoría del alta los
    registra.

## [1.4.0] - 2026-11-07

Exclusiones en el escaneo con doc_organize 1.3.0 (G41): subcarpetas por proyecto y patrones de nombre por ubicación.

### Added

- **backend**, **frontend**: «Excluir subcarpetas» en cada carpeta guardada de «Escanear» (owner del proyecto): el
  explorador se abre limitado a esa carpeta, con casillas; lo excluido sale tachado con la etiqueta «Excluida» y se
  puede quitar, con el aviso de que lo borrado por un «forzar» se volverá a convertir.
  - `PUT /api/v1/projects/{id}/scanned-folders/exclusions?subpath=…` con `{"excluded": [...]}` (rutas relativas a la
    ubicación de origen). 400 si una es la propia carpeta, sale de ella, es un enlace o no se puede resolver, o hay
    más de 50; las redundantes se colapsan y las que ya no existen se conservan (`exists: false`).
  - `GET …/scanned-folders` devuelve `excluded: [{subpath, exists}]` en cada carpeta. Auditoría
    `project.scan_folder_exclusions` con la lista anterior y la nueva.
- **backend**, **frontend**: patrones de nombre que no se escanean en una ubicación de origen (`~$*`, `@eaDir`,
  `#recycle`, `$RECYCLE.BIN`, `System Volume Information`…), editables por un administrador en su ficha con el aviso
  de que afectan a todos los proyectos de la ubicación.
  - `PATCH /api/v1/locations/{id}` con `ignore_patterns`: hasta 30, de hasta 64 caracteres, sin vacíos ni `/` ni `\`
    (400 si no); solo en ubicaciones de origen. `GET` los devuelve (`[]` por defecto) y el cambio queda en la auditoría
    de la ubicación con la lista anterior y la nueva.
- **backend**: el run de escaneo copia al encolarse las exclusiones de cada carpeta y los patrones de la ubicación
  (`ScanParams.exclusions` e `ignore_patterns`; lo que mande el cliente se descarta) y todos sus tramos usan esa copia:
  se pueden cambiar con un escaneo en marcha. El job registra «N subcarpetas excluidas» por carpeta.
- **backend**, **frontend**: la vista previa de «Forzar reconversión» cuenta `excluded` (documentos de la caché bajo
  una exclusión o que encajan con un patrón, que se borrarán) y la confirmación lo avisa antes de escribir el nombre.
  Cambiar las exclusiones o los patrones invalida una vista previa anterior.

### Changed

- **backend**: doc_organize 1.3.0, wheel de su release en GitHub con su hash en `uv.lock`
  (`sha256:4653d93195f7ca9036f8192881221fa085c784280760c203c12fc09216b3984f`). Sin exclusiones ni patrones, el
  escaneo y su resultado son los de la 1.3.0.
- **backend**: migración `0011` (aditiva y reversible): `scanned_folders.excluded_subpaths` y
  `locations.ignore_patterns`, JSON con `[]` por defecto.

### Docs

- **docs**: G41 pasa a resueltos (L-19 ✅) y las mejoras P2 y P3 de exclusiones quedan hechas. No quedan huecos
  abiertos en doc_organize.

## [1.3.0] - 2026-11-07

Documentos ordenables por columna con doc_organize 1.2.0 (G40).

### Added

- **backend**, **frontend**: Documentos se ordena por ruta, última actualización, estado de conversión o fallos
  seguidos («Ordenar por» y el botón de sentido), con `sort` y `order` en `GET /api/v1/projects/{id}/documents`.
  - Con una carpeta, o filtrando por una, ordena doc_organize directamente.
  - Con varias, la web pide a cada caché su página ordenada y las mezcla con el mismo criterio que la librería
    (empates por ruta, vacíos al final): el orden es el mismo que si todo estuviera en una caché.

### Changed

- **backend**: doc_organize 1.2.0, wheel de su release en GitHub con su hash en `uv.lock`
  (`sha256:b59419526becc69bd3fdada6cd2898b0b82f52808cead7800ce4dc0fb89618d5`).

### Docs

- **docs**: G40 pasa a resueltos (L-18 ✅). No quedan huecos abiertos en doc_organize.

## [1.2.0] - 2026-11-06

Listados homogéneos, roles como usuarios y borrado de la auditoría por fechas.

### Added

- **backend**, **frontend**: todos los listados se pueden **ordenar por columna** y **buscar**, con 25 filas por página
  como mucho y la página, la búsqueda y el orden en la dirección.
  - En el servidor (`q`, `sort` y `order` en los endpoints de usuarios, tenants, ubicaciones, proyectos, ejecuciones,
    sesiones, auditoría, errores de escaneo, grupos de duplicados y documentos del contexto): `sort` solo admite las
    columnas de cada listado (422 con otra), los vacíos van al final y la paginación es estable.
  - En el cliente, las listas cortas: roles, miembros, plantillas, uso de IA, workers y los documentos de cada grupo de
    duplicados.
  - Los grupos de duplicados, que son tarjetas, tienen un selector «Ordenar por».
- **backend**, **frontend**: **eliminar auditoría por fechas** (`POST /api/v1/audit/purge`), solo el administrador de
  la instancia y solo en su tenant activo:
  - primero una vista previa (`dry_run`) con el número de entradas; después hay que teclear ese número
    (`confirm_count`), y si cambió entretanto responde 409;
  - nunca borra las entradas de hoy (422);
  - el borrado queda en la auditoría (`audit.purge`, con el rango y el número).

### Changed

- **frontend**: **Roles** funciona como Usuarios: listado con «Nuevo rol» y, en cada fila, «Editar» en un modal. Los
  predeterminados salen como «Predeterminado» y se abren con «Ver», en solo lectura; borrar un rol pide confirmación.
- **frontend**: 25 filas por página en todos los listados, sin selector de tamaño (Documentos iba de 50 en 50). Los
  grupos de duplicados siguen de 10 en 10.

### Docs

- **docs**: guías de usuarios y sesiones (listados y borrado de auditoría) y de tenants y roles; ASVS V7.
- **docs**: hueco **G40** y su petición **L-18** a doc_organize: los documentos solo se ordenan por ruta hasta que
  `load_cache_page` admita otro orden.

## [1.1.0] - 2026-11-06

La web usa la API nueva de doc_organize 1.1.0 (G38, G11) y la ficha de workers dice lo que hace cada uno. No quedan
huecos abiertos en doc_organize.

### Added

- **backend**: escaneos más robustos en carpetas de red (G11), con variables del worker:
  - `DOW_SCAN_DOCUMENT_TIMEOUT_SECONDS` (0 = sin límite): el documento que tarda más queda como error y el escaneo
    sigue;
  - `DOW_SCAN_IO_RETRIES` (2): reintentos ante errores de lectura transitorios al listar, leer, hashear y copiar;
  - `DOW_SCAN_REUSE_HASHES` (sí): no rehashear lo que no cambió de tamaño ni fecha («Forzar» rehashea todo).
- **backend**, **frontend**: el resultado de un escaneo cuenta los «Ficheros que no se pudieron leer» (`io_errors`).
- **backend**: `GET /api/v1/admin/workers` añade `running` (ejecuciones en marcha de cada worker) y, en `resources`,
  `slots` y los ajustes del escaneo del worker.

### Changed

- **backend**: los tramos de un escaneo largo (G38) los aplica doc_organize con `ScanOptions.max_documents`: la web ya
  no cuenta eventos ni cancela para partir. Cancelar durante el OCR conserva lo ya procesado
  ([ADR-015](docs/adr/ADR-015-endurecimiento.md), enmienda).
- **frontend**: Administración → Ajustes → Workers se entiende mejor:
  - el estado dice **Libre**, **Trabajando (1 de 1)** o **Sin latido**, en vez de «En marcha», que solo indicaba que
    el proceso tenía latido;
  - la memoria muestra el uso actual, el pico desde que arrancó el contenedor y el límite;
  - columna **Escaneo** con los tramos, el tiempo máximo por documento, los reintentos y los hashes;
  - el último latido en relativo («hace 10 s»), las versiones de cada worker y una introducción a la tabla.

### Docs

- **docs**: G38, G11 y G25 pasan a resueltos. G25 (`DocumentMetadata.from_cache_entry`) no se adopta: la vista previa
  de duplicados ya no rehashea, y su `lstat` detecta los ficheros que ya no están y da el tamaño y la fecha actuales.

## [1.0.1] - 2026-11-06

doc_organize 1.1.0, que incluye su hotfix 1.0.1 (G39). La web todavía no usa la API nueva de la 1.1.0
(`max_documents`, timeouts y reintentos, `from_cache_entry`): llegará en la 1.1.0 de la web.

### Changed

- **backend**: doc_organize 1.1.0, wheel de su release en GitHub con su hash en `uv.lock`
  (`sha256:eef6dfa70562cff70771183384452b4a67fd3f56bf2bb8e0c77de69e8bc760d8`). Con sus valores por defecto escanea
  igual que la 1.0.0. Además:
  - los documentos que no son PDF ni imagen ya no pasan por OCR ni se convierten dos veces (G39); las entradas
    `OCR_PENDING` antiguas se reprocesan una vez en el siguiente escaneo con OCR;
  - cancelar o partir en tramos durante el OCR conserva lo ya procesado (G38);
  - libera memoria durante la conversión y el OCR, y no sigue las *junctions* de Windows.

### Fixed

- **backend**, **frontend**: la ficha «Capacidades de la instancia» sumaba solo el worker de la cola `cpu` y decía «No»
  a la GPU aunque un `worker-gpu` la tuviera lista. Ahora una capacidad está si algún worker vivo la tiene, y la ficha
  dice en qué colas cuando no son todas (p. ej. «cola gpu»). `GET /api/v1/instance/capabilities` añade
  `capability_queues`.

### Docs

- **docs**: hueco G39 (los documentos que no son PDF pasan por OCR y se convierten dos veces) y su petición L-17 a
  doc_organize (hotfix 1.0.1). G12 pasa a resueltos: los detectores son públicos desde doc_organize 0.10.0.

## [1.0.0] - 2026-11-06

Primera versión estable. El código es el de [1.0.0rc1](#100rc1---2026-11-05); solo cambia doc_organize, que pasa a su
1.0.0 final (L-15), con la misma API que 1.0.0rc2.

### Changed

- **backend**: doc_organize 1.0.0, wheel de su release en GitHub con su hash en `uv.lock`
  (`sha256:632e1dbb43ee64914d61e42a03256250f265d33e1cfb8c58d7b01a0baf041034`).

## [1.0.0rc1] - 2026-11-05

Fase 10 — endurecimiento y release 1.0 ([ADR-015](docs/adr/ADR-015-endurecimiento.md),
[ASVS L2](docs/security/ASVS_L2.md)). Primera versión candidata de la 1.0, con doc_organize 1.0.0rc2; la 1.0.0 fijará
doc_organize 1.0.0 (L-15), con la misma API.

### Added

- **backend**: los escaneos largos van en **tramos** (G38). Cada `DOW_SCAN_RECYCLE_DOCUMENTS` documentos convertidos
  (200) el escaneo para de forma ordenada y el worker lo sigue en un subproceso nuevo: misma ejecución, memoria limpia.
  - El tramo nuevo salta las carpetas terminadas.
  - La carpeta a medias se retoma sin repetir «forzar».
  - El resultado suma los tramos (`segments`).
  - Si se pide cancelar o vence el tiempo entre tramos, la ejecución se cierra.
- **backend**: límite por IP. Admite 10 inicios de sesión y 120 escrituras a `/api/v1` por minuto
  (`DOW_RATE_LIMIT_LOGIN`, `DOW_RATE_LIMIT_WRITE`); al pasarse, 429 `rate_limited` con `Retry-After`.
- **backend**: `GET /metrics` en formato Prometheus, solo con el secreto `dow_metrics_token` (si no, 404). Incluye:
  - peticiones y duración por ruta (plantilla), ejecuciones por estado, cola y operación;
  - fallidas por código, workers vivos y tamaño de `config.db`.
- **backend**: `python -m app.cli restore <copia> [--yes]` restaura `config.db` y las cachés con la API de backup de
  SQLite.
  - Sin `--yes` solo enseña la vista previa.
  - Se niega con ejecuciones en marcha o un worker vivo.
  - Guarda lo de antes como `.pre-restore-<UTC>`.
- **backend**: `workers.resources` (migración `0010`) con la memoria del contenedor (límite, pico, uso), los OOM y el
  tamaño de tramo, en `GET /api/v1/admin/workers` junto con `gpu_ready`.
- **frontend**: listados por páginas con la página y el tamaño en la URL (`?page=`, `?size=` de 25, 50 o 100):
  - **Documentos** deja el scroll infinito (50 por página);
  - **Duplicados**, 10 grupos por página y los grupos de más de 5 documentos plegados;
  - Ubicaciones y Tenants pasan a ir por páginas;
  - Ejecuciones, Proyectos, Auditoría, Usuarios y Sesiones usan el mismo control.
- **frontend**: **Continuar el escaneo** en un escaneo que se quedó sin memoria, se cortó, superó el tiempo o se canceló
  (editores). Lanza otro con las mismas opciones y sin «forzar».
- **frontend**: aviso cuando termina una ejecución propia, en la aplicación y, si se da permiso desde el menú de
  usuario, también del navegador con la pestaña en segundo plano.
- **frontend**: Ajustes → Workers enseña la GPU, la memoria (pico de límite), las veces sin memoria y el tamaño de tramo
  de cada worker.
- **frontend**: con un proyecto abierto, sus secciones en el menú lateral (cambio del mantenedor en las pruebas).
- **frontend**: aviso de cómo montar carpetas cuando `/mnt` está vacía (cambio del mantenedor en las pruebas).
- **docker**: `--build-arg WITH_LIBREOFFICE=true` (`soffice`) y `WITH_AV=true` (ffmpeg y Whisper, grupo `av`), en
  compose con `DOW_WITH_LIBREOFFICE`/`DOW_WITH_AV`.
- **docker**: `docker-compose.gpu.yml` y `scripts/smoke_variants.py` para probar cada variante en su contenedor.
  Verificadas en un equipo con RTX 5070:
  - GPU: OCR con EasyOCR, 4,5 s frente a 14-30 s en CPU;
  - LibreOffice 7.4 y ffmpeg 5.1 con Whisper.
  - Imágenes: 3,2 GB la CPU, 5,8 GB con LibreOffice y AV, 11 GB la GPU.
- **backend**: `scripts/load_test.py`, prueba de carga en proceso con 100 000 documentos, 10 000 grupos y 5 000
  ejecuciones sintéticos. Todos los listados por debajo de 500 ms de p95; el más lento, la búsqueda por nombre, 273 ms.
- **frontend**: `npm run safe -- install …` instala con `--before=<hoy - 14 días>`.

### Changed

- **frontend**: en el proyecto, **Duplicados** va el primero, en los botones y en el menú.
- **backend**: cabeceras `Strict-Transport-Security` (un año, fuera de `development`) y `Cache-Control: no-store` en
  toda la API.
- **backend**: el cuerpo de las peticiones se limita a `DOW_MAX_REQUEST_MB` (16): 413 `body_too_large`, y 411 a una
  escritura sin `Content-Length`.
- **backend**: `resume`, el estado interno entre tramos, no sale en el resultado de una ejecución.
- **ia**: vuelve la regla de versiones con al menos 14 días (ADR-001 §6):
  - `exclude-newer = "2 weeks"` en uv, sin cambios en el lock;
  - `cooldown` de 14 días en Dependabot;
  - `npm run safe`.
- **docs**: guías de despliegue (restaurar, métricas, límites, variantes, GPU), ejecuciones (tramos, continuar,
  avisos), documentos y duplicados (páginas). Nuevos ADR-015 y el estado ASVS L2.

### Security

- Revisión ASVS L2 completa ([ASVS_L2.md](docs/security/ASVS_L2.md)): sin CRITICAL ni HIGH.
  - Corregidos tres MEDIUM: sin límite por IP, API sin `no-store` y cuerpo sin límite.
  - Corregido un LOW: sin HSTS.
  - Riesgos aceptados en la 1.0: sin segundo factor y sin comprobar contraseñas filtradas.

## [0.10.1] - 2026-11-05

Hotfix de lo encontrado probando la 0.10.0 con documentos reales, y doc_organize 1.0.0rc2.

### Fixed

- **frontend**: al crear un proyecto con una ubicación de destino vacía no se podía elegir carpeta. En «Usar una
  carpeta vacía» la raíz de la ubicación no vale (el backend la rechaza) y ahora se explica, con «Elegir esta carpeta»
  desactivado en ella; en «Crear carpeta nueva» elegir la raíz ya no se muestra como «Aún no has elegido una carpeta».
- **backend**: un escaneo largo que pasaba el límite de memoria del worker (`DOW_WORKER_MEM_LIMIT`, 6 GB) acababa
  como «La operación terminó de forma inesperada». El worker lee el contador `oom_kill` del cgroup y lo cierra como
  `out_of_memory`, con qué hacer: relanzar (el escaneo continúa donde quedó), subir el límite o escanear por partes.

### Changed

- **backend**: doc_organize **1.0.0rc2**, la pre-release de la librería pura (L-11…L-14): se retiran su web integrada,
  `auth/`, el `tenant_id` de `Project`/`Context`, las `*_config_from_store_or_env` y `MkDocsGenerator`. La web no usaba
  nada de eso: no cambia el código, solo el wheel fijado (hash en `uv.lock`). La 1.0.0 final se fijará al cerrar la
  Fase 10.

## [0.10.0] - 2026-11-03

Fase 9 — multi-tenant y roles ([ADR-013](docs/adr/ADR-013-multi-tenant.md),
[guía](docs/guides/tenants_y_roles.md)). Con ella, la paridad con la web integrada de doc_organize es completa.

### Added

- **backend**: tenants (admin de instancia):
  - `GET/POST /api/v1/tenants`, `PATCH/DELETE /api/v1/tenants/{id}` y `GET /api/v1/tenants/{id}/users`;
  - un tenant se crea con sus roles base y solo se borra vacío (409 `tenant_not_empty`; `default`: 409
    `tenant_protected`);
  - su auditoría pasa a `default` al borrarlo.
- **backend**: tenant activo en la sesión (`PUT /api/v1/auth/tenant`, solo admin de instancia, auditado como
  `session.tenant_switch`).
- **backend**: roles del tenant con permisos de administración:
  - catálogo: `users.manage`, `roles.manage`, `audit.read`, `templates.manage`, `projects.create` y
    `projects.all`;
  - `GET/POST /api/v1/roles`, `GET/PATCH/DELETE /api/v1/roles/{id}` y `GET /api/v1/permissions`;
  - los roles base «Administrador» y «Usuario» no cambian; un rol con usuarios no se borra;
  - nadie da un permiso que no tiene (403 `permission_escalation`);
  - quitar permisos o cambiar el rol de alguien cierra sus sesiones.
- **backend**: aislamiento entre tenants en el dominio, con 404 para lo ajeno:
  - proyectos y todo lo que cuelga de ellos, ubicaciones, plantillas, usuarios, sesiones, roles y auditoría;
  - la auditoría de cada petición va al tenant activo, y la de un job, al tenant de su proyecto.
- **backend**: usuarios con `role_id`, `is_instance_admin` y `tenant_id`:
  - mover a alguien de tenant (solo el admin de instancia) le quita sus membresías y sus sesiones;
  - siempre quedan un admin de instancia y un gestor de usuarios por tenant.
- **backend**: migración `0009_tenants_roles`:
  - crea la tabla `roles`, `users.role_id`, `users.is_instance_admin` y `sessions.acting_tenant_id`;
  - los `admin` pasan a admin de instancia con el rol «Administrador»; los `user`, a «Usuario» (decisión E4).
- **frontend**: **Administración → Tenants** y **Administración → Roles**; selector de tenant en la cabecera para el
  admin de instancia; selector de rol, «Administrador de la instancia» y tenant en el formulario de usuario.
- **docs**: guía [Tenants y roles](docs/guides/tenants_y_roles.md), ADR-013 y E2E `tenancy.spec.ts`.

### Changed

- **backend**: `GET /api/v1/auth/me` deja de devolver `role: admin|user`. Ahora trae `tenant`, `acting_tenant`,
  `is_instance_admin`, `role` (el del tenant) y `permissions` (decisión E5).
- **backend**: `POST/PATCH /api/v1/users` usan `role_id` en lugar de `role`.
- **backend**: lo que antes exigía `admin` exige ahora un permiso:
  - usuarios y sesiones: `users.manage`;
  - auditoría: `audit.read`;
  - plantillas: `templates.manage`;
  - lo que es del servidor, ser admin de instancia: ubicaciones, ajustes, IA, workers y capacidades;
  - crear proyectos: `projects.create`;
  - ver y administrar todos los proyectos: `projects.all`.
- **backend**: las ubicaciones son de un tenant y se registran en el tenant activo. Solo cambian de tenant si ningún
  proyecto las usa (decisión E1).
- **backend**: `alembic/env.py` desactiva las claves foráneas de SQLite durante las migraciones y comprueba
  `PRAGMA foreign_key_check`. Así, recrear una tabla ya no dispara los `ON DELETE` de las demás.
- **frontend**: el menú y las guardas de administración van por permisos (`RequireAccess`), no por el rol `admin`.
- **backend**: doc_organize **0.14.0** (L-3a…L-3e, L-8d…L-8f y L-10), que resuelve G30–G37. La web retira sus rodeos
  ([huecos](docs/plan/DOC_ORGANIZE_GAPS.md#resueltos)):
  - IA: fuera los clientes «vigilados»; `ContextBuilder.build(ai_max_failures=3, ai_max_documents=…)`,
    `*Config.retries` (solo errores de transporte, con espera creciente) y el recuento del run desde el `Context`;
  - borrador: muestra con `select_document_sample(roots=)`;
  - contexto: cada documento con nombre repetido conserva su copia (`<stem>-<8 hex>/`, ruta de `organized_path`), sin
    aviso ni `collisions` en el resultado; fuera `clear_temporaries` y la validación propia de `context.json` (un
    `context.json` no válido cuenta como sin contexto y reconstruir lo sustituye).
- **docs**: guía de contexto (nombres repetidos), ADR-014 y huecos G30–G37 en «Resueltos».

## [0.9.0] - 2026-11-03

Fase 8 — IA: clasificación, manifiestos y uso. Con doc_organize **0.13.0** (la fase pedía 0.10.0, L-3). Cierra la
paridad funcional con la web integrada: solo quedan las filas de roles y tenants (Fase 9).

### Added

- **backend**: configuración de IA de la instancia ([guía](docs/guides/ia.md#configuración-ia-administradores),
  [ADR-004](docs/adr/ADR-004-cifrado-secretos.md)):
  - las 5 familias de la web integrada: clasificación de dominios, clasificación por taxonomía, borrador de
    manifiesto, uso de LiteLLM y uso de GitHub Copilot;
  - tabla `ai_settings` (migración `0008_ai`) con los secretos cifrados con MultiFernet (`DOW_FERNET_KEYS`, nueva
    dependencia `cryptography`);
  - precedencia: valor guardado > variable `DOC_ORGANIZE_*`;
  - `GET /api/v1/admin/ai-settings` y `PUT /api/v1/admin/ai-settings/{family}` (admin) nunca devuelven un secreto,
    solo su origen y sus 4 últimos caracteres;
  - la `base_url` se valida (`http`/`https`, sin credenciales, *query* ni fragmento);
  - cada cambio se audita (`ai_settings.update`) sin valores secretos;
  - `GET /api/v1/ai/status` dice a cualquier usuario qué familias están configuradas;
  - `python -m app.cli rotate-secrets` vuelve a cifrar con la primera clave.
- **backend**: clasificación con IA ([guía](docs/guides/ia.md#clasificar-con-ia),
  [ADR-014](docs/adr/ADR-014-uso-de-servicios-de-ia.md)):
  - `context_build` admite `ai_classification`; se usa la familia de un eje o la de dos ejes según el catálogo, y se
    comprueba al encolar (422 `ai_not_configured`);
  - el subproceso descifra solo esa familia y construye el `*Config` de doc_organize (L-3, G3);
  - ajustes administrables nuevos: `ai_timeout_seconds` (30), `ai_retries` (2) y `ai_max_documents_per_run` (500);
  - se deja de llamar a la IA tras una clave rechazada, tras 3 fallos de conexión seguidos o al llegar al tope (G33,
    G34);
  - el run cuenta lo enviado, lo clasificado y los errores (G35); `context_documents.classified_by` marca lo que
    clasificó la IA.
- **backend**: run `taxonomy_draft` (editor; sustituye a `POST .../context/taxonomy-manifest-draft`):
  - envía una muestra de 1–60 documentos convertidos, con rutas relativas a la ubicación (G36);
  - el borrador va en el resultado del run y no se guarda;
  - se audita (`project.taxonomy_draft`) y su tamaño está acotado (256 KiB).
- **backend**: `GET /api/v1/admin/ai-usage` (admin): uso del periodo actual de LiteLLM y de GitHub Copilot.
  - Caché de 5 minutos por fuente en el proceso; `refresh` como mucho cada 30 s; timeout de 10 s.
  - Una fuente que falla no impide ver la otra. El payload original (`raw`) nunca se devuelve.
- **frontend**: **Administración → Configuración IA** y **Administración → Uso de IA**.
- **frontend**: en la página **Contexto**:
  - interruptor «Clasificar con IA», con aviso de que el contenido sale de la aplicación;
  - marca **IA** en los documentos que clasificó la IA;
  - «Pedir borrador», que carga el manifiesto propuesto en el editor sin guardarlo.
- **frontend**: el resultado de los runs muestra los datos anidados (`ai.*`) y las listas de catálogo por nombre.
- **docker**: servicio `litellm-fake` en `docker-compose.e2e.yml`, un LiteLLM Proxy falso para los E2E sin red.
- **docs**: guía [Inteligencia artificial](docs/guides/ia.md), ADR-014 y E2E `ai.spec.ts`.

### Changed

- **frontend**: el menú lateral se desplaza cuando no cabe (con todos los enlaces de administración quedaba fuera de
  pantalla en alturas de 720 px).
- **backend**: los loggers `httpx` y `httpcore` quedan en WARNING sea cual sea `DOW_LOG_LEVEL`. El cliente de uso de
  LiteLLM lleva la clave en la URL (`/key/info?key=…`) y httpx escribe cada URL en INFO (hallazgo de AUDIT_CODE; G37,
  pedido a doc_organize como L-3e).

### Security

- Las credenciales de IA nunca se escriben en claro: ni en respuestas, `config.db`, `run.json`, eventos SSE, ni
  registros. Los tests lo comprueban buscando la clave en todos esos sitios.

## [0.8.0] - 2026-11-02

Fase 7 — contexto y taxonomías. Con doc_organize **0.13.0** (L-8 y L-8a…L-8c, pedidas antes de la fase).

### Added

- **backend**: plantillas de taxonomía ([guía](docs/guides/contexto.md#plantillas-de-taxonomía)):
  - las incluidas en doc_organize (`calidad`, `sgi-integrado`, `sgi-iso27001`) se listan y leen, en solo lectura;
  - las personalizadas viven en `taxonomy_templates` (migración `0007_context`) y las gestiona el admin
    (`PUT`/`DELETE /api/v1/taxonomy-templates/{name}`, auditado), con el Markdown validado por doc_organize. No pueden
    usar el nombre de una incluida (409 `template_builtin`).
  - Mejora opcional: `GET /api/v1/taxonomy-templates/{name}/download` exporta cualquier plantilla como `.md`.
- **backend**: contexto del proyecto ([guía](docs/guides/contexto.md)):
  - run `context_build` (editor, destino `rw`): reúne los documentos convertidos cuyo original, `.md` y `.json` siguen
    ahí; clasifica por dominios (descubiertos, catálogo propio, plantilla o manifiesto del proyecto); copia a la
    carpeta reorganizada sin seguir enlaces; construye el sitio Zensical con `DOW_CONTEXT_SITE_TIMEOUT_SECONDS` (600 s
    por defecto).
    - Los documentos que no se copian y las colisiones de nombre (G30) quedan como avisos.
    - La clasificación se cancela entre documentos.
    - La plantilla se fija al encolar, con su Markdown vigente, que no se devuelve en el run.
  - run `context_delete` (propietario, con vista previa y nombre del proyecto): borra la carpeta reorganizada, el
    sitio, `context.json` y `domains/`. Solo actúa sobre la carpeta de la vista previa confirmada.
  - El resumen y los documentos se proyectan en `project_contexts` y `context_documents`.
    `GET /api/v1/projects/{id}/context` y `.../context/documents` (por dominio o sin clasificar, filtros «no copiados» y
    «nombre repetido») paginan sin leer el destino.
  - `GET`/`PUT /api/v1/projects/{id}/context/taxonomy-manifest`: el manifiesto del proyecto, validado; el `PUT` exige
    editor, destino `rw` y que no haya otra escritura en el proyecto.
- **backend**: sitio aislado ([ADR-010](docs/adr/ADR-010-sitio-de-contexto-aislado.md)):
  - `POST /api/v1/projects/{id}/context/site-session` da una URL `/site/<token>/` con un token firmado, ligado a la
    sesión y al proyecto, que caduca en una hora;
  - `/site/` sirve el sitio con una CSP `sandbox` propia (sin `allow-same-origin`), `no-referrer` y `no-store`, a
    través del resolvedor y sin seguir enlaces. El token no se escribe en los registros.
- **frontend**: pantalla «Contexto» del proyecto: construir con los cuatro catálogos, dominios y documentos paginados,
  avisos, manifiesto editable, borrar en dos pasos y visor del sitio en un iframe `sandbox`. «Plantillas de taxonomía»
  en la administración: duplicar las incluidas, crear, editar, importar y exportar `.md`.
- **docs**: guía `contexto.md` y ADR-010.

### Changed

- **backend**: doc_organize **0.13.0** con el extra `site` (zensical; la imagen no lleva mkdocs). G10 y G27–G29 pasan
  a «Resueltos».
- **backend**: vaciar el histórico del proyecto borra también la proyección del contexto.
- **docker**: uvicorn arranca con `--no-access-log`; el registro de accesos es el de la aplicación, que oculta el
  token del sitio.

### Security

- **backend**: la carpeta reorganizada que se lee de `context.json` (que se puede cambiar desde el recurso de red) se
  valida antes de copiar o borrar (G32), y los temporales `.tmp` que doc_organize escribe sin `O_NOFOLLOW` se quitan
  si no son ficheros normales (G31). Se piden a doc_organize como L-8e y L-8f.

### Notas

- Dos documentos con el mismo nombre en el mismo dominio y tipo se sobrescriben en la carpeta reorganizada (G30,
  limitación de doc_organize): la web los marca y avisa. Pedido como L-8d.
- Un script incrustado en un documento puede leer la URL del sitio con su token: es un riesgo aceptado y acotado
  (lectura del sitio de ese proyecto, una hora como mucho, mientras siga la sesión). Ver ADR-010.

## [0.7.0] - 2026-11-02

Fase 6 — duplicados. Con doc_organize **0.12.1** (L-11a: ruta relativa en `duplicados/` y movimiento sin seguir
enlaces simbólicos).

### Added

- **backend**: duplicados en dos pasos ([guía](docs/guides/duplicados.md)):
  - run `dedup_preview` (editor): busca duplicados exactos, conflictos de versión y, opcionalmente, nombres parecidos
    (umbral 50–100) con el hash de la caché del último escaneo más un `stat` de cada documento (G25), sin tocar
    ningún fichero. Los grupos se guardan en `duplicate_groups` (migración `0006_duplicates`) con rutas relativas; una
    búsqueda nueva sustituye a las anteriores del proyecto. El modo «nombre parecido» se limita a 5 000 documentos sin
    agrupar (`fuzzy_too_large`);
  - run `dedup_apply` con los grupos confirmados y el documento que se conserva en cada uno, en modo `copy` o
    `report_only` (editor) o `move` (propietario, con el origen `rw`). Exige vista previa (`dry_run`) y el nombre del
    proyecto; la vista previa de grupos caduca a los 60 min o si el proyecto cambió. Cada grupo se comprueba justo
    antes de aplicarlo (hash actual y ningún tramo de la ruta es un enlace): si cambió, se salta. Cada fichero movido o
    copiado queda en la auditoría (`duplicate.move`/`duplicate.copy`), más un resumen (`duplicate.apply`) que se
    escribe también si algo falla a mitad. El informe de doc_organize va al estado del proyecto;
  - `GET /api/v1/runs/{id}/duplicate-groups` (paginado, filtro por motivo) y
    `GET /api/v1/projects/{id}/duplicates/last` (última búsqueda y última aplicación).
- **backend**: informe Excel de los grupos (mejora opcional) como artefacto de la búsqueda, con celdas protegidas
  contra fórmulas.
- **frontend**: pantalla «Duplicados»: búsqueda con umbral difuso, grupos lado a lado por motivo, política de
  conservación (más antiguo, más reciente, ruta más corta) con elección manual por grupo, aplicar en dos pasos y aviso
  si ya se aplicaron duplicados después de la búsqueda. Las decisiones se guardan por búsqueda en la pestaña.

### Changed

- **backend**: doc_organize **0.12.1** (L-11a): en `duplicados/` cada fichero conserva su ruta relativa al origen
  (`duplicados/2024/a.pdf`, G24) y doc_organize ya no sigue enlaces simbólicos al mover o copiar (G26). La web pasa
  rutas reales (resueltas una vez por el resolvedor de ubicaciones).
- **backend**: las respuestas de un run `dedup_apply` resumen la lista de grupos en su número.
- **backend**: doc_organize **0.12.0** (L-10a…L-10e), con sus rodeos retirados:
  - la API abre la caché en solo lectura (`CacheManager(read_only=True)`, G21);
  - la búsqueda de la lista de documentos mira la ruta relativa a la carpeta, no la del servidor (G22, retira el
    riesgo aceptado en la 0.6.0), y nuevo filtro por estado de conversión (`conversion_status`);
  - las rutas de las salidas las calcula `resolve_output_paths` de la librería, sin Docling (G20);
  - el escaneo pasa la carpeta de modelos con `ScanOptions.artifacts_path` y sin descargas (G17);
  - los JSON nuevos llevan `source_path` relativa (G23); el visor sigue reescribiendo los antiguos.
  La caché se guarda durante la conversión (G16) y «forzar» no borra salidas de carpetas ilegibles (G19) sin cambios
  en la web.
- **frontend**: filtro «Estado» en la lista de documentos.
- **docs**: doc_organize 0.12.0 publicada (L-10a…L-10e): G16–G23 pasan a «Resueltos» en `DOC_ORGANIZE_GAPS.md`, con
  sus rodeos pendientes de retirar al subir la dependencia, y la deprecación de la web integrada (L-10) pasa a la
  0.13.0 en `TAREAS_DOC_ORGANIZE.md`, `PARIDAD.md`, `DECISIONES_Y_RIESGOS.md` y el README del plan.
- **docs**: guía `duplicados.md`; huecos G24 y G26 resueltos en 0.12.1 (L-11a) y G25 con rodeo en la web.

### Notas

- Una aplicación admite como mucho 10 000 grupos: con más, la pantalla avisa y hay que filtrar por motivo o buscar de
  nuevo tras aplicar una parte.
- El ZIP de exportación del proyecto no incluye el informe de duplicados de doc_organize (lleva rutas absolutas del
  contenedor).

## [0.6.0] - 2026-11-02

Fase 5 — caché, resultados y descargas. Con doc_organize **0.11.0** (L-7, `doc_organize.export`).

### Added

- **backend**: `GET /api/v1/projects/{id}/documents` ([guía](docs/guides/documentos.md)): documentos de la caché de
  doc_organize de todas las carpetas de origen, paginados en servidor (`count_entries`/`load_cache_page`), con búsqueda
  en la ruta y filtro por carpeta; rutas relativas a la carpeta y errores enmascarados.
- **backend**: visor `GET /api/v1/projects/{id}/outputs?path=`: Markdown, JSON e imágenes de `Conversión/` por el
  resolvedor de ubicaciones, leídos desde el descriptor ya abierto (un enlace simbólico no lo saca de la carpeta), con
  tipo fijo, `nosniff`, CSP `sandbox` y máx. 20 MB; el JSON se sirve con `source_path` relativa.
- **backend**: exportaciones como ejecuciones con el fichero como artefacto: `export_zip` (con `dry_run` para ver su
  tamaño; comprueba cuota y espacio libre antes de escribir) y `export_xlsx` (`cache` o `errors`), con
  `doc_organize.export`; cualquier miembro del proyecto puede exportar. Cierra G8 sin copiar código de la web
  integrada.
- **backend**: búsqueda de texto completo (mejora opcional): índice SQLite FTS5 por proyecto (`search.db`, incremental
  por `mtime` y tamaño), actualizado al terminar cada escaneo y con el run `search_index` (editor);
  `GET /api/v1/projects/{id}/search` con fragmentos, todas las palabras, sin tildes, consulta sin sintaxis FTS5 y con
  tiempo acotado (`search_too_broad`).
- **backend**: copias de seguridad (mejora opcional, adelanta parte de la Fase 10): `python -m app.cli backup
  [--dest] [--keep N]` y `verify-backup` de `config.db` y de las cachés con la API de backup de SQLite, manifiesto con
  SHA-256 y permisos solo para el usuario de la aplicación.
- **frontend**: pantalla «Documentos» con lista virtualizada (`@tanstack/react-virtual`), visor Markdown saneado
  (`marked` + DOMPurify: sin scripts, estilos, formularios, marcos ni imágenes externas) y JSON, búsqueda en el
  contenido y panel de exportaciones.

### Changed

- **backend**: doc_organize **0.11.0** con el extra `export` (`openpyxl`). La API importa `doc_organize.cache` solo al
  listar documentos, sin Docling ni torch (G15; lo comprueba el test de arquitectura).
- **backend**: `folder_state` pasa a `app/domain/scan/state.py` (lo usan el escaneo, las exportaciones y la API).
- **backend**, **ci**: regla de versiones con ≥ 2 semanas suspendida hasta la 1.0 (decisión del mantenedor): sin
  `exclude-newer` ni sus excepciones por paquete en `backend/pyproject.toml` (el `uv.lock` no cambia de versiones),
  sin `--before` en npm y sin `cooldown` en Dependabot. La Fase 10 la reactiva.

### Security

- **backend**: los JSON de `Conversión/` que escribe doc_organize llevan `source_path` con la ruta absoluta del
  servidor y el ZIP los copia tal cual (G23); la búsqueda por nombre filtra sobre la ruta absoluta (G22). Riesgos bajos
  aceptados hasta que doc_organize los corrija (L-10e); el visor ya muestra `source_path` relativa.

### Fixed

- **docker**: variante GPU probada con una GPU NVIDIA real (RTX 5070, `sm_120`, driver 616.92): EasyOCR fallaba en
  todos los documentos con OCR porque creaba `~/.EasyOCR` en el sistema de ficheros de solo lectura, y torch perdía la
  caché de kernels CUDA. `runtime-gpu` fija `EASYOCR_MODULE_PATH` y `PYTORCH_KERNEL_CACHE_PATH` en el tmpfs `/tmp`, y
  el entrypoint crea la carpeta de la caché.
- **docker**: `models-init --easyocr` no podía funcionar (la imagen CPU no trae EasyOCR): nuevo servicio
  `models-init-gpu` (perfil `setup-gpu`) con la imagen `runtime-gpu`. Las guías pasaban `python -m …` como comando de
  `models-init`, que ya lo tiene como entrypoint; ahora solo los argumentos (`download --picture-description`).
- **backend**: cada descarga de modelos reescribía `manifest.json` solo con lo pedido y «olvidaba» la visión o EasyOCR
  descargados antes; ahora conserva los grupos opcionales cuyas carpetas siguen en disco.

## [0.5.0] - 2026-11-01

Fase 4 — escaneo y conversión. Con doc_organize **0.10.0**.

### Added

- **backend**: operación `scan` ([guía](docs/guides/escaneo.md)): `ScanCommand.run_streaming` con `ScanOptions`,
  `on_progress` y `CancelToken` en la capa anticorrupción; incremental (solo nuevos o modificados); cada carpeta de
  origen es un ámbito propio (su caché y sus salidas en `Conversión/<carpeta>/`) para que documentos con el mismo
  nombre en carpetas distintas no se pisen (G18) y para no perder la caché de las terminadas (G16); si una carpeta
  falla se siguen las demás; progreso por fases (`discovery`, `conversion`,
  `ocr`) con el documento actual y rutas relativas a la ubicación; recuentos y duraciones (`ScanSummary`,
  `ScanRunReport`) en el resultado del run y errores (`ScanErrorReport`) en la tabla `scan_errors`, sin rutas del
  contenedor.
- **backend**: «forzar reconversión» (`force`): solo propietarios, todas las carpetas, vista previa (`dry_run`: caché,
  documentos que ya no existen y tamaño de las salidas; caduca si cambian las carpetas) y confirmación con el nombre;
  carpeta a carpeta; se niega si una carpeta no se puede leer o su caché tiene documentos de fuera (G19); auditado.
- **backend**: opciones del escaneo validadas contra las capacidades publicadas por los workers vivos de su cola
  (`422 option_unavailable`); «usar GPU» va a la cola `gpu`; `GET /api/v1/instance/capabilities` añade
  `scan_options` y las capacidades `models_ready`, `picture_description_ready` y `gpu_ready`.
- **backend**: carpetas guardadas (`scanned_folders`, migración `0005_scan`): `GET/POST/DELETE
  /api/v1/projects/{id}/scanned-folders` con `used`, último escaneo y disponibilidad; errores paginados en
  `GET /api/v1/runs/{id}/scan-errors` y `GET /api/v1/projects/{id}/scan-errors` (último escaneo).
- **backend**: modelos de Docling sin Internet ([ADR-011](docs/adr/ADR-011-modelos-sin-internet.md)):
  `python -m app.integrations.doc_organize.models download` escribe un manifiesto en `/models/docling` y el job usa
  `DOCLING_ARTIFACTS_PATH`.
- **docker**: variante GPU: grupos de dependencias `cpu` (por defecto) y `gpu` (torch CUDA 13.0 + EasyOCR) en el
  mismo `uv.lock`, etapa `runtime-gpu`, servicio `worker-gpu` (perfil `gpu`, driver NVIDIA ≥ 580); volumen `models` y
  servicio `models-init` (perfil `setup`). La imagen de producción corre con `HF_HUB_OFFLINE=1`.
- **frontend**: pantalla «Escanear» (carpetas con casilla, estado y último escaneo; añadir y quitar; opciones con ayuda
  contextual y desactivadas según la instancia; forzar reconversión en zona roja), página de errores paginada,
  resultado del escaneo y enlace a sus errores en el detalle del run; capacidades de modelos en Ajustes.
- **ci**: E2E de escaneo real con el worker (HTML y TXT sintéticos): progreso, resultado y segundo escaneo con 0
  conversiones. Test de integración (fuera del CI) con conversión real de un PDF generado con Pillow 13, incremental y
  cancelación entre documentos que conserva la caché.
- **docs**: guía [Escaneo y conversión](docs/guides/escaneo.md), ADR-011, notas de la Fase 4 en ADR-002 y ADR-006,
  despliegue con modelos y worker con GPU.

### Changed

- **backend**: al vencer `DOW_JOB_TIMEOUT_SECONDS` el worker pide una **parada ordenada** (`runs.cancel_reason`) y
  espera `DOW_TIMEOUT_GRACE_SECONDS` (10 min) antes de terminar el subproceso: la operación guarda lo hecho y el run
  acaba `failed`/`timeout` con el resultado parcial.
- **backend**: las carpetas de origen de un proyecto ya no pueden anidarse (`422 nested_folders`) en vez de quedarse
  con la de fuera: la ruta de cada salida depende de la carpeta escaneada.
- **frontend**: «Probar el motor» pasa a ser solo para administradores; el proyecto ofrece «Escanear».

### Security

- **backend**: el `run.log` descargable ya no lleva rutas del contenedor ni trazas de las librerías (solo registros de
  la aplicación y avisos, enmascarados, máx. 20 MB); los mensajes de `scan_errors` se enmascaran igual y se guardan
  como mucho 10 000 por run. `models-init` corre sin secretos ni `config.db`.
- **backend**: Pillow **13.0.0** (41 alertas, 5 críticas, al leer JPEG, TIFF, FlashPix y PDF) como mínimo explícito,
  con docling/docling-slim 2.142.0, docling-core 2.104.0, docling-parse 7.22.4 y docling-ibm-models 4.0.4 por
  excepción de seguridad a `exclude-newer` (levantan el límite `pillow<13`).

## [0.4.0] - 2026-11-01

Fase 3 — proyectos y motor de ejecuciones. Con doc_organize **0.10.0**.

### Added

- **backend**: migración `0004_projects_runs` (`projects`, `project_members`, `runs`, `run_events`, `artifacts`,
  `workers`, `periodic_tasks`). Proyectos con origen (ubicación + hasta 20 carpetas) y una carpeta de salidas **propia**
  en una ubicación de destino `rw` (nueva o vacía al crearla), estado de doc_organize en `/data/projects/<id>`
  (`ProjectLayout` con `state_root`, L-5); miembros `owner`/`editor`/`viewer` (cualquier usuario crea proyectos y queda
  como propietario; un admin actúa como propietario de todos); proyecto ajeno o borrado → 404.
- **backend**: motor de ejecuciones ([ADR-002](docs/adr/ADR-002-ejecucion-de-jobs.md)): cola sobre `runs` con reclamo
  atómico (`UPDATE … RETURNING`), colas `cpu`/`gpu`, un subproceso *spawn* por job que recibe solo el `run_id`,
  latido, huérfanos, cancelación cooperativa con terminación forzada fuera de las fases críticas, timeout, una
  escritura por proyecto garantizada por un índice único parcial (`409 write_locked`), tope de 5 runs activos por
  usuario, tareas periódicas (sondeo de ubicaciones, purga del workspace, capacidades) y `run.json`/`run.log` por run.
- **backend**: progreso por **SSE** en `GET /api/v1/runs/{id}/events`, reanudable con `Last-Event-ID`
  ([ADR-008](docs/adr/ADR-008-progreso-sse.md)); historial, detalle, cancelación y descarga de artefactos (adjunto,
  `nosniff`, tipo fijo; 410 tras la retención).
- **backend**: operaciones `noop` (prueba del motor), `history_clear` (`ProjectHistoryCleaner` con `state_root`),
  `project_move` (renombrado atómico o copia → cambio en la BD → borrado del origen, con vuelta atrás si la copia
  falla) y `project_delete` (con o sin las salidas). Las tres que mueven o borran exigen una **vista previa**
  (`dry_run`) de menos de 15 min sin escrituras posteriores y el nombre del proyecto tecleado, rechazan una carpeta de
  salidas sustituida por un enlace y se auditan.
- **backend**: `/api/v1/projects` (+ miembros y lanzar runs), `/api/v1/runs`, `/api/v1/users/lookup`,
  `/api/v1/admin/workers`; ajustes administrables `location_probe_interval_minutes`, `run_retention_days` y
  `user_quota_mb`; `/api/health` añade `worker` (`ok`/`stale`/`none`).
- **frontend**: «Proyectos» (lista, alta con exploradores de origen y destino, dashboard con últimas ejecuciones,
  miembros y zona de peligro con vista previa y confirmación por nombre) y «Ejecuciones» (historial con filtros,
  detalle con progreso en vivo por `EventSource`, anuncios `aria-live` por fase y cada 10 %, avisos, resultado,
  ficheros y cancelación); tarjeta de workers en Ajustes; estado del worker en Inicio.
- **ci**: el E2E levanta `web` + `worker` con un origen de solo lectura y un destino de escritura sintéticos: crea un
  proyecto, sigue el progreso en vivo y cancela una ejecución tras cerrar la pestaña.
- **docs**: ADR-008, notas de implementación en ADR-002/005/007, guías [Proyectos](docs/guides/proyectos.md) y
  [Ejecuciones](docs/guides/ejecuciones.md), despliegue con el worker.

### Changed

- **docker**: el servicio `worker` arranca por defecto (sale del perfil `worker`) y monta las mismas ubicaciones que
  `web`; publica las capacidades de su contenedor y la API deja de lanzar su propio subproceso de capacidades.
- **backend**: borrar una ubicación que usa algún proyecto responde 409.
- **frontend**: la ficha de capacidades indica si no hay worker en marcha y las colas atendidas.
- **backend**: doc_organize **0.10.0** (wheel de su release, SHA-256 `4ca73b85…6fc2` en `uv.lock`), con la API pública
  que necesitan las Fases 3 y siguientes. Sin cambios funcionales en la web.
- **docs**: `DOC_ORGANIZE_GAPS.md` pasa G1–G7, G13 y G15 a «Resueltos» por doc_organize 0.10.0 (G9 y G14 ya lo
  estaban); ADR-006 recoge el workflow de release de doc_organize.
- **ci**: la suite corre en los PR y en `develop`, no en `main`. Los PR se fusionan con squash y `main` avanza por
  fast-forward a un commit de `develop` con el CI en verde (rulesets; `docs/guides/publicar_version.md`).

### Security

- **backend**: certifi 2026.10.18 (retira los raíz de emSign con intermedias comprometidas), filelock 4.2.1 (17
  alertas) y setuptools 84.1.0, con excepción por paquete a `exclude-newer` en `backend/pyproject.toml`. Pillow
  (41 alertas) queda para antes de la Fase 4: exige subir también la familia Docling, que limitaba `pillow<13` hasta
  sus versiones del 2026-10-21/22.

## [0.3.0] - 2026-10-31

Fase 2 — ubicaciones locales/red y ajustes administrables. Sigue con doc_organize **0.9.3**.

### Added

- **backend**: migración `0003_locations_settings` (`locations`, `app_settings`). Ubicaciones registradas por un admin
  bajo `DOW_LOCATIONS_ROOT` (`/mnt`) con uso (origen/destino/ambas), acceso (`ro`/`rw`), tipo (local/red) y ruta para
  mostrar; la carpeta del contenedor es inmutable y se rechazan solapes, la propia `/mnt` y carpetas que contengan
  `data`/`workspace` ([ADR-007](docs/adr/ADR-007-ubicaciones.md)).
- **backend**: resolvedor único de rutas (`app/domain/locations/paths.py`): solo rutas relativas; rechaza absolutas,
  UNC, unidades, `\`, `..` y bytes nulos (400); `resolve(strict)` + `is_relative_to` contra enlaces simbólicos;
  mismo 404 para «fuera de la ubicación» y «no existe»; montaje caído o colgado → 503 con timeout de E/S.
- **backend**: sondeo de ubicaciones (`ok`/`degraded`/`unavailable`: existencia, lectura, latencia, espacio libre y
  escritura en `rw`) bajo demanda; `/api/health` añade el peor estado agregado (`locations`).
- **backend**: `/api/v1/locations` (CRUD admin, lectura para cualquier sesión sin la ruta del contenedor),
  `/api/v1/fs/browse` (sustituye a `/api/fs/browse`), `/api/v1/admin/mounts`, `/api/v1/admin/settings` y
  `/api/v1/instance/capabilities` + `/api/v1/admin/capabilities/refresh`.
- **backend**: ajustes administrables sin reiniciar con precedencia BD > `DOW_*` > defecto
  ([ADR-012](docs/adr/ADR-012-ajustes-administrables.md)): sesión, bloqueo, contraseña y umbrales del sondeo; auditados.
- **backend**: ficha de capacidades (GPU, Whisper + ffmpeg, LibreOffice) obtenida en un **subproceso** con caché de 1 h:
  importar los detectores de doc_organize carga Docling y torch (G15).
- **frontend**: «Ubicaciones» (lista con semáforo de estado accesible, detalle con explorador), alta/edición con el
  explorador de `/mnt`, «Comprobar» y borrado con confirmación por nombre; componentes `FolderBrowser` y `StatusLight`;
  «Administración → Ajustes» con origen de cada valor y ficha de capacidades.
- **ci**: `docker-compose.e2e.yml` monta una carpeta sintética en `/mnt/e2e` y un E2E registra y explora una ubicación.
- **docs**: ADR-007, ADR-012, guías [Ubicaciones](docs/guides/ubicaciones.md) y
  [Montar carpetas de red](docs/guides/carpetas_de_red.md); hueco G15 en `DOC_ORGANIZE_GAPS.md`; PARIDAD del
  explorador y del semáforo.

### Changed

- **backend**: las dependencias de la API y el CLI reciben los ajustes efectivos (`SettingsDep` = `Settings` con
  `app_settings` aplicado).

## [0.2.0] - 2026-10-31

Fase 1 — identidad y multiusuario. Sigue con doc_organize **0.9.3** (esta fase no usa su API).

### Added

- **backend**: migración `0002_identity` con `tenants` (fila `default`), `users` (`tenant_id`, nombre único en la
  instancia), `sessions` y `audit_log`; contraseñas Argon2id (`pwdlib[argon2]`) con política de 12–128 caracteres,
  distinta del usuario y fuera de las 10 000 más frecuentes de SecLists (también su núcleo sin dígitos ni símbolos);
  bloqueo tras 5 intentos fallidos durante 15 minutos.
- **backend**: sesión de servidor en la cookie `__Host-dow_session` (`HttpOnly; Secure; SameSite=Lax`) con caducidad
  por inactividad y absoluta, rotación al iniciar sesión y CSRF de doble envío firmado (`__Host-dow_csrf` +
  `X-CSRF-Token`); en `development`, `dow_session`/`dow_csrf` sin `Secure`.
- **backend**: `/api/v1/auth` (`csrf`, `login`, `logout`, `me`, `password`), `/api/v1/users` (alta, edición, cambio de
  rol, desactivación, restablecer contraseña y `unlock`), `/api/v1/sessions` (el admin, todas; cada usuario, las
  suyas) y `/api/v1/audit` (filtros por acción, autor y fechas con zona).
- **backend**: `python -m app.cli create-admin --username <u> [--password-stdin]` para el primer administrador.
- **frontend**: inicio de sesión, guardas de ruta, menú de usuario, cambio de contraseña, «Mis sesiones» y
  administración de usuarios (con desbloqueo), sesiones y auditoría; formularios con React Hook Form + Zod; pantallas
  en rutas lazy con `features.json` cargado bajo demanda y librerías en chunks propios (ningún chunk supera 500 kB).
- **ci**: el job `image` crea un admin con el CLI y ejecuta los E2E de login, administración y cambio de contraseña.
- **docs**: guía [usuarios y sesiones](docs/guides/usuarios_y_sesiones.md), primer admin en la guía de despliegue y notas
  de implementación en ADR-003.

### Changed

- **backend**: los errores de dominio (`AppError`) se devuelven como *problem details* con su estado HTTP.
- **docs**: `PARIDAD.md` marca las filas de la Fase 1; borrar usuarios pasa a desactivarlos (sustitución deliberada).

### Security

- Respuesta `401` única en el login (usuario inexistente, desactivado, bloqueado o contraseña errónea) con verificación
  ficticia para igualar tiempos; la auditoría no guarda el nombre probado si el usuario no existe.

## [0.1.0] - 2026-10-31

Fase 0 — fundaciones. Consume doc_organize **0.9.3**.

### Added

- **backend**: esqueleto FastAPI con capas `core`, `db`, `api`, `domain`, `integrations/doc_organize`, `jobs` y
  `workspace`. Ajustes `DOW_*` con Docker secrets (`dow_app_secret_key` y `dow_fernet_keys` obligatorios en
  producción); logs JSON con `request_id` (`X-Request-ID`); errores RFC 9457; cabeceras de seguridad y CSP; SQLite con
  WAL, `synchronous=NORMAL`, `busy_timeout` y claves foráneas; Alembic con la revisión `0001` vacía.
- **backend**: `GET /api/health` (`200 ok` / `503 degraded`) con las versiones de la aplicación y de doc_organize y el
  estado de `config.db`; SPA servida en `/` con *fallback*; `/api/docs` solo en `development` y sin
  `/api/openapi.json` en producción.
- **backend**: capa anticorrupción con test de arquitectura (solo `app/integrations/doc_organize` importa
  doc_organize o Docling; `domain` sin FastAPI); `scripts/export_openapi.py --check`; worker mínimo (`app.jobs.worker`).
- **frontend**: React 19 + TypeScript 5.9 estricto + Vite 8, Mantine 9 (tema claro/oscuro automático), React Router 8,
  TanStack Query 5, i18next en español (`core.json` / `features.json`), cliente `openapi-fetch` generado; layout con
  navegación por fases, página de salud y 404; ESLint, Prettier, Vitest y E2E de humo con Playwright.
- **docker**: Dockerfile multi-stage (`frontend-build`, `backend-build`, `backend-dev`, `runtime` CPU) con usuario no
  root, `read_only`, `tmpfs`, `cap_drop: ALL`, `no-new-privileges` y `HEALTHCHECK`; compose con `web` y `worker`
  (perfil), secretos y volúmenes `data`/`workspace`; `docker-compose.dev.yml` con ubicaciones locales de prueba;
  `scripts/generate_secrets.py`.
- **ci**: jobs `backend`, `frontend`, `docs` (`zensical build --strict`) e `image` (build, `/api/health`, import de
  Docling en la imagen y E2E); Dependabot para uv, npm, Docker y Actions con *cooldown* de 14 días.
- **docs**: sitio Zensical; ADR-001 a ADR-006; `PARIDAD.md` (inventario L-0 de la web integrada: 65 rutas HTTP,
  4 WebSocket y 20 plantillas); guías de desarrollo, despliegue y publicación; `LICENSE` (MIT), `CONTRIBUTING.md` y
  plantillas de issue.
- **ia**: configuración IA para Claude Code y GitHub Copilot (WD-0.3).

### Changed

- **docs**: `DOC_ORGANIZE_GAPS.md` con G14 y la sección «Resueltos» (G9 y G14 por doc_organize 0.9.3; G1 en parte).

### Removed

- `scripts/check_doc_links.py`: lo sustituye `zensical build --strict`.

### Notas

- doc_organize se instala desde el wheel de su release `v0.9.3` (URL + hash en `uv.lock`); torch y torchvision, desde
  el índice CPU de PyTorch.
