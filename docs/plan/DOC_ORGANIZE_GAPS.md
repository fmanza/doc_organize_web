# Huecos de la API de doc_organize

Mismo contrato que `UTIL_BBDD_GAPS.md`: **no se parchea doc_organize desde la web**; cada hueco tiene un rodeo en
`backend/app/integrations/doc_organize/` hasta que la librería lo resuelva (tareas `L-*` de `TAREAS_DOC_ORGANIZE.md`).

Versión analizada: **doc_organize 0.9.0** (rama `develop`, commit `1e40c8c`, 2026-10-31).

| # | Hueco | Impacto en la web | Rodeo hasta resolverlo | Petición | Tarea |
|---|---|---|---|---|---|
| G1 | `__version__ = "0.1.0"` frente a `version = "0.9.0"` en `pyproject.toml`; `__all__` no incluye `ScanCommand`, `ContextBuilder`, eventos… | La web no puede comprobar la versión ni depender de una API pública declarada | Leer `importlib.metadata.version("doc_organize")` | Fachada pública coherente | L-1 |
| G2 | Sin `on_progress` ni `cancel_token`; cancelar = cerrar el generador (el OCR en curso sigue hasta terminar su lote) | Progreso sin total fiable; cancelar no es cooperativo | Contar eventos del generador; cancelar = matar el subproceso del job | Callback + token cooperativo | L-2 |
| G3 | `ai/*_client.py` importan `doc_organize.auth.InstanceSecretsStore` | La librería arrastra la capa de usuarios; impide retirar `auth/` | Construir los `*Config` en la web y llamar solo a los clientes | Clientes con config explícita | L-3 |
| G4 | `Project.tenant_id` y `ProjectRegistry(..., tenant_id=)`; registro en `~/.doc_organize/projects.json` | Dos fuentes de verdad de proyectos y tenants | La web no usa `ProjectRegistry`; deriva rutas por su cuenta (frágil) | `ProjectLayout` público y sin tenants | L-4, L-6c |
| G5 | Rutas de estado (`cache.db`, historial, errores, carpetas guardadas, `DEDUP_REPORT.json`) junto a las salidas | SQLite+WAL **no es fiable en SMB/NFS**; con destino de red se corrompería la caché | Pasar `cache_db` explícito (ya admitido) y aceptar el resto en destino | Todas las rutas de estado inyectables | L-5 |
| G6 | La deduplicación se resuelve dentro del escaneo con la opción «Deduplicar» y `move_group` mueve en el origen | Sin modo seco ni revisión; imposible en origen de solo lectura | Lanzar siempre el escaneo sin deduplicar y llamar a `find_duplicates` aparte | Vista previa + aplicar grupos confirmados + modos `move/copy/report_only` | L-6 |
| G7 | Eventos Pydantic sin versión de esquema | Un cambio de campos rompe SSE y el historial guardado | Test de contrato en la web | `schema_version` + `to_dict()` estable | L-6b |
| G8 | Exportaciones (ZIP, Excel de caché y de errores) dentro de `web/routes/downloads.py` | Se perderían al retirar `web/` | Copiar la lógica a la web (duplicación temporal) | Módulo `doc_organize.export` | L-7 |
| G9 | Sin wheel publicado en GitHub Releases con hash | No se puede fijar como util_bbdd (ADR-006) | Wheel construido localmente y vendorizado temporalmente | Workflow de release | L-6d |
| G10 | `MkDocsGenerator` depende de mkdocs (sin soporte futuro), lanza `mkdocs build` si está instalado y devuelve `site_built=False` si no | Resultado silencioso según la imagen; dependencia obsoleta en la imagen | Hasta 0.11.0: instalar `mkdocs` en la imagen y comprobar `site_built` (temporal) | `SiteGenerator` con Zensical + parámetro `build` + error tipado + extra `site` | L-8 |
| G11 | Sin reintentos ante errores de E/S transitorios ni timeout por documento | Escaneos largos en red fallan enteros por un corte | Reintentar el run entero (incremental gracias a la caché) | Reintentos y timeout configurables | L-9 |
| G12 | Detectores (`GpuStatus`, `AvStatus`, `OfficeStatus`) sin punto de entrada público | La ficha de capacidades duplicaría la detección | Importar los módulos internos desde la capa anticorrupción | `doc_organize.diagnostics` | L-9b |
| G13 | `ScanCommand.run_streaming` tiene 12 parámetros posicionales | Fácil desordenarlos al llamar | Llamar siempre por nombre | `ScanOptions` (modelo) | L-1 / L-2 |
