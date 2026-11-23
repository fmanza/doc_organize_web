# TRACEABILITY

## Session metadata
- id: 2026-11-23-version-2.2.0
- fecha: 2026-11-23
- rama: develop → main
- skill: version_closure
- fase: VERSION

## Prompt issued
«Fusiona el PR #104 y actualiza el #105», «Fusiona el PR #105 y publica la web 2.2.0» y `/version-closure 2.2.0`.

## Context supplied
- Sesión `2026-11-23-ia-duplicados-2.2`; `docs/guides/publicar_version.md`; cierre anterior
  `2026-11-22-version-2.1.0`.

## AI output summary
- PR #104 (2.1.1) fusionado con squash (`d131119`) tras arreglar su E2E; no se publicó 2.1.1 por separado: va en la
  2.2.0.
- PR #105 fusionado con squash (`191c74e`) con CI en verde tras traer `develop`.
- PR #106 `release: v2.2.0` (versión en CHANGELOG, `backend/pyproject.toml`, `app/__init__.py`, `package.json` y lock,
  `uv.lock`, `openapi.json` y `DOW_TAG` de `.env.example`) fusionado en `develop` (`3df84a7`); CI de `develop` en
  verde; `main` por fast-forward a `3df84a7`; etiqueta `v2.2.0`; release de GitHub con las notas del CHANGELOG y la
  sección «Actualizar» (añadida en el cierre).
- Con doc_organize **2.2.0** (wheel de su release, SHA-256 en `uv.lock`); G45 resuelto.
- Sin despliegue local en esta sesión.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Release | https://github.com/fmanza/doc_organize_web/releases/tag/v2.2.0 | publicada |
| Etiqueta | `v2.2.0` sobre `3df84a7` | subida |

## Directrices para Futuras IAs
- **[release]**: igual que en `2026-11-22-version-2.1.0`; la sección «Actualizar» de las notas se escribe a mano al
  crear la release (no está en el CHANGELOG).
- **[sesiones]**: guardar PLAN y AUDIT_PLAN en la carpeta de la sesión al hacerlos; en la 2.2 no se hizo y la
  trazabilidad se reconstruyó desde los PR.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Despliegue local de la 2.2.0 (copia de seguridad, `DOW_TAG=2.2.0` en `.env`, modelo `doc-organize-dedup` en
  LiteLLM y reconstruir sin ejecuciones en marcha).
- Los de `2026-11-23-ia-duplicados-2.2` (opción (a) de C1, calibración, revisión visual).
