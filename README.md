# doc_organize_web

Aplicación web multiusuario (FastAPI + React) sobre la librería
[doc_organize](https://github.com/fmanza/doc_organize): escaneo de carpetas de documentos locales o de red, conversión
a Markdown y JSON con Docling y OCR, duplicados y contexto navegable por dominios, con proyectos, miembros y
ejecuciones en segundo plano.

Con doc_organize 2.2: contexto por **ejes** de taxonomía en pasos de trabajo (plantillas y manifiesto del proyecto,
con perfil), IA por funcionalidad a través de un LiteLLM Proxy (clasificar con cita, describir, embeddings para la
clasificación semántica y los duplicados por contenido, y agentes para diseñar la taxonomía y revisar la
clasificación) con su consumo por ejecución, decisiones de personas, versiones de un documento, calidad contra una
referencia, y entregas del contexto (Excel, sitio sin conexión y paquete para IA, con su SHA-256). Multiusuario con
tenants, roles, auditoría y tema claro u oscuro por usuario. La documentación está en [docs/](docs/README.md) (se publica con
Zensical).

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
docker/     Dockerfile multi-stage (runtime, runtime-gpu, backend-dev) y entrypoint
docs/       guías, ADRs y plan (sitio con Zensical: zensical.toml)
```

## Desarrollo

[docs/guides/desarrollo.md](docs/guides/desarrollo.md). Para contribuir:
[CONTRIBUTING.md](CONTRIBUTING.md). Seguridad: [SECURITY.md](SECURITY.md).

## Licencia

[MIT](LICENSE).
