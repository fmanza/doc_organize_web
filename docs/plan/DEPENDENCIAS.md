# Librerías y dependencias

Política (≈ util_bbdd_web): `uv.lock` con `exclude-newer` (≥ 2 semanas, excepciones justificadas en
`pyproject.toml`), npm con versiones exactas e instalación `--before=<fecha>`, imágenes base con versión exacta.
La regla de ≥ 2 semanas está **suspendida hasta la 1.0** (2026-11-01); la Fase 10 la reactiva.
Las versiones concretas se fijan en la Fase 0 a partir de las de util_bbdd_web 1.10.1 para no divergir.

## Backend (`backend/pyproject.toml`)

| Paquete | Para qué | Fase |
|---|---|---|
| `fastapi`, `uvicorn[standard]` | API y servidor ASGI; SSE nativo (`EventSourceResponse`) | 0 |
| `pydantic>=2`, `pydantic-settings` | Contratos HTTP y ajustes `DOW_*` + secretos | 0 |
| `sqlalchemy>=2.1`, `alembic` | `config.db` portable a otra BD | 0 |
| `doc_organize[rapidocr,ai,context,export,site]==X.Y.Z` | Librería fijada por URL del wheel + hash (ADR-006) | 0 |
| `pwdlib[argon2]` | Contraseñas | 1 |
| `cryptography` | Fernet para credenciales IA | 1/8 |
| `prometheus-client` | `/metrics` | 10 |
| `httpx` | Llega con `doc_organize[ai]`; también tests | 8 |
| `openpyxl` | Llega con `doc_organize[export]` | 5 |
| `pyyaml` | Llega con `doc_organize[context]` | 7 |
| `zensical` | Llega con `doc_organize[site]` (sitio de contexto, L-8). **Sin mkdocs** en ninguna imagen | 7 |
| `python-magic` + `libmagic1` (sistema) | Detección de tipo, ya en doc_organize | 4 |
| Opcional `ocr-gpu`: `torch`, `torchvision`, `opencv-python-headless`, `easyocr` | Variante GPU | 4 |
| Opcional `av`: `docling[asr]` | Variante audio/vídeo | 4 |
| dev: `pytest`, `pytest-cov`, `pytest-asyncio`, `httpx`, `ruff`, `mypy` | Calidad | 0 |
| docs: `zensical` | Sitio de documentación (como util_bbdd_web) | 0 |

Nota: `python-multipart` solo si se aprueba la subida de documentos desde el navegador (mejora opcional).

## Frontend (`frontend/package.json`)

| Paquete | Para qué | Fase |
|---|---|---|
| `react`, `react-dom` 19, `react-router` | SPA y rutas | 0 |
| `@tanstack/react-query` | Datos de servidor | 0 |
| `@mantine/core`, `@mantine/hooks` | UI, tema claro/oscuro | 0 |
| `@mantine/notifications`, `@mantine/dropzone` (si hay subida) | Avisos de fin de run; subida | 3 / opc. |
| `openapi-fetch` + `openapi-typescript` (dev) | Cliente tipado desde OpenAPI | 0 |
| `react-hook-form`, `zod` | Formularios (ubicaciones, escaneo, ajustes IA) | 1 |
| `i18next`, `react-i18next` | Textos en español | 0 |
| `@tanstack/react-virtual` | Tablas de caché y duplicados con miles de filas | 5 |
| `marked` + `dompurify` | Visor Markdown **saneado** de documentos convertidos | 5 |
| `highlight.js` | JSON / YAML del manifiesto | 5/7 |
| `diff` | Comparar duplicados difusos lado a lado | 6 |
| dev: `typescript` 5.9, `vite`, `@vitejs/plugin-react`, `eslint` + `typescript-eslint` + plugins React, `prettier`, `vitest`, `jsdom`, `@testing-library/*`, `@playwright/test` | Calidad | 0 |

## Sistema (Dockerfile)

| Paquete | Imagen | Para qué |
|---|---|---|
| `python:3.12-slim-<distro>` (versión exacta) | runtime | Base |
| `libmagic1` | runtime | `python-magic` |
| `libgl1`, `libglib2.0-0` | runtime | OpenCV/Docling (PENDIENTE DE VERIFICAR con `-headless`) |
| `sqlite3` CLI | runtime | `backup`/`restore` |
| `cifs-utils` / `nfs-common` | **host**, no imagen | Los montajes se hacen fuera del contenedor (ADR-007) |
| `libreoffice-calc-nogui` | `WITH_LIBREOFFICE` | `.xls` legado |
| `ffmpeg` | `WITH_AV` | Audio/vídeo |
| `nvidia/cuda:<ver>-cudnn-runtime` | `runtime-gpu` | OCR en GPU; host con NVIDIA Container Toolkit |
| `node:24-<distro>` | `frontend-build` | Build de la SPA |
