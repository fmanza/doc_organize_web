# TRACEABILITY

## Session metadata
- id: 2026-11-27-version-3.0.0
- fecha: 2026-11-26 / 2026-11-27
- rama: `docs/plan-3.0`, `refactor/prepare-3.0`, `refactor/alembic-squash`, `feat/remove-legacy-3.0`,
  `refactor/typed-run-results`, `feat/typed-run-contract`, `test/jsdom-31` y `release/3.0.0` (todas desde `develop`)
- skill: new_feature/refactor (plan 3.0) + version_closure
- fase: PLAN + AUDIT_PLAN (`GO_CONDICIONAL`) → IMPLEMENT + AUDIT_CODE (seis PRs) → VERSION

## Prompt issued
«Lanza /version-closure para la 2.8.0 y planifica paralelamente 3.0» → «No pidas confirmación hazlo» → «Haz httpx2,
pregunta lo que necesites» (todo hasta fusionar; encadenar los PRs sin parar) → «continua» → `/version-closure` 3.0.0.

## Context supplied
- `.github/SHARED_INSTRUCTIONS.md`, skills `new-feature`, `refactor` y `version-closure`.
- Informe `/tech-debt` de la 2.7.0 y sesión `2026-11-26-version-2.8.0`.
- Clon de solo lectura de doc_organize y wheel 2.5.0 instalado (campos de los informes de evaluación, reglas y auditor).

## AI output summary
- Plan de la 3.0 (agente Plan, solo lectura) → `docs/plan/VERSION_3.0.md` (PR #137). Python 3.13 y TypeScript 7
  fuera: `uv.lock` sin ruedas `cp313`; typescript-eslint 8.72 pide `typescript <6.1.0`.
- PR #140: `update_user` en pasos (156 → 37 líneas); `tests/fixtures/schema_0033.sql` + test; `httpx2` 2.16.0 en
  `dev` (aprobado expresamente por el usuario; el clasificador bloqueó el primer intento).
- PR #141: línea base `0033_baseline.py` (26 tablas, 29 índices, semilla), puerta de versión
  `app/db/migrations.py`, ADR-018, guía de despliegue.
- PR #142 (agente + revisión): retirada de `deleted_projects`, `collision`/`collisions_count`, G23, `legacy_variables`,
  `legacy_format`, `markdown_v1`; migración `3001`.
- PR #143 (agente + revisión): `domain/runs/results.py`, `RunResult.stored()`, `parse_result`. El CI falló por un
  `.stored().stored()` en un test `posix_paths` (se omite en Windows); corregido en el mismo PR.
- PR #144 (agente + revisión): `RunOut` unión discriminada de 21 `<Op>RunOut`; `QualityEvaluationOut`,
  `QualityDryRunOut`, `QualityAuditOut`; frontend sin casts.
- PR #145: el agente se cortó por el límite de uso; terminado a mano: jsdom 31.0.0, `e2e/mobile-menu.spec.ts`,
  `layout.test.tsx` por `aria-controls`.
- VERSION: 3.0.0 sincronizada (`pyproject.toml`, `app/__init__.py`, `package.json`/lock, `uv.lock`, `openapi.json`,
  `DOW_TAG`); CHANGELOG `[3.0.0]` con aviso de actualización; plan marcado como ejecutado.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Plan 3.0 | `docs/plan/VERSION_3.0.md` (#137) | fusionado |
| PR 0 | #140 · `dfcb3ca` | fusionado |
| PR 1 | #141 · `ff4b6be` | fusionado |
| PR 2 | #142 · `4776e9d` | fusionado |
| PR 3a | #143 · `92ee053` | fusionado |
| PR 3b | #144 · `c8079a9` | fusionado |
| PR 4 | #145 · `dfc42a7` | fusionado |
| Release 3.0.0 | rama `release/3.0.0` | pendiente de PR |

## Directrices para Futuras IAs
- **[migraciones]**: la cadena empieza en `0033_baseline.py` (revisión `0033`, sin padre). Las migraciones nuevas van
  desde `3001` en adelante. `app/db/migrations.py::check_revision_is_known` rechaza BD anteriores a la 2.7; en
  `alembic/env.py` hay que cerrar la transacción tras la comprobación (`connection.rollback()`) o el
  `PRAGMA foreign_keys=OFF` no se aplica.
- **[migraciones]**: `tests/fixtures/schema_0033.sql` describe `0033` y no se regenera con migraciones nuevas
  (`test_0033_matches_the_schema_snapshot` sube solo a `0033`). Alembic *batch* emite las restricciones de tabla en un
  orden que depende de `PYTHONHASHSEED`: `tests/schema_snapshot.py` las ordena.
- **[migraciones]**: en las semillas no pases `datetime` crudos a `sa.text` (adaptador de sqlite3 obsoleto en 3.12):
  formatea como `sa.DateTime` (`%Y-%m-%d %H:%M:%S.%f`).
- **[ejecuciones]**: cada operación devuelve un `*Result` de `app/domain/runs/results.py` y el runner guarda
  `RunResult.stored()` (`exclude_unset=True`, conserva las claves escritas con `None`). Para leer, `parse_result` /
  `parse_result_as` (aviso con el id del run y `None` si no valida). No hay `TypeDecorator`: la forma depende de la
  columna `operation`.
- **[api]**: `RunOut` es un `RootModel` con `oneOf` de `<Op>RunOut` discriminado por `operation`; `params` pasa antes
  por `public_params`. Un resultado o unos params inválidos nunca dan 500.
- **[tests backend]**: los tests `@pytest.mark.posix_paths` se omiten en Windows y solo corren en el CI (Linux):
  revisa a mano los que toques.
- **[frontend tests]**: con jsdom 31 un elemento con `display: none` (p. ej. `hiddenFrom`) no tiene nombre accesible,
  ni con `aria-label`; búscalo por atributo y deja la visibilidad a Playwright (`e2e/mobile-menu.spec.ts`).
- **[dependencias]**: añadir una dependencia nueva requiere la aprobación expresa del usuario (el clasificador del
  modo automático lo bloquea sin ella).
- **[proceso]**: para mover trabajo sin commit a una rama nueva desde `develop` tras un squash, comprueba
  `git diff --quiet HEAD origin/develop` y usa `git stash -u` + `git switch -c <rama> origin/develop` + `git stash pop`.

## Veredicto final
Veredicto: CLOSED (pendiente de publicar: PR de release, fast-forward de `main`, tag y release en GitHub)
Pendientes al cierre:
- Python 3.13 y TypeScript 7: estudio para la 3.1.
- typescript-eslint 8.74 / `minimatch` (Dependabot, desde el 2026-12-07).
- G47 (depende de doc_organize).
