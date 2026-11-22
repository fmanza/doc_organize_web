# TRACEABILITY

## Session metadata
- id: 2026-11-22-version-2.1.0
- fecha: 2026-11-22
- rama: develop → main
- skill: version_closure
- fase: VERSION

## Prompt issued
`/version-closure` y «Hazlo» (contenedor con la versión 2.1.0 y trazabilidad del cierre).

## Context supplied
- Sesiones `2026-11-22-contexto-orden`, `2026-11-22-ia-uso-copilot`, `2026-11-22-ia-alcance-construir` y
  `2026-11-22-contexto-a-medias`; `docs/guides/publicar_version.md`; `.github/SHARED_INSTRUCTIONS.md` (ramas).

## AI output summary
- PR #101 (todo `feature/2.1`) fusionado en `develop` con squash (`5bcdf8b`); CI del PR en verde con los 27 E2E.
- PR #102 `release: v2.1.0` (versión en CHANGELOG, `backend/pyproject.toml`, `app/__init__.py`, `package.json` y lock,
  `uv.lock`, `openapi.json` y `DOW_TAG` de `.env.example`) fusionado en `develop` (`6da2bd1`); CI de `develop` en
  verde; `main` por fast-forward a `6da2bd1`; etiqueta `v2.1.0`; release de GitHub con las notas del CHANGELOG y la
  sección «Actualizar».
- Sigue con doc_organize **2.0.1**: la 2.1.0 de la librería (publicada a la vez) solo marca Copilot como obsoleto.
- Despliegue local: sin ejecuciones en marcha, copia `/data/backups/20261122T193506Z`, `DOW_TAG=2.1.0` en `.env` y
  `docker compose --profile gpu up -d --build` desde `main`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Release | https://github.com/fmanza/doc_organize_web/releases/tag/v2.1.0 | publicada |
| Etiqueta | `v2.1.0` sobre `6da2bd1` | subida |

## Directrices para Futuras IAs
- **[release]**: `main` avanza por fast-forward (`git push origin <sha>:main`) al commit `release:` de `develop` con su CI
  en verde; GitHub avisa «Bypassed rule violations» por la excepción de administrador, es lo previsto. La release de la
  web se crea a mano (`gh release create`): ningún workflow la crea con la etiqueta.
- **[release/versión]**: la versión de la web vive en los sitios de `docs/guides/publicar_version.md`; las imágenes
  locales se etiquetan con `DOW_TAG` del `.env` real, que también hay que cambiar al desplegar.
- **[despliegue]**: antes de reconstruir los contenedores, comprobar que no hay runs `queued`/`running`: un reinicio los
  corta como `interrupted` (y doc_organize puede dejar un contexto a medio guardar, que la 2.1 ya detecta).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Revisión visual en el navegador de IA › Uso (claro, oscuro, móvil) y de los pasos de Contexto en móvil (360 px): no
  se hizo en esta sesión.
- Ejecuciones de IA que fallan sin resultado (p. ej. el agente con `AiConnectionError`) no registran su consumo (F0
  sigue pendiente).
