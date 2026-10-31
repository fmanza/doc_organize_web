# PLAN + AUDIT_PLAN — Fase 0 (Fundaciones → 0.1.0)

## PLAN

### Tareas y DoD

| Tarea | Entregable |
|---|---|
| WB-0.1 | `backend/` con `app/{core,db,api,domain,integrations/doc_organize,jobs,workspace}`, `pyproject.toml` (uv, `package = false`, Python `>=3.12,<3.13`, `exclude-newer = 2026-10-17`), `uv.lock` |
| WB-0.2 | `core/config.py` (`Settings` con prefijo `DOW_`, `secrets_dir=/run/secrets`; secretos obligatorios en `production`), `core/logging.py` (JSON + `request_id` por middleware y cabecera `X-Request-ID`), `core/errors.py` (RFC 9457 para `HTTPException`, validación y 500 genérico), cabeceras de seguridad |
| WB-0.3 | `db/engine.py` (PRAGMA `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`, `foreign_keys=ON` en el *listener*), `db/base.py`, Alembic con `render_as_batch` y revisión `0001` vacía |
| WB-0.4 | `GET /api/health` → `{status, version, doc_organize, database}` (503 si la BD falla); SPA servida en `/` con *fallback* a `index.html`; `/api/*` desconocido → 404 problem+json; `/api/docs` solo en `development` |
| WB-0.5 | `integrations/doc_organize/version.py` (`importlib.metadata.version("doc_organize")`, G1) + `tests/unit/test_architecture.py` (AST: solo la ACL importa `doc_organize`; `domain/` sin FastAPI) |
| WB-0.6 | `scripts/export_openapi.py [--check]` → `openapi/openapi.json` |
| — | `app/cli.py` vacío de comandos de negocio (llegan en F1) y `app/jobs/worker.py` mínimo (arranca, registra «sin operaciones hasta la Fase 3» y termina limpio con SIGTERM) |
| WF-0.1 | Vite 8 + React 19 + TS 5.9 estricto, Mantine 9 (claro/oscuro), React Router 8, TanStack Query 5, i18next `es` (`core.json`, `features.json`) |
| WF-0.2 | `src/api/client.ts` (`openapi-fetch`) + `schema.d.ts` generado; `Layout` con navegación por fases (entradas futuras deshabilitadas), página de salud, 404 |
| WF-0.3 | ESLint (typescript-eslint strict + react-hooks), Prettier, Vitest + Testing Library (`src/test/render.tsx`), Playwright con E2E de humo (salud) |
| WD-0.1 | `docker/Dockerfile` (`uv` → `frontend-build` → `backend-build` → `backend-dev` / `runtime`), `entrypoint.sh` (`alembic upgrade head`), `docker-compose.yml` (`web`; `worker` con perfil `worker`), secretos, endurecimiento, healthcheck; `scripts/generate_secrets.py`; `.dockerignore`, `.env.example` |
| WD-0.2 | CI: `backend`, `frontend`, `docs` (`zensical build --strict`, sustituye a `check_doc_links.py`), `image` (build + `/api/health` 200); Dependabot ampliado a `uv`, `npm`, `docker` con *cooldown* 14 días |
| WD-0.3 | (IA ya hecha en `bf7664a`) ADR-001…006 en `docs/adr/`; `zensical.toml`; `docs/README.md`; `docs/plan/PARIDAD.md` (L-0: 56 endpoints, 4 WebSocket, 20 plantillas → fase); `DOC_ORGANIZE_GAPS.md` con G14 |
| WD-0.4 | Resto del repo público: `LICENSE` (MIT), `CONTRIBUTING.md`, plantillas de issue, `.gitattributes` (`eol=lf`), `.editorconfig`; checks `backend`/`frontend`/`image`/`docs` como obligatorios en `main`/`develop` (cambio de configuración en GitHub: se pide confirmación antes) |
| WD-0.5 | `docker-compose.dev.yml` con `./dev-data/locations/{origen,destino}` montadas en `/mnt` (git-ignored) |
| Docs | `README.md`, `CHANGELOG.md` (0.1.0), `docs/guides/desarrollo.md`, `docs/guides/despliegue.md`, `docs/guides/publicar_version.md` |

DoD de la fase: comandos de desarrollo en verde, OpenAPI exportado y cliente generado, migración `0001` con
`downgrade`, imagen construida y `/api/health` 200, CHANGELOG, guías, TRACEABILITY. Los tests 401/403/IDOR y la fila de
PARIDAD «marcada» no aplican en F0 (sin recursos protegidos ni pantallas de paridad); PARIDAD se crea.

### Contrato HTTP

| Método | Ruta | Respuesta |
|---|---|---|
| GET | `/api/health` | 200 `HealthOut {status: "ok", version, doc_organize, database: "ok"}`; 503 problem+json si la BD no responde |
| GET | `/api/v1/...` | (vacío en F0; el router v1 existe) |
| GET | `/api/<desconocido>` | 404 `application/problem+json` |
| GET | `/*` | `index.html` de la SPA (o 404 si no hay build en desarrollo) |

### Modelo de datos

`config.db` sin tablas de negocio: Alembic `0001_inicial` vacía (`upgrade`/`downgrade` no-op) para fijar la cadena.
Test de migración `upgrade head` → `downgrade base` en CI.

### doc_organize (verificado en el clon local, 2026-10-31)

- Último tag `v0.9.2` (2026-09-17), pero `pyproject.toml` dice `version = "0.9.0"` y `__init__.__version__ = "0.1.0"`;
  el wheel de `dist/` es `doc_organize-0.9.0` del 2026-09-11. GitHub Releases solo tiene hasta `v0.7.0` (sin wheel de
  0.9.x) → **G9 confirmado** y **G14 nuevo** (tag ≠ versión del paquete).
- Propuesta: construir el wheel desde el tag `v0.9.2` (`uv build --wheel`), vendorizarlo en
  `backend/vendor/doc_organize-0.9.0-py3-none-any.whl` (MIT, repo público sin problema), fuente
  `[tool.uv.sources] doc_organize = { path = "vendor/…whl" }`, hash en `uv.lock`; nota en ADR-006 y CHANGELOG.
- Extras: `doc_organize[ai,context]`. Los extras `export` y `site` de `DEPENDENCIAS.md` **no existen en 0.9.x**
  (llegan con L-7/L-8); `rapidocr` ya llega por `docling[rapidocr]` en las dependencias base.
- F0 solo usa `importlib.metadata.version("doc_organize")`; ninguna otra firma.

### Pantallas

`Layout` (cabecera, navegación por fases, tema), `HealthPage` (sustituye al semáforo de `base.html.j2` solo para la
salud), `NotFoundPage`. Sin login (F1).

### Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| K1 | **torch**: `docling` → `docling-slim[standard]` exige `torch>=2.2.2` y `torchvision`. En Linux, el torch de PyPI arrastra las librerías CUDA (varios GB) | Índice `pytorch-cpu` (`https://download.pytorch.org/whl/cpu`, `explicit = true`) para `torch`/`torchvision` en `[tool.uv.sources]`; la variante GPU (F4) tendrá su propia resolución |
| K2 | `exclude-newer` con el índice de PyTorch (puede no publicar fecha de subida) | PENDIENTE DE VERIFICAR al hacer `uv lock`; si falla, `exclude-newer-package` para torch/torchvision justificado |
| K3 | Tamaño de la imagen `runtime` (torch CPU + docling + pandas) | Medir y anotar (estimación 2–3 GB; PENDIENTE DE MEDIR); modelos **no** precargados en F0 (ADR-011 en F4) |
| K4 | CI lento por instalar torch/docling en `backend` | Caché de uv en Actions; los tests no importan docling |
| K5 | G14: versión del paquete 0.9.0 en un wheel construido desde `v0.9.2` | `/api/health` muestra la versión de metadatos; documentado en GAPS |
| K6 | SPA y API en el mismo proceso: rutas `/api/*` capturadas por el *fallback* | El *fallback* excluye `/api` y `/metrics`; test |
| K7 | Fin de línea CRLF en Windows (avisos en el commit de IA) | `.gitattributes` con `* text=auto eol=lf` |
| K8 | Secretos en producción ausentes | `Settings` falla al arrancar en `production` sin `dow_app_secret_key`/`dow_fernet_keys`; `generate_secrets.py` |

### Estrategia de pruebas

- Backend `unit`: ajustes (entorno, fichero de secreto, error sin secreto en producción), logging JSON con
  `request_id`, PRAGMA del engine, arquitectura, versión de doc_organize. `api`: salud 200/503, problem+json en 404 y
  422, cabeceras de seguridad, `X-Request-ID`, SPA *fallback* sin capturar `/api`. Migraciones up/down.
- Frontend: Vitest de `HealthPage` (carga, ok, error) y `NotFoundPage`; Playwright de humo contra compose.
- Imagen: `docker compose up` + `curl /api/health` en CI.

## AUDIT_PLAN

- **Arquitectura y reglas no negociables**: niveles de `.ai/architecture.md` respetados; ACL con test desde el
  primer commit; sin rutas de usuario ni operaciones pesadas en F0; secretos solo por Docker secrets.
- **ADRs**: 001 (stack), 002 (jobs, colas cpu/gpu), 003 (auth), 004 (secretos), 005 (zonas de datos), 006
  (integración + wheel vendorizado temporal) se redactan como «Aceptado» desde `ADRS_PROPUESTOS.md`.
- **Huecos nuevos**: G14 (tag `v0.9.2` frente a `version = "0.9.0"`); G9 confirmado (Releases solo hasta v0.7.0).
- **Paridad**: F0 no cubre filas; crea `PARIDAD.md` con el inventario (revisión del usuario pendiente, como pide L-0).
- **Simplificaciones**: `app.cli` y `jobs/worker` mínimos; sin `/metrics` (F10); sin modelos precargados (F4).
- **Fuera de alcance**: variantes GPU/LibreOffice/AV, CodeQL (ya activo), publicación en GHCR.

**Veredicto: `GO_CONDICIONAL`**

Condiciones:

1. Aprobar el wheel construido desde `v0.9.2` y vendorizado en `backend/vendor/` (alternativa: publicar antes una
   release `v0.9.3` de doc_organize con wheel y versión coherente — cerraría G9 y G14 en el origen).
2. Aprobar torch/torchvision desde el índice CPU de PyTorch.
3. Rama de trabajo: `feature/fase-0` creada desde `chore/config-ia` (o fusionar antes `chore/config-ia` en `develop`
   por PR).
4. Autorizar al final el cambio de protección de ramas en GitHub (checks obligatorios) o dejarlo para que lo haga el
   mantenedor.

## Resolución de condiciones (mantenedor, 2026-10-31)

1. Wheel: se publica antes **doc_organize v0.9.3** con wheel y sdist en GitHub Releases (cierra G9 y G14 en origen);
   se fija por URL + hash como util_bbdd_web, sin vendorizar.
2. torch/torchvision desde el índice CPU de PyTorch: aprobado.
3. `chore/config-ia` fusionada en `develop` por PR #4; la fase se trabaja en `feature/fase-0`.
4. La protección de ramas (checks obligatorios) la aplica Claude al terminar.

Veredicto tras condiciones: **GO** — IMPLEMENT autorizado.
