# Runtime (contexto para IAs)

> Implementado en la Fase 0 (0.1.0): `web`, `worker` (perfil, sin operaciones), volúmenes `data`/`workspace` y los dos
> primeros secretos. El worker GPU, el volumen `models`, `dow_metrics_token` y las variantes llegan en fases
> posteriores. Imagen `runtime` CPU: 3,01 GB.

## Procesos

| Proceso | Comando | Puerto |
|---|---|---|
| API (`web`) | `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8080 --proxy-headers` | 8080 (publicado en 127.0.0.1) |
| Worker CPU | `python -m app.jobs.worker` con `DOW_WORKER_QUEUES=cpu` | — |
| Worker GPU | igual, imagen `runtime-gpu`, `DOW_WORKER_QUEUES=gpu` (perfil compose `gpu`) | — |
| Frontend dev | `npm run dev` (Vite, proxy `/api` → 127.0.0.1:8000) | 5173 |

`entrypoint.sh` ejecuta `alembic upgrade head` antes de cualquier proceso.

## Volúmenes, montajes y secretos

- `data` → `/data/config.db` y `/data/projects/<id>/cache.db` (SQLite WAL; copiar con `.backup`, nunca solo el `.db`).
- `workspace` → `/workspace/...` (carpetas por ejecución).
- `models` → `/models` (solo lectura; modelos de Docling, RapidOCR, EasyOCR, Whisper; `HF_HUB_OFFLINE=1`).
- Ubicaciones → *bind mounts* bajo `/mnt` (carpetas locales o montajes SMB/NFS del host Linux; `:ro` si la ubicación
  es de solo lectura).
- Docker secrets: `/run/secrets/dow_app_secret_key`, `/run/secrets/dow_fernet_keys`, `/run/secrets/dow_metrics_token`
  (leídos por pydantic-settings con prefijo `DOW_`).

## Variantes de imagen (D6)

| Variante | Añade |
|---|---|
| `runtime` (CPU, por defecto) | doc_organize con extras `rapidocr,ai,context,export,site`, `libmagic1`, modelos precargados |
| `WITH_LIBREOFFICE=true` | `soffice` para `.xls` legado |
| `WITH_AV=true` | extra `av`, `ffmpeg`, Whisper |
| `runtime-gpu` | base CUDA, extra `ocr-gpu` (torch, EasyOCR); requiere NVIDIA Container Toolkit en el host |

## Validación sin uv local

```bash
docker build -f docker/Dockerfile --target backend-dev -t doc_organize_web:backend-dev .
docker run --rm -v "$PWD/backend:/src/backend" -v "$PWD/openapi:/src/openapi" doc_organize_web:backend-dev uv run --frozen pytest
```
