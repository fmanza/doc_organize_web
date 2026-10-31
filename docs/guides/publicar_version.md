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

El commit de release (`release: vX.Y.Z - <resumen>`) llega a `develop` por PR como cualquier otro cambio, fusionado con
**squash**. Cuando el CI de ese commit en `develop` está en verde, `main` avanza por **fast-forward** hasta él: sin PR
de `develop` a `main`, sin commit de merge y sin volver a ejecutar la suite.

```bash
git switch develop && git pull
sha=$(git rev-parse HEAD)
gh run list --branch develop --commit "$sha" --workflow CI     # debe estar en «completed / success»
git push origin "$sha:main"                                    # fast-forward; el ruleset lo rechaza sin CI verde
git tag -a vX.Y.Z -m "vX.Y.Z" "$sha"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <notas extraídas del CHANGELOG>
```

Reglas de las ramas (rulesets del repositorio):

- **CI en verde** (`main` y `develop`, sin excepciones): checks `backend`, `frontend`, `docs` e `image` en el commit,
  rama al día, sin force-push ni borrado.
- **PR obligatorio en `develop`**, sin excepciones; solo se admite squash y la rama se borra al fusionar.
- **PR obligatorio en `main`**, con excepción solo para los administradores del repositorio, para el fast-forward.
  `main` nunca recibe un commit que no esté ya en `develop`.

## Cambiar la versión de doc_organize

Ver [ADR-006](../adr/ADR-006-integracion-doc-organize.md): versión en `dependencies` y URL del wheel en
`[tool.uv.sources]` de `backend/pyproject.toml`, `uv lock`, suite completa, nota en el CHANGELOG y en la columna
«Requiere» del ROADMAP.
