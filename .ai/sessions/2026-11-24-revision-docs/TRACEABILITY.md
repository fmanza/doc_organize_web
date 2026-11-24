# TRACEABILITY

## Session metadata
- id: 2026-11-24-revision-docs
- fecha: 2026-11-23 → 2026-11-24
- rama: `docs/revision-2.3.1` (PR #114) y `release/v2.3.2`
- skill: documentation + version_closure
- fase: IMPLEMENT (documentación y textos de la interfaz) + VERSION

## Prompt issued
«`.github\agents\documentation-generator.agent.md`, revisa el proyecto y actualiza toda la documentación y corrige
también el agente para que use docs/guides»; después «corrige también los textos de la interfaz», «crea una rama y abre
el PR a develop», «fusiona el PR cuando el CI esté en verde» y `/version-closure` (release v2.3.2, esta sesión).

## Context supplied
- `.github/agents/documentation-generator.agent.md`, `.github/instructions/docs.instructions.md`, `zensical.toml`,
  `docs/README.md`, `CHANGELOG.md` (2.0–2.3.1), `frontend/src/i18n/es/`, `openapi/openapi.json`, `backend/app/core/`,
  `docker/`, `docker-compose*.yml`.

## AI output summary
- Documentation Generator corregido: tabla «Dónde va cada cosa» (toda guía, de uso, operación o desarrollo, en
  `docs/guides/`; sin carpetas nuevas), `nav` de `zensical.toml` e índice obligatorios, fuentes de verdad (CHANGELOG,
  i18n, `DOW_*`, `docker/`) y `execute` para `zensical build --strict`. Fila actualizada en `.github/AGENTS.md`.
- Las 15 guías de `docs/guides/` verificadas contra el código (tres subagentes en paralelo por grupos: uso, contexto/IA,
  operación). Errores corregidos: Documentos en páginas fijas de 25 (no 50 con selector), crear proyectos exige el
  permiso «Crear proyectos», `DOW_CONTEXT_SITE_TIMEOUT_SECONDS` es del worker (no administrable), nombres de IA de la
  2.2. Añadido lo que faltaba (patrones de nombre y «Excluir subcarpetas», límite de 5 ejecuciones por usuario, cuota,
  `DOW_AI_*`, SemVer desde 1.0, E2E como en el CI, montajes en `worker-gpu`, «Restablecer las elecciones», tope de
  10 000 grupos, suelta de ubicaciones de la 2.3.1).
- `preproduccion_2_0.md`: nombre de un fondo documental interno sustituido por un ejemplo genérico.
- Portadas `README.md` y `docs/README.md` (doc_organize 2.2, ADR-015 en el índice, `runtime-gpu`); `.ai/product.md`
  (estaba en 1.4.4) y `.ai/glossary.md` (familias de IA sin Copilot, ejes, duplicados por contenido, tenants).
- Textos de la interfaz (`features.json`): sin «Modelos de IA» (avisos de «sin IA» del contexto y del proyecto, ayuda
  de la semántica y del máximo por ejecución), «Guardar Conexión con LiteLLM», aviso sin cifrado sin el «usuario» de
  Copilot, presentación de LiteLLM con duplicados por contenido. Tests unitarios y E2E (`ai.spec.ts`, `w9.ts`)
  ajustados.
- Validación local: `zensical build --strict` sin avisos; frontend `format:check`, `lint`, `typecheck` y `npm test`
  189/189 (dos tests con tiempo límite fallaron en la suite completa y pasaron solos).
- PR #114 con CI en verde (`backend`, `frontend`, `docs`, `image` con E2E) fusionado con squash en `develop`
  (`1c12481`).
- VERSION: 2.3.2 sincronizada en `CHANGELOG.md`, `backend/pyproject.toml`, `app/__init__.py`, `package.json` y lock,
  `uv.lock`, `openapi.json` y `DOW_TAG` de `.env.example`; `.ai/product.md` e `INDEX.md` al día. Commit propuesto, no
  ejecutado.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PR de documentación y textos | https://github.com/fmanza/doc_organize_web/pull/114 | fusionado (`1c12481`) |
| Release 2.3.2 | rama `release/v2.3.2` | preparada, sin commit |

## Directrices para Futuras IAs
- **[docs]**: toda guía nueva va a `docs/guides/` y se registra en el `nav` de `zensical.toml` y en `docs/README.md`;
  el agente Documentation Generator lo exige.
- **[docs]**: los nombres de pantalla se comprueban en `frontend/src/i18n/es/features.json`: la tabla de IA usa
  `ai.tasks` («Embeddings (semántica)»); `ai.tasksShort` («Contexto semántico») solo sale en IA › Parámetros.
- **[frontend]**: en Windows, ejecutar vitest desde `C:\…` (unidad en mayúscula); desde `c:\…` carga dos veces el
  módulo y fallan los 28 ficheros con «Vitest failed to find the current suite».
- **[frontend]**: en regex de tests de Testing Library, escapar los paréntesis de textos como «Embeddings (semántica)».
- **[repositorio público]**: `.ai/sessions/` de sesiones anteriores contiene el nombre de un fondo documental interno;
  no repetirlo en documentación nueva.
- **[git]**: los scripts que reescriben ficheros en Windows con `write_text` dejan CRLF; el repositorio es LF
  (`git ls-files --eol`).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit `release: v2.3.2 - …`, PR a `develop`, fast-forward de `main`, etiqueta y release de GitHub (a petición).
- Sin verificar en las guías: prueba con RTX 5070 y tamaño de los modelos (~1 GB), límites del perfil (8000
  caracteres / 20 ejemplos), contenido exacto del ZIP y del Excel de la caché, `app.cli backup --dest` «desde la
  0.6.0».
- Heredados de la 2.3.1: despliegue local 2.2.0 → 2.3.x, calibrar el umbral 0,90 de «contenido parecido», quitar
  `LocationUsageOut.deleted_projects` en la próxima mayor.
