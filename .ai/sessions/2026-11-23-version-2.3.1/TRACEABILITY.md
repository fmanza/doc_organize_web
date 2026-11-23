# TRACEABILITY

## Session metadata
- id: 2026-11-23-version-2.3.1
- fecha: 2026-11-23
- rama: develop → main
- skill: version_closure
- fase: VERSION

## Prompt issued
«Fusiona el PR #111 y publica la web 2.3.1» y `/version-closure 2.3.1`.

## Context supplied
- Sesión `2026-11-23-ubicacion-libre`; `docs/guides/publicar_version.md`; cierre anterior `2026-11-23-version-2.3.0`.

## AI output summary
- PR #111 fusionado con squash (`ff8f2da`) con CI en verde.
- PR #112 `release: v2.3.1` (versión en CHANGELOG, `backend/pyproject.toml`, `app/__init__.py`, `package.json` y lock,
  `uv.lock`, `openapi.json` y `DOW_TAG` de `.env.example`) fusionado en `develop` (`df66045`; el CI de `ff8f2da` quedó cancelado al llegar este commit); CI de `develop` en
  verde; `main` por fast-forward a `df66045`; etiqueta `v2.3.1`; release de GitHub «Latest» con las notas del
  CHANGELOG y la sección «Actualizar» (copia de seguridad antes: la `0029` no se puede deshacer con proyectos borrados;
  sin ejecuciones en marcha; `DOW_TAG=2.3.1`).
- Sigue con doc_organize **2.2.0**; sin cambios en la librería.
- Sin despliegue local en esta sesión.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Release | https://github.com/fmanza/doc_organize_web/releases/tag/v2.3.1 | publicada |
| Etiqueta | `v2.3.1` sobre `df66045` | subida |

## Directrices para Futuras IAs
- **[release]**: igual que en `2026-11-23-version-2.3.0`; las notas de una versión con migración no reversible deben
  pedir la copia de seguridad en «Actualizar».
- **[sesiones]**: en esta versión PLAN y AUDIT_PLAN sí quedaron en la carpeta de la sesión (`2026-11-23-ubicacion-libre`).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Despliegue local de 2.2.0 → 2.3.1 (copia de seguridad, `DOW_TAG=2.3.1`, modelo `doc-organize-dedup` en LiteLLM,
  reconstruir sin ejecuciones en marcha; migraciones `0027`, `0028` y `0029`).
- Calibrar el umbral 0,90 y el tamaño de bloque de «contenido parecido» con `bge-m3` real.
- Quitar `LocationUsageOut.deleted_projects` y `LocationProjects.deleted` en la próxima versión mayor.
