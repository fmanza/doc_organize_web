# syntax=docker/dockerfile:1
# doc_organize_web — imagen única para API (target "runtime") y worker (mismo target, otro comando).
# Build:  docker compose build            (o docker build -f docker/Dockerfile .)
# Variantes previstas (Fase 4, D6): runtime-gpu, WITH_LIBREOFFICE=true, WITH_AV=true.

ARG PYTHON_IMAGE=python:3.12.14-slim-bookworm
ARG NODE_IMAGE=node:24.21.0-alpine
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.1

FROM ${UV_IMAGE} AS uv

# ---------- 1. Frontend ----------
FROM ${NODE_IMAGE} AS frontend-build
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. Dependencias Python ----------
# torch y torchvision (vía docling) salen del índice CPU de PyTorch (backend/pyproject.toml).
FROM ${PYTHON_IMAGE} AS backend-build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# ---------- 2b. Herramientas de desarrollo (CI y equipos sin uv local) ----------
# docker build -f docker/Dockerfile --target backend-dev -t doc_organize_web:backend-dev .
# docker run --rm -v "$PWD/backend:/src/backend" -v "$PWD/openapi:/src/openapi" doc_organize_web:backend-dev uv run --frozen pytest
FROM backend-build AS backend-dev
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen
ENV PATH=/opt/venv/bin:$PATH
CMD ["uv", "run", "--frozen", "pytest"]

# ---------- 3. Runtime (CPU) ----------
# libmagic1: python-magic (doc_organize). libgl1 y libglib2.0-0: OpenCV, que llega con RapidOCR.
FROM ${PYTHON_IMAGE} AS runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends libmagic1 libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
 && mkdir -p /data /workspace /models /mnt \
 && chown app:app /data /workspace

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOW_ENVIRONMENT=production \
    DOW_DATA_DIR=/data \
    DOW_WORKSPACE_DIR=/workspace \
    DOW_LOCATIONS_ROOT=/mnt \
    DOW_MODELS_DIR=/models \
    DOW_STATIC_DIR=/app/static

WORKDIR /app
COPY --from=backend-build /opt/venv /opt/venv
COPY --chown=app:app backend/app ./app
COPY --chown=app:app backend/alembic ./alembic
COPY --chown=app:app backend/alembic.ini ./alembic.ini
COPY --chown=app:app --from=frontend-build /fe/dist ./static
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh

USER app
EXPOSE 8080
VOLUME ["/data", "/workspace"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import json,urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4); sys.exit(0 if json.load(r)['status']=='ok' else 1)"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-server-header"]
