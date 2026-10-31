# TRACEABILITY

## Session metadata
- id: 2026-10-31-fase0
- fecha: 2026-10-31
- rama: feature/fase-0 (desde develop tras fusionar chore/config-ia, PR #4)
- skill: phase (+ release de doc_organize 0.9.3)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
/phase — Fase: 0. Alcance: completa. Mejoras opcionales: no. Restricciones: doc_organize 0.9.x como wheel local
mientras no haya release publicada (G9); sin GPU en desarrollo.

## Context supplied
- `.ai/*.md`, `docs/plan/*` (README, ARQUITECTURA_PROPUESTA, ROADMAP, DEPENDENCIAS, ADRS_PROPUESTOS, DOC_ORGANIZE_GAPS,
  DECISIONES_Y_RIESGOS, INSTRUCCIONES_IA)
- util_bbdd_web: estado tras su Fase 0 (commit `02c79a3`) como molde y versiones de 1.10.1
- doc_organize (clon local): `pyproject.toml`, tags, releases, `src/doc_organize/web/`

## AI output summary
- WD-0.3 (IA): configuración IA en `chore/config-ia`, PR #4 fusionado en `develop`.
- PLAN + AUDIT_PLAN (`PLAN.md`): `GO_CONDICIONAL`. Decisiones del mantenedor: publicar doc_organize 0.9.3 en lugar de
  vendorizar, torch desde el índice CPU, PR de la IA antes de la fase y protección de ramas por Claude.
- doc_organize 0.9.3 (PR #7 a `develop`, PR #8 a `main`, tag `v0.9.3`, release con wheel, sdist y `.sha256`):
  versión alineada en `pyproject.toml`/`__version__`/tag, CHANGELOG completo desde 0.9.0, COMPATIBILITY, Python
  mínimo 3.12 (y 3.11 fuera de la matriz del CI, a petición del mantenedor). Su CI estaba en rojo desde septiembre:
  ruff `<0.16`, pandas sin stubs en mypy, `cryptography` en `dev`, `_build_node` ante `OSError` de `is_symlink()`,
  doctest con rutas resueltas y test de duración estable en Windows. CI final en verde (Ubuntu y Windows, 3.12–3.14,
  tests lentos con Docling real).
- IMPLEMENT: backend (core, db, api/health, ACL, worker, Alembic 0001, export_openapi), 32 tests; frontend (Vite,
  React, Mantine, i18n core/features, cliente generado, salud, 404), 4 tests + 2 E2E; Docker multi-stage y compose;
  CI con `backend`, `frontend`, `docs`, `image` (+ import de Docling y E2E); Dependabot; Zensical; ADR-001…006;
  PARIDAD (65 HTTP + 4 WS + 20 plantillas); guías; LICENSE, CONTRIBUTING, plantillas de issue; `check_doc_links.py`
  retirado.
- AUDIT_CODE: corregido el 500 no controlado, que salía sin `X-Request-ID` ni cabeceras de seguridad (Starlette lo
  responde en `ServerErrorMiddleware`, fuera del middleware propio); test añadido.
- Validación local: ruff, format, mypy, pytest, `export_openapi --check`; format, lint, typecheck, Vitest, build;
  `zensical build --strict`; `docker compose build` + `/api/health` 200 + import de Docling + E2E 2/2 + ciclo del
  worker con SIGTERM.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-31-fase0/PLAN.md` | emitido (GO tras condiciones) |
| IMPLEMENT | `backend/`, `frontend/`, `docker/`, `docs/`, `.github/workflows/ci.yml`, `zensical.toml` | completado |
| Release de la librería | https://github.com/fmanza/doc_organize/releases/tag/v0.9.3 | publicada |

## Directrices para Futuras IAs
- **[dependencias-py]**: uv solo aplica `[tool.uv.sources]` a dependencias **directas**: para tomar torch/torchvision
  del índice CPU hay que declararlos en `dependencies` (si no, el lock trae 15 paquetes `nvidia-*` de PyPI).
- **[dependencias-py]**: el índice `download.pytorch.org/whl/cpu` publica `upload-time`, así que `exclude-newer` lo
  filtra (torch 2.14.1 y torchvision 0.29.1 son del 2026-09-30).
- **[doc_organize]**: 0.9.3 es la primera versión con wheel en GitHub Releases; SHA-256 del wheel
  `da158e4058af33b14d272aefe1ea0ec8234fb9c35f06bf01414cd357c4958fff`. Exige Python ≥ 3.12. Los extras `export` y `site`
  no existen hasta 0.11.0.
- **[doc_organize-ci]**: el CI de la librería instala la última ruff; ruff 0.16 activa reglas DTZ/RUF/SIM (11 avisos
  pendientes): está fijada a `<0.16` hasta revisarlos.
- **[imagen]**: la imagen `runtime` CPU mide 3,01 GB (torch CPU + Docling); necesita `libmagic1`, `libgl1` y
  `libglib2.0-0` para importar `docling.document_converter`. Los modelos aún no van en la imagen (ADR-011, Fase 4).
- **[backend]**: Starlette responde las excepciones no controladas en `ServerErrorMiddleware`, por fuera de cualquier
  middleware propio: `RequestMiddleware` las captura para conservar `X-Request-ID` y las cabeceras.
- **[backend]**: `mypy` usa `platform = "linux"`: el worker usa `signal.sigwait`, que no existe en Windows.
- **[backend]**: `Settings.environment` vale `production` por defecto y exige `dow_app_secret_key` y
  `dow_fernet_keys`; en local hay que poner `DOW_ENVIRONMENT=development`.
- **[tests]**: con `from __future__ import annotations`, un modelo Pydantic definido dentro de una función de test no
  lo resuelve FastAPI como cuerpo (lo toma como query): definirlo a nivel de módulo.
- **[frontend]**: jsdom 30 pide Node ≥ 24.15 (aviso `EBADENGINE` con 24.13 local; el CI y la imagen usan 24.21.0).
  El bundle inicial supera 500 kB: dividir con rutas lazy desde la Fase 1.
- **[docs]**: Zensical crea `.cache/` en la raíz (git-ignored).
- **[starlette]**: `TestClient` avisa `StarletteDeprecationWarning` por `httpx` (recomienda `httpx2`); pendiente, igual
  que en util_bbdd_web.

## Veredicto final
Veredicto: CLOSED (pendiente de CI del PR y de fusionar)
Pendientes al cierre:
- PR `feature/fase-0` → `develop` con CI en verde; checks obligatorios en `main`/`develop` (WD-0.4).
- Revisión de `PARIDAD.md` por el mantenedor (criterio de L-0).
- Publicar 0.1.0 (`develop` → `main`, tag) cuando el mantenedor lo decida.
