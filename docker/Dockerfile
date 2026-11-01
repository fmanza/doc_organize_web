# syntax=docker/dockerfile:1
# doc_organize_web — imagen única para API (target "runtime") y worker (mismo target, otro comando).
# Build:  docker compose build            (o docker build -f docker/Dockerfile .)
# Variantes (D6): runtime (CPU, por defecto: es la última etapa) y runtime-gpu (CUDA 13.0, driver NVIDIA >= 580;
# Fase 4). Pendientes: WITH_LIBREOFFICE=true, WITH_AV=true.

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
# torch y torchvision (vía docling) salen del índice CPU de PyTorch: grupo `cpu`, por defecto (backend/pyproject.toml).
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

# ---------- 2c. Dependencias de la variante GPU ----------
# Grupo `gpu`: torch del índice CUDA 13.0 de PyTorch y doc_organize[ocr-gpu] (EasyOCR). Varios GB: fuera del CI.
FROM backend-build AS backend-build-gpu
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-group cpu --group gpu

# ---------- 3. Base común de runtime ----------
# libmagic1: python-magic (doc_organize). libgl1 y libglib2.0-0: OpenCV, que llega con RapidOCR (y EasyOCR en GPU).
# Modelos sin Internet (ADR-011): el worker no descarga nada (HF_HUB_OFFLINE=1); los modelos van al volumen /models
# con el servicio models-init (python -m app.integrations.doc_organize.models download), que sí tiene red.
FROM ${PYTHON_IMAGE} AS runtime-base
RUN apt-get update \
 && apt-get install -y --no-install-recommends libmagic1 libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
 && mkdir -p /data /workspace /models /mnt \
 && chown app:app /data /workspace /models

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOW_ENVIRONMENT=production \
    DOW_DATA_DIR=/data \
    DOW_WORKSPACE_DIR=/workspace \
    DOW_LOCATIONS_ROOT=/mnt \
    DOW_MODELS_DIR=/models \
    DOW_STATIC_DIR=/app/static \
    HF_HOME=/models/hf \
    HF_HUB_OFFLINE=1

WORKDIR /app
COPY --chown=app:app backend/app ./app
COPY --chown=app:app backend/alembic ./alembic
COPY --chown=app:app backend/alembic.ini ./alembic.ini
COPY --chown=app:app --from=frontend-build /fe/dist ./static
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh

USER app
EXPOSE 8080
VOLUME ["/data", "/workspace", "/models"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import json,urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4); sys.exit(0 if json.load(r)['status']=='ok' else 1)"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-server-header"]

# ---------- 4. Runtime GPU (worker de la cola gpu) ----------
# docker build -f docker/Dockerfile --target runtime-gpu -t doc_organize_web:gpu .   (compose: perfil `gpu`)
FROM runtime-base AS runtime-gpu
COPY --from=backend-build-gpu /opt/venv /opt/venv
# Escrituras de la variante GPU al tmpfs (/app, el HOME, es de solo lectura):
# - EasyOCR crea siempre `<MODULE_PATH>/user_network` (por defecto ~/.EasyOCR). Los modelos no van ahí: Docling le pasa
#   `DOCLING_ARTIFACTS_PATH/EasyOcr` con la descarga desactivada (ADR-011).
# - torch guarda los kernels CUDA compilados (por defecto ~/.cache/torch/kernels); sin caché los recompila cada job.
#   No crea esa carpeta: la crea entrypoint.sh.
ENV EASYOCR_MODULE_PATH=/tmp/easyocr \
    PYTORCH_KERNEL_CACHE_PATH=/tmp/torch-kernels

# ---------- 5. Runtime CPU (por defecto: última etapa) ----------
FROM runtime-base AS runtime
COPY --from=backend-build /opt/venv /opt/venv
