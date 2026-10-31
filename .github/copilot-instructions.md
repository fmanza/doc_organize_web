# Instrucciones para GitHub Copilot — doc_organize_web

Lee primero la fuente canónica: [`SHARED_INSTRUCTIONS.md`](SHARED_INSTRUCTIONS.md) (rol, arquitectura, reglas no
negociables, comandos, flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION). Este fichero solo añade lo
específico de Copilot.

## Instrucciones por ruta

Copilot aplica automáticamente las de [`instructions/`](instructions/) según su `applyTo`:

| Fichero | Aplica a |
|---|---|
| `backend.instructions.md` | `backend/**/*.py` |
| `frontend.instructions.md` | `frontend/**/*.{ts,tsx}` |
| `api_contract.instructions.md` | routers, esquemas y cliente generado |
| `filesystem.instructions.md` | ubicaciones, proyectos, workspace, jobs y capa anticorrupción |
| `jobs.instructions.md` | worker, cola y ejecuciones |
| `security.instructions.md` | backend, Docker y frontend |
| `docker.instructions.md` | `docker/**`, `docker-compose*.yml` |
| `tests.instructions.md` | tests de backend, frontend y E2E |
| `docs.instructions.md` | `docs/**/*.md`, `README.md`, `CHANGELOG.md` |
| `sync.instructions.md` | `CHANGELOG.md`, `backend/pyproject.toml`, `frontend/package.json` |

## Agentes y prompts

Registro completo en [`AGENTS.md`](AGENTS.md). Flujo recomendado en Copilot Chat:

1. **Workflow Director** clasifica la solicitud.
2. Usa el prompt de [`prompts/`](prompts/) que indique (p. ej. `phase_implementation` para una fase del ROADMAP).
3. Copilot revisa; la ejecución de tests y Docker se hace en terminal (`run_in_terminal`) o con Claude Code.

## Particularidades

- No generes código que importe `doc_organize` fuera de `backend/app/integrations/doc_organize/`.
- No construyas rutas del sistema de ficheros a partir de texto del usuario sin el resolvedor de ubicaciones.
- No edites `frontend/src/api/schema.d.ts`: se genera con `npm run gen:api`.
- Sugerencias de UI: componentes Mantine, textos vía `useTranslation()`, nunca literales.

---

*Actualizado: 2026-10-31*
