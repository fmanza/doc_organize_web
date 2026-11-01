# doc_organize_web

Aplicación web multiusuario (FastAPI + React) sobre la librería
[doc_organize](https://github.com/fmanza/doc_organize): escaneo de carpetas de documentos locales o de red, conversión
a Markdown y JSON con Docling y OCR, duplicados y contexto navegable por dominios, con proyectos, miembros y
ejecuciones en segundo plano.

> **Estado: 0.5.0 — Fase 4 (escaneo y conversión).** Usuarios y sesiones, ubicaciones locales/red, ajustes
> administrables, proyectos con miembros, ejecuciones en segundo plano con progreso en vivo y escaneo incremental
> con OCR, GPU opcional y modelos sin Internet. Las
> funcionalidades llegan fase a fase según el [ROADMAP](docs/plan/ROADMAP.md); hasta alcanzar la
> [paridad](docs/plan/PARIDAD.md), la interfaz de doc_organize sigue siendo su web integrada.

## Arranque rápido

```bash
python3 scripts/generate_secrets.py
docker compose up -d --build
curl http://127.0.0.1:8080/api/health
docker compose exec web python -m app.cli create-admin --username <usuario>   # primer administrador
```

Después, abre http://127.0.0.1:8080 e inicia sesión.

Más en [docs/guides/despliegue.md](docs/guides/despliegue.md).

## Estructura

```text
backend/    FastAPI + SQLAlchemy 2 + Alembic (Python 3.12, uv); doc_organize solo en app/integrations/doc_organize/
frontend/   React 19 + TypeScript + Vite + Mantine; cliente generado desde openapi/openapi.json
docker/     Dockerfile multi-stage (runtime, backend-dev) y entrypoint
docs/       guías, ADRs y plan (sitio con Zensical: zensical.toml)
```

## Desarrollo

[docs/guides/desarrollo.md](docs/guides/desarrollo.md). Para contribuir:
[CONTRIBUTING.md](CONTRIBUTING.md). Seguridad: [SECURITY.md](SECURITY.md).

## Licencia

[MIT](LICENSE).
