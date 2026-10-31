# Prompt: version_closure (aplicación web)

Cierre de versión, fase o sesión. Agente: `.github/agents/version-closer.agent.md`.

## Inputs requeridos
- **Cambios resumidos**
- **Versión objetivo**: `vX.Y.Z` (ver `.github/instructions/sync.instructions.md`)
- **Fase del ROADMAP** cerrada (si aplica)
- **Sesión**: carpeta `.ai/sessions/<fecha>-<slug>/`

## Devuelve en este orden
1. **Commit message** — Conventional Commits; releases: `release: vX.Y.Z - <resumen>`.
2. **Changelog** — `Added / Changed / Fixed / Removed / Security` por área (backend, frontend, docker, docs).
3. **Impacto en la API HTTP** — endpoints nuevos, cambiados o retirados.
4. **Migraciones** — revisiones Alembic nuevas, cambios en volúmenes, montajes, secretos o variables `DOW_*`.
5. **Compatibilidad** — versión de doc_organize, variantes de imagen (CPU/GPU/LibreOffice/AV), navegadores, Python
   y Node.
6. **Paridad** — filas de `docs/plan/PARIDAD.md` cerradas y huecos de `DOC_ORGANIZE_GAPS.md` resueltos o abiertos.
7. **Rollback** — imagen anterior + `alembic downgrade <rev>` + restauración de backup de `config.db` si aplica.
8. **Checklist final**:
   - [ ] Comandos de «Comandos de desarrollo» en verde
   - [ ] `docker compose build` y `/api/health` 200
   - [ ] Versiones sincronizadas (`sync.instructions.md`)
   - [ ] `## Directrices para Futuras IAs` poblada
9. **Pruebas ejecutadas o sugeridas** — solo las ejecutadas cuentan como ejecutadas.

## Reglas
- No inventes pruebas ni archivos; el commit se propone, no se ejecuta.
