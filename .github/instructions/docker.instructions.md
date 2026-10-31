---
applyTo: "docker/**,docker-compose*.yml,.dockerignore"
---
# Docker — reglas

- Una imagen, varios procesos: `web` (uvicorn), `worker` (`python -m app.jobs.worker`, cola `cpu`) y, con el perfil
  `gpu`, `worker-gpu` (cola `gpu`). Comparten imagen, volúmenes y secretos.
- Etapas: `frontend-build` (Node, `npm ci`, `vite build`) → `backend-build` (uv, `uv sync --frozen --no-dev`) →
  `runtime` (CPU, por defecto). `runtime-gpu` parte de `nvidia/cuda:<ver>-runtime` con el extra `ocr-gpu`;
  `backend-dev` añade el grupo `dev` para CI y equipos sin uv.
- Variantes por `build-arg`: `WITH_LIBREOFFICE=true` (`libreoffice-calc-nogui`, `.xls` legado) y `WITH_AV=true`
  (extra `av`, `ffmpeg`, modelo Whisper). El tamaño de cada variante se mide y se anota en el CHANGELOG.
- Versiones exactas de `python`, `node`, `uv` y CUDA en los `ARG` del Dockerfile; al subirlas, versión con ≥ 2 semanas.
- Librerías nativas en `runtime`: `libmagic1` y lo que exija Docling (verificado, no supuesto).
- Modelos de Docling/RapidOCR/EasyOCR/Whisper precargados en `/models` durante el build (o volumen `models` de solo
  lectura); `HF_HUB_OFFLINE=1` y cachés de HF/torch apuntando a `/models` (ADR-011).
- Runtime: usuario `app` (uid 10001), `read_only`, `tmpfs /tmp`, `cap_drop: ALL`, `no-new-privileges`,
  `HEALTHCHECK` contra `/api/health`, `CMD` en forma exec, límites de memoria en compose.
- Volúmenes con nombre: `data` (`config.db`, `projects/*/cache.db`) y `workspace` (artefactos). **Nunca sobre
  NFS/CIFS**. Las ubicaciones (locales o montajes SMB/NFS del host) se pasan como *bind mount* bajo `/mnt`.
- `docker-compose.dev.yml` (Docker Desktop) usa solo carpetas locales como ubicaciones; las pruebas de red se hacen en
  el servidor Linux.
- Secretos solo como Docker secrets (`dow_app_secret_key`, `dow_fernet_keys`, `dow_metrics_token`), generados con
  `scripts/generate_secrets.py`; `secrets/` está git-ignored.
- `entrypoint.sh` aplica `alembic upgrade head` antes del proceso.
