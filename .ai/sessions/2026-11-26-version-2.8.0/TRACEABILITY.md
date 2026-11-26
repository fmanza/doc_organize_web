# TRACEABILITY

## Session metadata
- id: 2026-11-26-version-2.8.0
- fecha: 2026-11-26
- rama: `refactor/quick-wins-2.7`, `refactor/tests-db-template`, `refactor/split-schemas-context`,
  `refactor/split-frontend-components`, `chore/deps-2.8` y `release/2.8.0` (todas desde `develop`)
- skill: tech_debt + refactor + version_closure
- fase: tech_debt (PLAN + AUDIT_PLAN + AUDIT_CODE, solo análisis) → refactor (PLAN + AUDIT_PLAN + IMPLEMENT +
  AUDIT_CODE, cuatro PRs) → VERSION

## Prompt issued
«Lanza /tech-debt» (todo el repositorio, solo análisis, se permite romper el contrato en una versión mayor) →
«Empieza por los quick wins de la 2.7.x» → «Empieza la 2.8» → «Lanza /version-closure para la 2.8.0».

## Context supplied
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`, skills `tech-debt`, `refactor` y `version-closure`.
- `docs/plan/DOC_ORGANIZE_GAPS.md`, `CHANGELOG.md`, `docs/guides/publicar_version.md`,
  `.github/instructions/sync.instructions.md`.
- Clon de solo lectura de doc_organize (tag v2.5.0) para reverificar firmas.

## AI output summary
- `/tech-debt`: veredicto `DEUDA_MENOR`; plan en tres versiones (2.7.x quick wins, 2.8 mantenimiento, 3.0 mayor).
- PR #131 (`refactor: quick wins de deuda técnica de la 2.7.x`): docs y configuración al día, `timeout-minutes` en
  el CI, ancla `x-worker-env` en compose, `PathFilter` único, `affected_rows`, alias de paginación, `ConfirmModal`,
  cabecera responsive, tests más rápidos. Revisión con `/ship` (solo revisión): 5 hallazgos, todos corregidos
  (decisiones con timeout y sin 500; errores dentro de los diálogos; sin párrafo vacío) con tests de regresión.
- `/refactor` 2.8: PLAN + AUDIT_PLAN con veredicto `GO_CONDICIONAL` (un PR por bloque, CI en verde entre PRs,
  `export_openapi --check` limpio salvo lo que venga de FastAPI, versiones con ≥ 14 días).
- PR #132: `config.db` plantilla por sesión y Argon2id barato solo en tests. Suite local 25 min 45 s → 17 min 26 s;
  job `backend` del CI 11 min → ~4,5 min.
- PR #133: `api/v1/schemas.py` → paquete (18 módulos + `__init__` que reexporta 180 esquemas) y `api/v1/context.py` →
  paquete (6 routers + `_shared`). Hecho con scripts `ast`; comparación de nombres antes/después sin diferencias.
- PR #134: seis componentes del frontend partidos (script con el compilador de TypeScript y `organizeImports`). El CI
  falló por `src/i18n/i18n.test.ts` (excepciones por ruta de fichero); corregido en el mismo PR.
- PR #135: FastAPI 0.162.5 y parches del backend; i18next 27.1.1 + react-i18next 18.0.1; acciones del CI por SHA.
  jsdom 31 aplazado. `openapi.json` cambia solo por FastAPI (`oneOf` + `discriminator` en `POST /projects/{id}/runs`).
- VERSION: versión 2.8.0 sincronizada (`pyproject.toml`, `app/__init__.py`, `package.json`/lock, `uv.lock`,
  `openapi.json`, `DOW_TAG`); `CHANGELOG.md` `[2.8.0]` con `Changed` y `Fixed`.
- Incidencia: borrar un worktree temporal con una junction a `frontend/node_modules` vació el `node_modules` real;
  restaurado con `npm ci`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Informe `/tech-debt` | conversación (no versionado) | emitido |
| PR quick wins | #131 · `54fe750` | fusionado |
| PR tests | #132 · `e5581e7` | fusionado |
| PR backend | #133 · `86d715b` | fusionado |
| PR frontend | #134 · `bca5a63` | fusionado |
| PR dependencias y CI | #135 · `c17383f` | fusionado |
| Release 2.8.0 | rama `release/2.8.0` | pendiente de PR |

## Directrices para Futuras IAs
- **[tests backend]**: `migrated` copia una `config.db` plantilla (`migrated_template`, sesión) y
  `_cheap_password_hashing` (autouse, sesión) sustituye `passwords._HASHER`; un test que necesite Alembic real debe
  usar `settings` + `run_migrations()`, no `migrated`.
- **[tests backend]**: el coste que queda por test es `create_app` (~0,25 s); reutilizar la app exige aislar su
  estado (métricas, rate limit).
- **[backend]**: `app.api.v1.schemas` es un paquete; añade esquemas al módulo del área y al `__init__` (import y
  `__all__`). FastAPI nombra los esquemas por la clase: dos clases con el mismo nombre en módulos distintos
  cambiarían `openapi.json`.
- **[backend]**: `app.api.v1.context` es un paquete con un router por subdominio, todos con `tags=["context"]`;
  `__init__` los incluye en orden. Lo común va en `context/_shared.py`.
- **[frontend]**: `src/i18n/i18n.test.ts` tiene `ALLOWED_LITERALS` con clave `fichero|literal`: al mover código de
  fichero, actualiza la ruta o fallará el CI. Ejecuta la suite completa de Vitest tras mover componentes.
- **[frontend]**: jsdom 31 evalúa media queries con un ancho interno fijo de 1024 px (`living/window/environment.js`)
  que no se cambia con `window.innerWidth`; con él, `hiddenFrom="sm"` oculta el menú móvil y falla
  `src/app/layout.test.tsx`. Por eso se quedó en jsdom 30.1.3.
- **[dependencias]**: `uv lock --upgrade-package` ya respeta `exclude-newer = "2 weeks"`; en npm usa `npm run safe`
  (añade `--before`) y revisa el lockfile por si hay bajadas.
- **[dependencias]**: el aviso de `npm audit` por `minimatch` (GHSA-g3hv-75wg-m249, vía ESLint/typescript-eslint, solo
  desarrollo) existía ya en `develop`; el arreglo (typescript-eslint 8.74.0) cumple los 14 días el 2026-12-07.
- **[api]**: FastAPI ≥ 0.162 genera `oneOf` + `discriminator` para las uniones discriminadas de Pydantic; los tipos
  de `openapi-typescript` no cambian.
- **[ci]**: las acciones de `.github/workflows/ci.yml` van fijadas por SHA con `# vX.Y.Z`; para subirlas, deja que
  Dependabot (`github-actions`, 14 días) actualice SHA y comentario a la vez.
- **[entorno Windows]**: no crees worktrees con junction a `node_modules`; ejecuta Vitest desde PowerShell con ruta
  `C:\`; no lances a la vez las suites de backend y frontend.

## Veredicto final
Veredicto: CLOSED (pendiente de publicar: PR de release, fast-forward de `main`, tag y release en GitHub)
Pendientes al cierre:
- jsdom 31 (decidir cómo probar vistas móviles).
- typescript-eslint 8.74 / `minimatch` desde el 2026-12-07 (Dependabot).
- `httpx2` para el `TestClient` (aviso de Starlette).
- Partir `update_user`; unificar versiones de uv/Node/Python entre CI y Dockerfile.
- 3.0.0: plan en curso (retirar compatibilidad heredada, tipar `run.result`, squash de Alembic).
