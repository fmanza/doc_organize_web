# TRACEABILITY

## Session metadata
- id: 2026-11-05-fase10
- fecha: 2026-11-05
- rama: `feature/fase10` (desde develop `698499d`: hotfix 0.10.1 + doc_organize 1.0.0rc2); sin commit todavía
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
`/phase 10` ([00_REQUEST.md](00_REQUEST.md)):
- alcance completo;
- «proponme mejoras»;
- GPU en este equipo (worker `doc_organize_web-gpu`), con «añade lo que necesites para las pruebas».

Incluye lo que pidió el mantenedor tras probar la 0.10.0 con documentos reales:
- sus cambios de prueba sin subir;
- Duplicados el primero;
- paginar los listados largos;
- que un escaneo largo no muera por OOM.

«IMPLEMENT» sin más se tomó como aceptación de las recomendaciones del [PLAN](PLAN.md):
- mejoras M1 a M3;
- 1.0.0rc1 y después 1.0.0;
- tramos de 200 documentos;
- Duplicados el primero en botones y menú.

## Context supplied
- ROADMAP (Fase 10), DOC_ORGANIZE_GAPS y TAREAS_DOC_ORGANIZE (L-15), CHANGELOG de doc_organize 1.0.0rc2 y
  `ScanOptions` y `ProgressEmitter` del clon local (solo lectura).
- Análisis de causa raíz del escaneo de «Proyecto_1» (hotfix 0.10.1): OOM a 6 GiB tras 2 h 13 min, con 521
  documentos reales.
- `stash` con los cambios de prueba del mantenedor, recuperado sobre `develop` sin conflictos.

## AI output summary
- **PLAN + AUDIT_PLAN**: `GO_CONDICIONAL`, con tres condiciones:
  - doc_organize 1.0.0 (L-15) al final;
  - la GPU se verifica en el portátil, no en el servidor Linux;
  - comprobar la sintaxis de la regla de 14 días.
- **Tramos (G38)**:
  - `ConversionCounter` en la capa anticorrupción: solo cuenta al terminar un documento y no corta en el último de la
    fase;
  - `ScanRequest.max_conversions`, que para con el `CancelToken`;
  - `JobRecycle` y salida 75 en el runner;
  - `JobWorker._recycle` relanza el mismo run, o lo cierra si entretanto se pidió parar;
  - el job `scan` retoma con `runs.result["resume"]` (carpetas hechas, carpeta a medias sin «forzar» ni recontar el
    descubrimiento), y la API oculta `resume`.
- **Endurecimiento**:
  - `core/ratelimit.py` (ventana deslizante por IP);
  - `core/metrics.py` y `api/metrics.py` (`/metrics` con token, 404 sin él);
  - `BodyLimitMiddleware` (413 y 411);
  - HSTS y `no-store` en `RequestMiddleware`;
  - `backup.restore_plan`/`restore_backup` y `app.cli restore [--yes]`.
- **M3**: `workers.resources` (migración 0010, con *downgrade*), leída del cgroup en cada latido, en
  `WorkerOut.resources` y `gpu_ready`.
- **Frontend**:
  - `components/Paging.tsx` y `usePageState.ts` (página en la URL), aplicados a Documentos (adiós al scroll infinito),
    Duplicados (10 por página y grupos plegados) y otras 7 pantallas;
  - `RunNotifier` (M2);
  - `ContinueScan` y el log recortado en el detalle (M1);
  - recursos en Ajustes → Workers;
  - Duplicados primero;
  - cambios del mantenedor integrados.
- **Docker**: `ARG WITH_LIBREOFFICE`/`WITH_AV` (grupo uv `av`), `docker-compose.gpu.yml` y
  `scripts/smoke_variants.py`. En el compose E2E, tramos de un documento y 1000 inicios de sesión por minuto.
- **Dependencias**: `exclude-newer = "2 weeks"`, que deja `uv.lock` sin cambios de versión; `npm run safe`;
  `cooldown` de 14 días en Dependabot.
- **Docs**:
  - ADR-015 y `docs/security/ASVS_L2.md`;
  - guías de despliegue, ejecuciones, documentos, duplicados y desarrollo;
  - G38 y L-16;
  - ROADMAP, PARIDAD, MEJORAS, ADR-001, DEPENDENCIAS y SHARED.

## AUDIT_CODE
- **Seguridad (ASVS L2)**: tres MEDIUM y un LOW corregidos (límite por IP, `no-store`, cuerpo acotado y HSTS). Sin
  CRITICAL ni HIGH. Riesgos aceptados: sin MFA y sin lista de contraseñas filtradas.
- **Revisión propia del diff**:
  - una `?page=` vieja dejaba la lista vacía sin controles: corregido, con su test;
  - el aviso no veía las ejecuciones cortas: ahora mira las recientes;
  - el tramo vacío al empezar la fase OCR: corregido.
- **Backend (Linux, imagen `backend-dev`)**: ruff y mypy en verde, `export_openapi --check` sin diferencias, **495
  passed**. Logs en `build/logs/fase10-backend-final.txt`.
- **Integración** (Docling real): los tramos convierten 5 + 5 + 2 documentos y la cancelación conserva la caché.
- **Frontend**: format, lint, typecheck, **95 tests** y build en verde (`fase10-frontend-final.txt`).
- **Docs**: `zensical build --strict` sin avisos.
- **Imagen**: pila aislada `dowf10` en el puerto 8091, `/api/health` 200 con HSTS y `no-store`. **E2E 18/18**:
  - el escaneo en 2 tramos;
  - el aviso al terminar;
  - el menú del proyecto;
  - la memoria de los workers;
  - el 413.
- **Carga (100 000 documentos, 10 000 grupos, 5 000 runs)**: todos los p95 por debajo de 500 ms; el más lento, la
  búsqueda por nombre, 273 ms (`fase10-carga.json`).
- **Variantes**:
  - GPU (RTX 5070): `gpu_ready` y el PDF escaneado con EasyOCR en 4,5 s;
  - LibreOffice 7.4 y ffmpeg 5.1 con Whisper;
  - imágenes: 3,2 GB la CPU, 5,8 GB con LibreOffice y AV, 11 GB la GPU.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN | `.ai/sessions/2026-11-05-fase10/PLAN.md` | emitido |
| IMPLEMENT | `backend/app/{core,api,db,jobs,integrations}/…`, `backend/alembic/versions/0010_worker_resources.py`, `frontend/src/{components,features}/…`, `docker/`, `docker-compose*.yml`, `scripts/smoke_variants.py`, `backend/scripts/load_test.py` | completado |
| Docs | `docs/adr/ADR-015-endurecimiento.md`, `docs/security/ASVS_L2.md`, guías, plan | completado |
| VERSION | 1.0.0rc1 en `pyproject.toml`, `uv.lock`, `app/__init__.py`, `package*.json`, `openapi.json`, `schema.d.ts`, `.env.example`, `.ai/product.md`, CHANGELOG | completado (sin commit) |

## Directrices para Futuras IAs
- **[escaneo]**: la fase OCR de doc_organize 1.0.0rc2 no atiende el `CancelToken` entre documentos. Un tramo o una
  cancelación pedidos durante el OCR esperan a que termine (G38/L-16). Las cuentas de `ConversionCounter` incluyen el
  OCR.
- **[escaneo]**: `ProgressEvent.processed` vuelve a 0 en cada fase y sube con `file_converted`/`ocr_processed`. Al
  empezar la fase OCR llega `(ocr, 0, total)`. Cortar ahí, con el límite ya pasado, crea un tramo vacío: solo se corta
  cuando sube `processed` y quedan documentos.
- **[worker]**: un subproceso que sale con `RECYCLE_EXIT` (75) **no cierra el run**. Antes de relanzarlo, el worker
  mira `cancel_requested`/`cancel_reason`. El `Slot` nuevo hereda `started`/`timeout_seen` (el timeout es por run, no
  por tramo).
- **[api]**: `scope["route"]` de FastAPI es la ruta del router incluido, sin prefijo. `route_template` reconstruye la
  plantilla completa probando la expresión de la ruta sobre los sufijos del `path`.
- **[api]**: FastAPI se traga cualquier excepción al leer el cuerpo y responde 400. Para limitar un cuerpo `chunked` no
  vale contar en `receive`: se exige `Content-Length` (411).
- **[e2e]**: todos los E2E usan el mismo admin, con un tope de 5 ejecuciones activas
  (`MAX_ACTIVE_RUNS_PER_USER`). Con los tramos de un documento del compose E2E, más de 3 *workers* de Playwright
  saturan la cola (`workers: 3`).
- **[e2e]**: el CPU de una construcción de imágenes en paralelo hace que el inicio de sesión (Argon2) pase de 5 s:
  falsos fallos en todos los E2E. No se lanzan E2E mientras se construye.
- **[deps]**: uv 0.13.1 acepta `exclude-newer = "2 weeks"` (en el lock queda `exclude-newer-span = "P2W"`). doc_organize
  llega por URL y no le afecta. npm 11.8 no tiene una opción relativa: `npm run safe`.
- **[docker]**: `libreoffice-calc-nogui` (bookworm) basta para `soffice --headless`. El grupo `av` añade Whisper,
  numba y ctranslate2, unos 2,6 GB de imagen.
- **[pruebas]**: para probar la GPU sin volver a descargar modelos, copiar el volumen `doc_organize_web_models` al de
  la pila aislada (`docker run … cp -a`) y hacer `chown 10001`.

## Veredicto final
Veredicto: **GO** para publicar 1.0.0rc1.

Pendientes al cierre:
- Commit, PR a `develop`, squash, *fast-forward* de `main` y tag `v1.0.0rc1`, con autorización del mantenedor.
- Pedir a doc_organize L-15 (1.0.0 final), fijarla en `uv.lock` (URL y hash) y publicar la web 1.0.0.
- Verificar la GPU, LibreOffice y AV en el servidor Linux al desplegar (`scripts/smoke_variants.py`).
- Desviación del PLAN: `restore` no limita la copia a una carpeta (no existe `DOW_BACKUP_DIR`). Lo garantiza el
  manifiesto: solo `config.db` y `projects/*/…/cache.db` dentro de `/data`, comprobados por hash.
- Desviación del PLAN: miembros y plantillas siguen sin paginar en el cliente (pocas filas, y la API ya pagina).
