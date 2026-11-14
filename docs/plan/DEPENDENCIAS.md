# Librerías y dependencias

Política (≈ util_bbdd_web): `uv.lock` con `exclude-newer` (≥ 2 semanas, excepciones justificadas en
`pyproject.toml`), npm con versiones exactas e instalación `--before=<fecha>`, imágenes base con versión exacta.
La regla de ≥ 2 semanas estuvo suspendida del 2026-11-01 a la Fase 10, que la reactiva (2026-11-05):
`exclude-newer = "2 weeks"`, `npm run safe` (`--before`) y `cooldown` de 14 días en Dependabot. Grupo nuevo `av`
(`doc_organize[av]`: Whisper y sus dependencias), solo en la imagen con `WITH_AV=true`.
Las versiones concretas se fijan en la Fase 0 a partir de las de util_bbdd_web 1.10.1 para no divergir.

**Exenciones permanentes (desde 2026-11-14, decisión del mantenedor)**: `zensical`, `zensical-ui` y `soupsieve`
están exentos de la regla de 2 semanas (`exclude-newer-package = { … = false }`): reciben cualquier versión nueva sin
espera, y el resto de dependencias sigue con la regla. Sustituyen a las excepciones con fecha tope de abajo, que
había que retirar el 2026-11-19 y el 2026-11-24. Riesgo aceptado: una versión comprometida recién publicada de esos
tres paquetes entraría en el siguiente `uv lock`; el lock sigue con hash y cada subida pasa por PR y CI.

**Excepción (1.4.6, 2026-11-14; sustituida por la exención)**: `zensical` 0.1.1 y `zensical-ui` 0.0.42 (publicados el
2026-11-10), con fecha tope fija `2026-11-11` en `exclude-newer-package`. doc_organize 1.4.0 exige `zensical>=0.1.1`:
con 0.0.71–0.0.74 el índice de búsqueda limitaba cada sección por bytes y el sitio de contexto de un proyecto real no
se construía.

**Excepción de seguridad (1.4.7, 2026-11-14; sustituida por la exención)**: `soupsieve` 4.0.1 (publicada el
2026-11-04), con fecha tope fija `2026-11-05`. Corrige GHSA-mmhr-3c5m-f64f (alta, tiempo polinómico en el combinador descendiente) y otros casos
cuadráticos; llega a la imagen con docling vía `beautifulsoup4`, que la usa con el HTML de los documentos de origen.
Es MAJOR (3 → 4: no entra en `<template>`, `iframe` como elementos normales); una conversión HTML con docling da el
mismo Markdown con 3.0.3 y con 4.0.1. En la misma versión,
`opentelemetry-api` 1.45.2 (GHSA-mf5v-w3w3-f6cg, media) entra sin excepción. La alerta de `minimatch` (solo
herramientas de desarrollo del frontend, no llega a la imagen) se descarta como riesgo tolerable hasta que eslint y
typescript-eslint la suban dentro de la regla.

## Backend (`backend/pyproject.toml`)

| Paquete | Para qué | Fase |
|---|---|---|
| `fastapi`, `uvicorn[standard]` | API y servidor ASGI; SSE nativo (`EventSourceResponse`) | 0 |
| `pydantic>=2`, `pydantic-settings` | Contratos HTTP y ajustes `DOW_*` + secretos | 0 |
| `sqlalchemy>=2.1`, `alembic` | `config.db` portable a otra BD | 0 |
| `doc_organize[rapidocr,ai,context,export,site]==X.Y.Z` | Librería fijada por URL del wheel + hash (ADR-006) | 0 |
| `pwdlib[argon2]` | Contraseñas | 1 |
| `cryptography` | MultiFernet para las credenciales IA de `ai_settings` (dependencia directa desde la 0.9.0) | 8 |
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
