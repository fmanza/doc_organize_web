# PLAN — Fase 10: Endurecimiento y release 1.0

## 1. Historias y DoD

| ID | Historia | Hecho cuando |
|---|---|---|
| WB-10.1 | ASVS L2 completo y remediado | `/security-review` completo al empezar IMPLEMENT; sus CRITICAL/HIGH corregidos, MEDIUM corregidos o aceptados por escrito en `docs/security/ASVS_L2.md` (requisito → estado → evidencia) |
| WB-10.2 | Rate limiting | Limitador en memoria por IP (un único proceso uvicorn) en `POST /auth/login` y en las mutaciones de `/api/v1`; 429 *problem details* con `Retry-After`; ajustes `DOW_RATE_LIMIT_*`; se suma al bloqueo por cuenta que ya existe |
| WB-10.3 | `/metrics` | Formato de texto Prometheus escrito a mano (sin dependencias): peticiones por ruta plantilla y estado, duración, runs por estado y cola, OOM del worker, tamaño de la BD. Solo con el secreto `dow_metrics_token` (`Authorization: Bearer`); sin él, 404 |
| WB-10.4 | Restaurar copias | `python -m app.cli restore <copia>` con web y worker parados: verifica la copia (`verify-backup`), guarda la BD actual aparte (`*.pre-restore`), restaura `config.db` y cada `projects/<id>/cache.db` con `sqlite3 .backup`, y aplica `alembic upgrade`. Guía en `despliegue.md` y simulacro de restauración automatizado en un test |
| WB-10.5 | Escaneos largos sin OOM | El subproceso del escaneo se recicla cada `DOW_SCAN_RECYCLE_DOCUMENTS` documentos convertidos (200 por defecto; 0 = nunca): se para de forma ordenada (`CancelToken`, la caché se guarda, G16) y el worker lanza un subproceso nuevo para el **mismo run**, que sigue donde se quedó gracias a la caché. Progreso y log continuos; el resultado suma los tramos (`result.segments`). Rodeo de G38 |
| WB-10.6 | Carga a escala de diseño | `scripts/load_test.py`: genera un proyecto sintético de 100 000 entradas de caché y 10 000 grupos de duplicados, sin convertir nada, y mide p50/p95 de las páginas de documentos, búsqueda, duplicados y runs. Objetivo: p95 < 500 ms por página. Informe en `build/logs/` y resumen en `docs/guides/despliegue.md` |
| WB-10.7 | Variantes de imagen verificadas | `WITH_LIBREOFFICE` y `WITH_AV` como `ARG` del Dockerfile (por defecto `false`); variante GPU verificada en este equipo (worker `doc_organize_web-gpu`, cola `gpu`, OCR de un PDF escaneado sintético con EasyOCR); LibreOffice (`.docx`/`.odt` sintéticos) y AV (ffmpeg/whisper: PENDIENTE DE VERIFICAR qué pide el extra `av`). Script `scripts/smoke_variants.sh` y `docker-compose.gpu.yml` para las pruebas |
| WB-10.8 | Regla de versiones ≥ 2 semanas | `exclude-newer` en `backend/pyproject.toml` con excepción para doc_organize (se publica para la web), `--before`/equivalente en npm, `cooldown: default-days: 14` en Dependabot; SHARED § «Dependencias», ADR-001 §6, `desarrollo.md`, `DEPENDENCIAS.md` |
| WB-10.9 | doc_organize 1.0.0 | La web cierra con 1.0.0rc2 → doc_organize publica 1.0.0 (L-15) → se fija en `uv.lock` (URL y hash) y se publica la web 1.0.0 |
| WF-10.1 | Duplicados primero | En el proyecto: Duplicados, Escaneo, Documentos, Contexto, en botones y en el menú lateral (`PROJECT_SECTIONS`). Escaneo sigue siendo el botón destacado |
| WF-10.2 | Paginación de los listados largos | Componente común `PagedTable`/`usePage` con la página en la URL (`?page=`) y selector de tamaño (25/50/100): Documentos (deja el scroll infinito), Duplicados (10 grupos por página; los grupos de más de 5 miembros se pliegan), log del run (últimas 200 líneas y «ver todo»), artefactos del run, Ubicaciones, Tenants, miembros y plantillas. Las que ya paginan (Runs, Proyectos, Auditoría, Usuarios, Sesiones, Contexto) pasan al mismo componente |
| WF-10.3 | Cambios de prueba del mantenedor | Menú del proyecto abierto en la barra lateral (sin las secciones «Fase N» desactivadas), aviso de `/mnt` vacía, `.gitignore` del override |
| WD-10.1 | E2E de todos los flujos | Lo que falta: restauración (CLI, fuera de Playwright), reciclado del escaneo (con `DOW_SCAN_RECYCLE_DOCUMENTS=2` y documentos sintéticos), 429 en el login, paginación con `?page=` y el orden del menú |

DoD común: comandos de desarrollo en verde, OpenAPI y cliente regenerados, tests de autorización, imagen y
`/api/health` 200, CHANGELOG, guías, `TRACEABILITY.md` y PARIDAD. **Sin migración Alembic**: el reciclado guarda los
tramos en `runs.result`/`runs.progress` (JSON) y el limitador vive en memoria.

## 2. doc_organize

- Requiere **1.0.0** (L-11…L-15). Publicadas 1.0.0rc1 y **1.0.0rc2** (fijada, PR #33). La final (L-15) la publica
  doc_organize **cuando esta fase cierre**: la web se valida con rc2, se pide L-15 y se fija la 1.0.0 (misma API que
  rc2 según su CHANGELOG: solo cambia la versión).
- Firmas usadas (tag `v1.0.0rc2`, verificadas en `../doc_organize/src`): `ScanOptions` (`cache_save_every`,
  `cache_save_seconds`, `artifacts_path`, `allow_model_downloads`, …) y `CancelToken`, sin cambios. **No hay opción
  para limitar los documentos de una llamada** → el reciclado se hace con `CancelToken` desde la capa anticorrupción
  contando los `ProgressEvent` de conversión.
- Huecos nuevos:
  - **G38** — La memoria del proceso crece durante un escaneo largo con OCR (521 documentos reales: OOM a 6 GiB tras
    2 h 13 min). Rodeo: reciclar el subproceso (WB-10.5). Petición a doc_organize (post-1.0, no bloquea): **L-16**
    `ScanOptions.max_documents` (parar limpio tras N) y liberar Docling/OCR entre documentos o documentar el
    crecimiento.
- Siguen abiertos y **no bloquean la 1.0**: G11 (L-9 reintentos/timeout por documento), G12 (L-9b
  `doc_organize.diagnostics`), G25 (opcional).

## 3. Contrato HTTP

| Cambio | Detalle |
|---|---|
| `GET /metrics` (fuera de `/api/v1`, no en OpenAPI) | `text/plain; version=0.0.4`; `Bearer <dow_metrics_token>`; sin secreto o token erróneo → 404 |
| 429 en `POST /api/v1/auth/login` y mutaciones | `application/problem+json`, `code: rate_limited`, cabecera `Retry-After` (segundos); en OpenAPI como respuesta común |
| `RunOut.result.segments` | entero (tramos del escaneo); solo informativo |
| `GET /api/v1/health` | `worker.scan_recycle_documents` en la ficha (para la UI y el soporte) |
| Paginación | Sin cambios de API: todos los listados ya tienen `limit/offset` acotado. `GET /api/v1/tenants` y `/locations` se piden por páginas en vez de `limit=200` |

Eventos SSE: un `log` «Tramo N terminado; continúa en un proceso nuevo» al reciclar; `status` no cambia (sigue
`running`).

## 4. Modelo de datos

Sin tablas ni columnas nuevas. Settings nuevos: `DOW_RATE_LIMIT_LOGIN` (10/min por IP), `DOW_RATE_LIMIT_WRITE`
(120/min por IP), `DOW_SCAN_RECYCLE_DOCUMENTS` (200), secreto opcional `dow_metrics_token`.

## 5. Rutas del sistema de ficheros

- `restore` escribe solo en `DOW_DATA_DIR` (volumen local `data`), nunca en una ubicación; la copia de origen la
  elige el operador por CLI dentro de `DOW_BACKUP_DIR` (se rechaza fuera, como `verify-backup`).
- El reciclado reutiliza las carpetas ya resueltas y autorizadas al encolar (no vuelve a resolver nada del usuario).
- `load_test.py` crea su proyecto en un `DOW_DATA_DIR` temporal; los documentos son entradas de caché sintéticas.

## 6. Frontend

| Pantalla/componente | Cambio |
|---|---|
| `components/PagedTable.tsx` + `usePage.ts` (nuevos) | página y tamaño en la URL, `Pagination` de Mantine, total con `formatCount`, foco al cambiar de página |
| `DocumentsPage` | tabla paginada en lugar de lista virtual infinita (sigue la búsqueda y el filtro de estado) |
| `DuplicatesPage` | 10 grupos por página, miembros plegados (>5), la selección por grupo se conserva al cambiar de página |
| `RunDetailPage` | log con las 200 últimas líneas y «Ver todo»; artefactos paginados; nota «N tramos» si `segments > 1` |
| `ProjectDetailPage`, `Layout` | orden Duplicados → Escaneo → Documentos → Contexto |
| `FolderBrowser`, `Layout`, i18n | cambios de prueba del mantenedor (ya revisados y en verde) |
| `HomePage` | aviso si el escaneo se recicla (`scan_recycle_documents`) |

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| El reciclado para a mitad de un documento | Se para en el `CancelToken`, que doc_organize comprueba entre documentos; lo convertido ya está en caché (G2, G16). Test con N=2 |
| Reciclado infinito (un documento que por sí solo agota la memoria) | Si un tramo muere por OOM sin convertir ninguno nuevo, el run termina en `out_of_memory` (no se relanza) |
| Limitador en memoria con varios procesos | Hoy un único uvicorn; documentado. Detrás de un proxy, la IP sale de `--proxy-headers` (solo si `FORWARDED_ALLOW_IPS` lo permite) |
| `/metrics` filtra datos | Sin nombres de proyecto, usuario ni ruta: solo la ruta plantilla (`/api/v1/projects/{project_id}`) y contadores |
| Restaurar sobre una app en marcha | `restore` se niega si la BD está bloqueada o hay runs `running`; guía «para web y worker antes» |
| Regla de 2 semanas y doc_organize 1.0.0 recién publicada | `exclude-newer-package` para doc_organize (PENDIENTE DE VERIFICAR la sintaxis en uv 0.13.1) |
| Tamaño de imagen con LibreOffice/AV | Solo con `ARG` explícito; la imagen por defecto no cambia; tamaño medido en el CHANGELOG |
| Memoria de Docling en la carga | La prueba de carga no convierte: mide la API, no Docling |
| GPU en un portátil con Windows (Docker Desktop + WSL2), no en el servidor Linux | Se verifica aquí y se documenta como tal; la verificación en el servidor Linux queda como paso de despliegue |

## 8. Pruebas

- Backend unit: limitador (ventana, `Retry-After`), exposición de métricas, reciclado (contador de conversiones →
  cancelación por tramo), `restore` (copia → restaura → integridad, rechazo de rutas fuera de `DOW_BACKUP_DIR`).
- Backend API: 429 en login y escritura; `/metrics` con y sin token (404); runs con varios tramos; autorización
  sin cambios (suite actual).
- Integración (fuera del CI, `@pytest.mark.integration`/`gpu`): escaneo real con OCR en la cola `gpu`; LibreOffice.
- Frontend Vitest: `PagedTable`/`usePage` (URL), Documentos y Duplicados paginados, orden del menú, log recortado.
- E2E Playwright: lo de WD-10.1 sobre la pila aislada (`COMPOSE_PROJECT_NAME`), con documentos sintéticos.
- Carga: `scripts/load_test.py` contra la imagen de la release, informe en `build/logs/`.
