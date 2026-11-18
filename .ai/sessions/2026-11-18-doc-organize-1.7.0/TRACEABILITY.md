# TRACEABILITY

## Session metadata
- id: 2026-11-18-doc-organize-1.7.0
- fecha: 2026-11-18
- rama: `chore/doc-organize-1.7.0` (PR #72); release **1.9.0** desde `develop`
- skill: cambio de versión de doc_organize (ADR-006, `docs/guides/publicar_version.md`)
- fase: IMPLEMENT + VERSION (1.9.0)

## Prompt issued
«Sí, sube el pin de la web a 1.7.0» y, después, «Fusiona #72 y cierra la versión 1.9.0».

## AI output summary
- `backend/pyproject.toml`: `doc_organize==1.7.0` (también extras `ocr-gpu` y `av`) y URL del wheel de la release
  v1.7.0; `uv.lock` con su SHA-256 (`7388323bd20de4f283d2b6b63d4e5686658289c70f2016ea62f1aee7dd0719e9`).
- Sin cambios en la integración: la redacción de credenciales (M3b del plan único de doc_organize 2.0.0) está
  activada por defecto en la librería (`ContextBuilder`, borrador de manifiesto y `SiteGenerator`).
- Tests de `/api/health` y de capacidades con la versión nueva; guías de IA y de contexto; CHANGELOG.

## Verificación
- CI de #72 en verde (backend, frontend, docs, imagen con E2E).

## Pendiente
- Mostrar en la web `Context.credential_findings` (qué documentos se redactaron), si se quiere.
