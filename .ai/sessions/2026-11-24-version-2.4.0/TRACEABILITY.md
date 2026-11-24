# TRACEABILITY

## Session metadata
- id: 2026-11-24-version-2.4.0
- fecha: 2026-11-24
- rama: `feat/doc-organize-2.4.1` → develop → main
- skill: version_closure
- fase: VERSION

## Prompt issued
«Nombres internos que usa la web… Dame opciones» → «Opcion 2» (la librería hace públicos los nombres; la web copia
`clean_text`/`clean_keywords`); «Sí, empieza la actualización de la web a 2.4.0»; «Fusiona los PR #111 y #117 y publica
la web 2.4.0» y `/version-closure web 2.4.0`.

## Context supplied
- doc_organize 2.4.0 (31 nombres nuevos en `__all__`; `test_names_used_by_doc_organize_web_are_public` impide quitarlos)
  y 2.4.1 (fase `done` del escaneo con unidades; canónico con desempate por ruta).
- Cierre anterior `2026-11-24-revision-docs` (web 2.3.2); `docs/guides/publicar_version.md`.

## AI output summary
- PR #117 (`02c1b01`): doc_organize 2.2.0 → **2.4.1** (wheel de la release; SHA-256 en `uv.lock`
  `db393c841c875bcd98e803bf6c05fb0bc5baa81eabbb31f2dc2a881248a8e541`, igual al publicado). 96 imports
  `from doc_organize.<submódulo> import …` pasan a `from doc_organize import …` (ruff fusionó 41) en la capa
  anticorrupción, tests y scripts. `scripts/bench_properties_strategies.py` lleva su copia de `clean_text` y
  `clean_keywords` (internos de la librería). `test_architecture`: el `CacheManager` del paquete raíz tampoco carga
  Docling.
- Pruebas locales: ruff, formato y mypy limpios; pytest 715 passed / 49 skipped con 2.4.0 y con 2.4.1.
  `tests/jobs/test_worker.py::test_swapped_output_folder_is_not_touched` se excluyó en local (Windows sin privilegio
  para enlaces simbólicos, `WinError 1314`); el CI lo ejecuta (backend en verde).
- PR #118 `release: v2.4.0` (CHANGELOG, `backend/pyproject.toml`, `app/__init__.py`, `package.json` y las líneas 3 y 9 del
  lock —la tercera aparición de `2.3.2` es `es-module-lexer` y no se toca—, línea de `doc-organize-web` en `uv.lock`,
  `openapi.json`, `DOW_TAG` de `.env.example` y `.ai/product.md`); `export_openapi.py --check` en verde. Fusionado en
  `develop` (`c803c67`; el CI de `02c1b01` quedó cancelado al llegar este commit); CI de `develop` en verde; `main`
  por fast-forward `240313c..c803c67`; etiqueta `v2.4.0`; release de GitHub «Latest» con las notas del CHANGELOG y
  «Actualizar» (sin migraciones; `DOW_TAG=2.4.0`; volver atrás con `DOW_TAG=2.3.2`).
- `docs/plan/DOC_ORGANIZE_GAPS.md`: G46 (nombres internos importados de submódulos) a «Resueltos».
- Sin despliegue local en esta sesión.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PR dependencia + imports | https://github.com/fmanza/doc_organize_web/pull/117 | fusionado |
| PR release | https://github.com/fmanza/doc_organize_web/pull/118 | fusionado |
| Release | https://github.com/fmanza/doc_organize_web/releases/tag/v2.4.0 | publicada |
| Etiqueta | `v2.4.0` sobre `c803c67` | subida |
| Librería | https://github.com/fmanza/doc_organize/releases/tag/v2.4.1 | publicada (consumida) |

## Directrices para Futuras IAs
- **[imports]**: de doc_organize se importa solo desde el paquete raíz (`from doc_organize import …`). Si hace falta
  algo que no está en `doc_organize.__all__`, se pide a la librería como API nueva (y se añade a su
  `test_names_used_by_doc_organize_web_are_public`); no se importa de un submódulo ni se parchea.
- **[release]**: en `frontend/package-lock.json` solo cambian las líneas 3 y 9; buscar y reemplazar la versión a ciegas
  puede tocar una dependencia con el mismo número.
- **[tests en Windows]**: el test de la carpeta de salida sustituida por un enlace necesita privilegio de enlaces
  simbólicos; en local se puede excluir con `--deselect` y lo valida el CI (Linux).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Despliegue local de la 2.4.0 (`DOW_TAG=2.4.0`; sin migraciones nuevas, pero si se viene de la 2.2.0 siguen
  `0027`–`0029` con copia de seguridad y el modelo `doc-organize-dedup` en LiteLLM).
- Heredados: calibrar el umbral 0,90 y el bloque de «contenido parecido» con `bge-m3` real; quitar
  `LocationUsageOut.deleted_projects` y `LocationProjects.deleted` en la próxima versión mayor.
- Librería (posible 2.4.2): `LiteLLMUsageConfig.virtual_key` sale en `repr()`/`model_dump()` (la web no registra esa
  config, pero conviene confirmarlo); `ContextBuilder.build` sin `across_extensions`; `review_queue` sin decisiones
  huérfanas.
