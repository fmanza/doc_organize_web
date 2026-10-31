# Configuración de Claude Code

```text
.claude/
  settings.json         ← hooks PostToolUse compartidos (versionado)
  settings.local.json   ← permisos y ajustes personales (git-ignored)
  commands/             ← slash commands (envoltorios de .github/prompts/)
```

## Hooks (tras cada `Edit`/`Write`, informativos)

| Hook | Condición | Qué hace |
|---|---|---|
| ruff | existe `backend/` y `uv` en el PATH | `ruff check` del backend |
| mypy | existe `backend/` y `uv` en el PATH | `mypy` estricto del backend |
| eslint | `frontend/node_modules` existe | `npm run lint` |
| tsc | `frontend/node_modules` existe | `npm run typecheck` |

Hasta que la Fase 0 cree `backend/` y `frontend/`, los hooks no hacen nada. Sin `uv` local, los hooks de backend
tampoco: valida con la imagen `backend-dev` (ver `.github/SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo»). Los
hooks no formatean ni ejecutan la suite.

No añadas permisos a `settings.json`: van a `settings.local.json`.
