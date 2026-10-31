# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/). Hasta la 1.0.0, una MINOR por fase del
ROADMAP (`0.<fase+1>.0`).

## [Unreleased]

## [0.1.0] - 2026-10-31

Fase 0 — fundaciones. Consume doc_organize **0.9.3**.

### Added

- **backend**: esqueleto FastAPI con capas `core`, `db`, `api`, `domain`, `integrations/doc_organize`, `jobs` y
  `workspace`. Ajustes `DOW_*` con Docker secrets (`dow_app_secret_key` y `dow_fernet_keys` obligatorios en
  producción); logs JSON con `request_id` (`X-Request-ID`); errores RFC 9457; cabeceras de seguridad y CSP; SQLite con
  WAL, `synchronous=NORMAL`, `busy_timeout` y claves foráneas; Alembic con la revisión `0001` vacía.
- **backend**: `GET /api/health` (`200 ok` / `503 degraded`) con las versiones de la aplicación y de doc_organize y el
  estado de `config.db`; SPA servida en `/` con *fallback*; `/api/docs` solo en `development` y sin
  `/api/openapi.json` en producción.
- **backend**: capa anticorrupción con test de arquitectura (solo `app/integrations/doc_organize` importa
  doc_organize o Docling; `domain` sin FastAPI); `scripts/export_openapi.py --check`; worker mínimo (`app.jobs.worker`).
- **frontend**: React 19 + TypeScript 5.9 estricto + Vite 8, Mantine 9 (tema claro/oscuro automático), React Router 8,
  TanStack Query 5, i18next en español (`core.json` / `features.json`), cliente `openapi-fetch` generado; layout con
  navegación por fases, página de salud y 404; ESLint, Prettier, Vitest y E2E de humo con Playwright.
- **docker**: Dockerfile multi-stage (`frontend-build`, `backend-build`, `backend-dev`, `runtime` CPU) con usuario no
  root, `read_only`, `tmpfs`, `cap_drop: ALL`, `no-new-privileges` y `HEALTHCHECK`; compose con `web` y `worker`
  (perfil), secretos y volúmenes `data`/`workspace`; `docker-compose.dev.yml` con ubicaciones locales de prueba;
  `scripts/generate_secrets.py`.
- **ci**: jobs `backend`, `frontend`, `docs` (`zensical build --strict`) e `image` (build, `/api/health`, import de
  Docling en la imagen y E2E); Dependabot para uv, npm, Docker y Actions con *cooldown* de 14 días.
- **docs**: sitio Zensical; ADR-001 a ADR-006; `PARIDAD.md` (inventario L-0 de la web integrada: 65 rutas HTTP,
  4 WebSocket y 20 plantillas); guías de desarrollo, despliegue y publicación; `LICENSE` (MIT), `CONTRIBUTING.md` y
  plantillas de issue.
- **ia**: configuración IA para Claude Code y GitHub Copilot (WD-0.3).

### Changed

- **docs**: `DOC_ORGANIZE_GAPS.md` con G14 y la sección «Resueltos» (G9 y G14 por doc_organize 0.9.3; G1 en parte).

### Removed

- `scripts/check_doc_links.py`: lo sustituye `zensical build --strict`.

### Notas

- doc_organize se instala desde el wheel de su release `v0.9.3` (URL + hash en `uv.lock`); torch y torchvision, desde
  el índice CPU de PyTorch.
