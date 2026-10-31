# Publicar una versión

Hasta la 1.0.0, una MINOR por fase cerrada del ROADMAP (`0.<fase+1>.0`) y PATCH para hotfix.

## 1. Sincronizar la versión

La versión vive en cuatro sitios que deben coincidir:

1. `CHANGELOG.md`: encabezado `## [X.Y.Z] - AAAA-MM-DD`.
2. `backend/pyproject.toml`: `[project] version`.
3. `backend/app/__init__.py`: `__version__`.
4. `frontend/package.json` y `package-lock.json`: `npm version X.Y.Z --no-git-tag-version` desde `frontend/`.

Y, derivados, en el mismo commit:

```bash
cd backend
uv lock                                             # versión de doc-organize-web en uv.lock
uv run --frozen python scripts/export_openapi.py    # info.version de openapi/openapi.json
cd ../frontend && npm run gen:api
```

Además, `DOW_TAG` en `.env.example`.

## 2. Validar

Todos los comandos de «Comandos de desarrollo» de
[SHARED_INSTRUCTIONS](https://github.com/fmanza/doc_organize_web/blob/develop/.github/SHARED_INSTRUCTIONS.md), la imagen
(`docker compose build`, `/api/health` 200) y `zensical build --strict`.

## 3. Publicar

```bash
git switch develop && git pull
# PR develop → main con el título "release: vX.Y.Z - <resumen>"; tras fusionarlo:
git switch main && git pull
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <notas extraídas del CHANGELOG>
```

## Cambiar la versión de doc_organize

Ver [ADR-006](../adr/ADR-006-integracion-doc-organize.md): versión en `dependencies` y URL del wheel en
`[tool.uv.sources]` de `backend/pyproject.toml`, `uv lock`, suite completa, nota en el CHANGELOG y en la columna
«Requiere» del ROADMAP.
