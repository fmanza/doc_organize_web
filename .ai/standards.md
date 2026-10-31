# Estándares

Fuente: `.github/SHARED_INSTRUCTIONS.md` y `.github/instructions/`. Resumen de umbrales:

| Ámbito | Herramienta | Umbral |
|---|---|---|
| Formato Python | `ruff format` | sin diferencias |
| Lint Python | `ruff check` (E, W, F, I, B, C4, UP, S, ASYNC) | 0 errores |
| Tipos Python | `mypy` estricto | 0 errores |
| Tests backend | `pytest` | verde; endpoints con 401/403/404/422 cubiertos; rutas con escape y enlace simbólico |
| Arquitectura | `tests/unit/test_architecture.py` | solo la ACL importa doc_organize |
| Migraciones | test `upgrade`/`downgrade` de Alembic | verde |
| Formato TS | `prettier --check` | sin diferencias |
| Lint TS | `eslint` (typescript-eslint strict, react-hooks) | 0 errores, 0 avisos nuevos |
| Tipos TS | `tsc -b --noEmit` (strict, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`) | 0 errores |
| Tests frontend | Vitest | verde |
| Contrato | `export_openapi.py --check` + `gen:api` sin diff | al día |
| Documentación | `zensical build --strict` | sin avisos |
| Imagen | `docker compose build` + `/api/health` | 200 `ok` |
| Accesibilidad | WCAG 2.2 AA | revisado por Frontend Reviewer |

Estilo: español en textos de usuario, docstrings y documentación; identificadores de código en inglés.
