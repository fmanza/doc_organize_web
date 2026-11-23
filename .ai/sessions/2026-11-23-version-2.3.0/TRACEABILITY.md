# TRACEABILITY

## Session metadata
- id: 2026-11-23-version-2.3.0
- fecha: 2026-11-23
- rama: develop → main
- skill: version_closure
- fase: VERSION

## Prompt issued
«Fusiona el PR #108 y publica la web 2.3.0» y `/version-closure 2.3.0`.

## Context supplied
- Sesión `2026-11-23-tema-usuario`; `docs/guides/publicar_version.md`; cierre anterior `2026-11-23-version-2.2.0`.

## AI output summary
- PR #108 actualizado con `develop` (estaba detrás) y fusionado con squash (`db004bc`) con CI en verde.
- PR #109 `release: v2.3.0` (versión en CHANGELOG, `backend/pyproject.toml`, `app/__init__.py`, `package.json` y lock,
  `uv.lock`, `openapi.json` y `DOW_TAG` de `.env.example`) fusionado en `develop` (`65a41b1`); CI de `develop` en
  verde; `main` por fast-forward a `65a41b1` (aviso esperado «Bypassed rule violations»); etiqueta `v2.3.0`; release
  de GitHub «Latest» con las notas del CHANGELOG y la sección «Actualizar» (migración `0028`, sin ejecuciones en
  marcha, `DOW_TAG=2.3.0`).
- Sigue con doc_organize **2.2.0**; sin cambios en la librería.
- Sin despliegue local en esta sesión.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Release | https://github.com/fmanza/doc_organize_web/releases/tag/v2.3.0 | publicada |
| Etiqueta | `v2.3.0` sobre `65a41b1` | subida |

## Directrices para Futuras IAs
- **[release]**: igual que en `2026-11-23-version-2.2.0`; la sección «Actualizar» se escribe a mano al crear la
  release.
- **[sesiones]**: el PLAN y el AUDIT_PLAN del tema volvieron a quedarse en la conversación; guardarlos en la carpeta
  de la sesión al hacerlos.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Despliegue local de la 2.2.0 + 2.3.0 (copia de seguridad, `DOW_TAG=2.3.0`, modelo `doc-organize-dedup` en LiteLLM,
  reconstruir sin ejecuciones en marcha; migraciones `0027` y `0028`).
- Los de `2026-11-23-ia-duplicados-2.2` (opción (a) de C1, calibración del umbral).
