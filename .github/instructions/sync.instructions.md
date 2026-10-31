---
applyTo: "CHANGELOG.md,backend/pyproject.toml,backend/app/__init__.py,frontend/package.json"
---
# Sincronización de versión

La versión de doc_organize_web vive en **cuatro** sitios y deben coincidir:

1. `CHANGELOG.md` — encabezado `## [X.Y.Z] - AAAA-MM-DD`
2. `backend/pyproject.toml` — `[project] version`
3. `backend/app/__init__.py` — `__version__`
4. `frontend/package.json` — `version` (y `package-lock.json`: `npm version X.Y.Z --no-git-tag-version`)

Y, derivados de esos, en el mismo commit de versión: la versión de `doc-organize-web` en `backend/uv.lock`
(`uv lock`), `info.version` de `openapi/openapi.json` (`scripts/export_openapi.py`) y `DOW_TAG` en `.env.example`.
Pasos completos: `docs/guides/publicar_version.md` (se crea en la Fase 0).

Política hasta 1.0: una MINOR por fase cerrada del ROADMAP (`0.<fase+1>.0`); PATCH para hotfix. Desde la 1.0.0,
SemVer: MINOR para funcionalidad compatible, MAJOR si rompe la API o exige intervención al actualizar.

La versión de doc_organize consumida se cambia solo en `backend/pyproject.toml` (dependencia y URL del wheel de la
release en `[tool.uv.sources]`) + `uv lock`, con nota en el CHANGELOG y en la columna «Requiere de doc_organize» del
ROADMAP (ADR-006). Mientras no haya wheel publicado (G9), se documenta el rodeo en `DOC_ORGANIZE_GAPS.md`.
