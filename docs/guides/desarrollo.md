# Entorno de desarrollo

## Requisitos

- [uv](https://docs.astral.sh/uv/) 0.13.1 o superior (descarga Python 3.12 si hace falta).
- Node.js 24.15 o superior (la imagen y el CI usan 24.21.0) con npm 11.
- Docker (Docker Desktop en Windows) para la imagen y los E2E.

Sin uv local, la imagen `backend-dev` contiene las mismas herramientas que el CI:

```bash
docker build -f docker/Dockerfile --target backend-dev -t doc_organize_web:backend-dev .
docker run --rm -v "$PWD/backend:/src/backend" -v "$PWD/openapi:/src/openapi" doc_organize_web:backend-dev uv run --frozen pytest
```

## Backend

Desde `backend/`:

```bash
uv sync --frozen                                   # instala doc_organize, Docling y torch (CPU): tarda la primera vez
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen pytest
uv run --frozen python scripts/export_openapi.py   # tras cambiar la API: actualiza openapi/openapi.json
```

Para levantar la API en local (puerto 8000, el que usa el proxy de Vite):

```bash
DOW_ENVIRONMENT=development DOW_DATA_DIR=../build/dev/data DOW_WORKSPACE_DIR=../build/dev/workspace \
  uv run --frozen uvicorn app.main:create_app --factory --reload --port 8000
```

`DOW_ENVIRONMENT` vale `production` por defecto: así la aplicación nunca arranca en producción sin secretos por
descuido. En `development` se habilita `/api/docs`.

## Frontend

Desde `frontend/`:

```bash
npm ci
npm run dev            # http://127.0.0.1:5173, con /api hacia 127.0.0.1:8000
npm run format:check
npm run lint
npm run typecheck
npm test
npm run gen:api        # tras exportar openapi/openapi.json
npm run build
```

Las dependencias nuevas se instalan con versión exacta: `npm install <paquete>@<versión>`. La fecha de corte
(`--before=<fecha>`, versiones con ≥ 2 semanas) está suspendida hasta la 1.0.

## Con Docker Desktop

`docker-compose.dev.yml` levanta la API con recarga sobre el código montado y monta dos ubicaciones de prueba
(`dev-data/locations/origen` en solo lectura y `dev-data/locations/destino`), que se usarán desde la Fase 2. Pon ahí
solo documentos sintéticos.

```bash
python scripts/generate_secrets.py
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build web
```

## Documentación

Sitio con [Zensical](https://zensical.org) (`zensical.toml`):

```bash
uv run --frozen --project backend --only-group docs zensical serve            # http://127.0.0.1:8000
uv run --frozen --project backend --only-group docs zensical build --strict   # lo que comprueba el CI
```

## E2E

Con la aplicación levantada (`docker compose up`), desde `frontend/`:

```bash
npx playwright install chromium   # la primera vez
DOW_E2E_URL=http://127.0.0.1:8080 npm run e2e
```
