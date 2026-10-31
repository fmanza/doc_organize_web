# Instrucciones IA

## A. doc_organize_web (crear, tarea WD-0.3, molde util_bbdd_web)

| Fichero | Contenido específico de doc_organize_web |
|---|---|
| `CLAUDE.md` | Importa `@.github/SHARED_INSTRUCTIONS.md`; tabla de slash commands; hooks |
| `.github/SHARED_INSTRUCTIONS.md` | Fuente canónica. Rol: ingeniero web senior que conoce doc_organize **como librería consumida**. Reglas no negociables (abajo), arquitectura, comandos de desarrollo, tests, dependencias, commits |
| `.github/copilot-instructions.md`, `.github/AGENTS.md` | Entry points de Copilot y agentes genéricos que remiten a SHARED |
| `.github/instructions/` | `backend`, `frontend`, `api_contract`, `docker`, `security`, `tests`, `docs`, `sync` (≈ UBW) **+ `filesystem.instructions.md`** (ubicaciones, resolución segura de rutas, red, `ro`/`rw`) **+ `jobs.instructions.md`** (colas cpu/gpu, cancelación, progreso) |
| `.github/prompts/` | `phase_implementation`, `new_feature`, `hotfix`, `refactor`, `audit_code`, `security_review`, `tech_debt`, `config_review`, `version_closure` |
| `.github/agents/` | Los 11 de UBW (`plan-architect`, `feature-implementer`, `frontend-reviewer`, `code-auditor`, `security-reviewer`…) |
| `.claude/commands/` | `phase`, `new-feature`, `hotfix`, `refactor`, `audit-code`, `security-review`, `tech-debt`, `config-review`, `version-closure` (envoltorios finos de los prompts) |
| `.claude/settings.json` | Hooks PostToolUse informativos: ruff + mypy del backend (si hay uv) y lint + typecheck del frontend |
| `.claude/README.md` | Hooks y `settings.local.json` |
| `.ai/` | `architecture.md`, `glossary.md` (proyecto, ubicación, run, artefacto, grupo de duplicados, contexto, taxonomía, familia IA, tenant), `product.md`, `runtime.md`, `standards.md`, `sessions/TEMPLATE/` |

**Reglas no negociables propuestas** (SHARED):

1. No modificar doc_organize desde la web; huecos → `docs/plan/DOC_ORGANIZE_GAPS.md`.
2. No inventar APIs: verificar en el wheel o en un clon local de [doc_organize](https://github.com/fmanza/doc_organize) (solo lectura); si no,
   `PENDIENTE DE VERIFICAR`.
3. Solo `backend/app/integrations/doc_organize/` importa `doc_organize` (test de arquitectura).
4. Operaciones pesadas (escaneo, OCR, dedup, contexto, IA, exportación) siempre como jobs; la API solo encola.
5. **Ninguna ruta del sistema de ficheros sin pasar por el resolvedor de ubicaciones**; autorización antes que
   existencia; nunca SQLite en una ubicación de red.
6. Secretos (claves IA, PAT de GitHub) nunca en claro: ni SQLite, logs, `run.json`, respuestas ni errores.
7. Operaciones que mueven o borran ficheros: rol autorizado, ubicación `rw`, vista previa y confirmación explícita.
8. Contrato primero: cambio en la API → `export_openapi.py` + `npm run gen:api` en el mismo cambio.
9. Sin `git add -A`; sin commits ni push salvo petición.

## B. doc_organize (adaptar a «librería pura», tareas L-14)

| Fichero | Cambio |
|---|---|
| `CLAUDE.md` | Quitar referencias a web; añadir «consumidores: doc_organize_web (no romper la API pública sin MAJOR)»; sección «MkDocs — cuándo actualizar» pasa a Zensical (`zensical build --strict` bloquea PR/release) |
| `.github/SHARED_INSTRUCTIONS.md` | Rol: ingeniero Python de librerías; arquitectura por niveles sin `web/`/`auth/`; regla «API pública = `__all__` + SemVer»; regla «nada de HTTP, usuarios ni tenants en la librería»; checklist de `DOC_ORGANIZE_GAPS.md` al cerrar una versión |
| `.github/instructions/architecture.instructions.md` | Eliminar el Nivel 3 web; test de arquitectura que prohíbe `fastapi`, `starlette`, `jinja2` |
| `.github/instructions/render*.instructions.md` | Revisar: si solo aplican a plantillas Jinja, pasan a doc_organize_web o se retiran |
| `.github/prompts/` | Retirar `tenant_role_user_redesign.prompt.md` (se va a la web, F9); revisar `doclink_extractor_plan.md`; resto sin cambios |
| `.github/agents/` | Sin `frontend`; `security-reviewer` centrado en rutas, ficheros y subprocesos |
| `.claude/settings.json` | Mantener ruff/mypy/pytest; quitar dependencias de extras web |
| `.ai/architecture.md`, `product.md`, `glossary.md` | Librería + CLI; enlace al proyecto web |
| Docs de gobierno obsoletas (`.github/PHASE_*_REPORT.md`, `EXECUTIVE_SUMMARY.md`, `IMPROVEMENTS_COMPLETED.md`, `AUDIT_PLAN_*`, `.ai/ULTRA_FINAL.md`, `FINAL_SUMMARY_PR_READY.md`…) | **Corregir en el sitio con una nota al final** (aprobaciones, versiones y tamaños no verificados), no borrar (criterio del mantenedor: se corrigen con nota, no se borran). Moverlas después a `.ai/doc_old/` solo con aprobación del mantenedor |

## C. util_bbdd_web

Sin cambios obligatorios. Opcional: extraer las plantillas comunes (prompts, agentes, `sessions/TEMPLATE`) a un
repositorio o carpeta compartida para que los tres repos no diverjan.
