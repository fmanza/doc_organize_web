# PLAN + AUDIT_PLAN — Adoptar doc_organize 1.5.0 (2026-11-16)

doc_organize 1.5.0 (release publicada el 2026-11-16, wheel `sha256:16de8c3427caf07ce37a49f128cefc08533e07fa1e16f07729007b48741d908d`)
añade metadatos de fichero en el escaneo, autor/descripción/palabras clave/idioma y trazabilidad en el contexto, un
enriquecimiento opcional por IA, un historial de construcciones del contexto y su Excel. Sin cambios incompatibles en
la API. Detalle en su `CHANGELOG.md` y en `docs/api/publica.md` (fila 1.5.0).

## PLAN

### Objetivo

1. Pasar a doc_organize 1.5.0 sin cambiar el comportamiento visible de la web salvo lo que cambia la propia librería.
2. Mostrar los metadatos nuevos donde aportan: lista de Documentos y documentos del Contexto.
3. Ofrecer como opciones lo que la librería deja opcional: el propietario del fichero y la IA de descripciones.
4. Hacer visible el historial del contexto (qué cambia entre construcciones) y descargarlo en Excel.

### Inventario: qué trae 1.5.0 y dónde entra en la web

| Novedad de la librería | Punto de entrada en la web | Fase |
|---|---|---|
| Pin y dependencias nuevas (`py3langid`, `pypdfium2` declarada) | `backend/pyproject.toml` (líneas 18-21, 48, 52, 81), `uv.lock` | A |
| `cache.db` gana `created_time`, `mime_type`, `file_permissions`, `owner_name` (migración aditiva) | `integrations/doc_organize/cache.py` (`CachedDocument`), `DocumentOut`, `DocumentsPage.tsx` | B |
| `ScanOptions.capture_owner` (desactivado por defecto) | `ScanParams`, `ScanRequest`, `run_scan`, formulario de escaneo | B |
| `DomainDocument.author/description/keywords/language/ai_filled` | `ContextDoc`, `_outcome`, tabla `context_documents`, `ContextDocumentOut`, `ContextPage.tsx` | C |
| Trazabilidad: `rules_domain/rules_confidence/ai_domain/ai_confidence/ai_reasoning/material_type_confidence`; `Context.ai_classification_model/ai_enrichment_model/built_with_version` | Igual que la fila anterior, más `project_contexts` | C |
| `DocumentEnrichmentClient`, `LiteLLMEnrichmentConfig`, `ContextBuilder.build(ai_enrichment_enabled=, ai_enrichment_client=)`, `Context.ai_enrichment_*`, `ProgressEvent.phase="enrichment"` | `integrations/doc_organize/ai.py` (familia nueva), `ContextBuildParams`, `build_context`, `AiSettingsPage.tsx` | D |
| `historial_contexto/CONTEXT_HISTORY.jsonl`, `load_context_history`, `write_context_history_xlsx` | `integrations/doc_organize/export.py`, endpoint de historial, `ContextPage.tsx`, `ExportPanel.tsx` | E |

### Fase A — Subir el pin (sin funcionalidad nueva)

**Cambios**
- `doc_organize[...]==1.5.0` en las tres líneas de `pyproject.toml` y la URL de `[tool.uv.sources]` a
  `.../v1.5.0/doc_organize-1.5.0-py3-none-any.whl`; `uv lock` con el hash publicado. Comprobar que `uv.lock` añade
  `py3langid` y no cambia nada más de forma inesperada (el comentario de la línea 63 sobre zensical sigue valiendo).
- Tests que fijan la versión: `tests/api/test_health.py:18,30` y `tests/api/test_locations.py:418`.
- Docstrings de firmas verificadas: `integrations/doc_organize/context.py` y `ai.py` citan «v0.14.0»; añadir lo de 1.5.0
  que se use en las fases siguientes.
- `CHANGELOG.md` de la web: avisar de los **cambios de comportamiento que llegan solo con el pin** (siguiente bloque).

**Cambios de comportamiento que trae el pin solo** (verificados contra el código de la librería)

| Cambio | Efecto en la web | Acción |
|---|---|---|
| Las reglas de clasificación ignoran tildes | Al reconstruir, algunos documentos pueden pasar de «sin clasificar» o de la IA a un dominio por reglas | Aviso en el CHANGELOG y en la ayuda del Contexto |
| Cada construcción escribe `historial_contexto/CONTEXT_HISTORY.jsonl` en `output_root` (destino) | Fichero nuevo en el destino del proyecto; borrar el contexto no lo borra | Decidir si `context_paths` (vista previa del borrado) lo lista (ver Decisiones) |
| `historial_contexto` pasa a nombre reservado | `check_folder_name` rechaza esa carpeta reorganizada (usa la validación de la librería) | Ninguna; test de regresión |
| `ContextBuilder` abre cada original para leer autor/descripción/palabras clave | En ubicaciones de red, una lectura más por documento al construir el contexto | Medir en la red de pruebas (Riesgos, 1) |
| `cache.db` se migra al abrirse en escritura | El worker la migra en el primer escaneo; la API, en solo lectura, lee las columnas nuevas como `NULL` hasta entonces | Ninguna; test con una caché de 1.4.0 abierta por la API |
| `ContextRegistry.load_context` lanza `ContextError` con cualquier contexto dañado (antes `UnicodeDecodeError`/`TypeError`) | `existing_folder_name` y `delete_context` reciben un error de dominio | Revisar que lo traducen a un 4xx/5xx con mensaje, no a un 500 genérico |
| `Context.ai_classification_model` lo rellena la librería | Nada (la web no lo usa) | — |

**Entrega**: PR propio; puede publicarse como web 1.4.8 (PATCH) para tener las correcciones de la librería sin esperar
al resto.

### Fase B — Metadatos de fichero en Documentos y opción «guardar propietario»

**Backend**
- `CachedDocument` gana `mime_type`, `created_time`, `file_permissions`, `owner_name` (todos opcionales).
- `DocumentOut` gana `mime_type`, `created_at` (de `created_time`), `file_permissions` y `owner_name`.
  `owner_name` se devuelve solo a quien tenga el permiso que se decida (ver Decisiones).
- `ScanParams.capture_owner: bool = False` → `ScanRequest.capture_owner` → `ScanOptions(capture_owner=...)`, pasándolo
  solo si es `True` (mismo patrón que `exclude_paths`, para no cambiar las opciones por defecto).

**Limitación de la librería**: `CacheManager.load_cache_page` no filtra ni ordena por las columnas nuevas
(`CacheOrderBy` no las incluye). En esta fase solo se **muestran**. Filtrar u ordenar por tipo, fecha de creación o
propietario requiere pedir una API nueva a doc_organize (hueco nuevo en `docs/plan/`), como se hizo con G40/L-18.

**Frontend** (`DocumentsPage.tsx`): columnas «Tipo» (MIME legible) y «Creado»; «Propietario» y «Permisos» ocultas por
defecto. Casilla «Guardar el propietario de cada fichero» en el formulario de escaneo, con texto que explique que es un
dato personal y que un escaneo sin la casilla lo borra.

### Fase C — Metadatos y trazabilidad en el Contexto

**Modelo de datos**: migración `0012_context_metadata`.
- `context_documents`: `author` (String 500), `description` (Text), `keywords` (JSON, `[]`), `language` (String 8),
  `ai_filled` (JSON, `[]`), `rules_domain` (String 128), `rules_confidence` (Float), `ai_domain` (String 128),
  `ai_confidence` (Float), `ai_reasoning` (String 500), `material_type_confidence` (Float). Todos nulos o `[]` en las
  filas existentes, que se rellenan en la siguiente construcción.
- `project_contexts`: `built_with_version`, `ai_classification_model`, `ai_enrichment_model` (String, nulos).

**Backend**: `ContextDoc` y `_outcome` copian los campos de `DomainDocument`; el job los guarda; `ContextDocumentOut` y
`ContextOut` los exponen. Filtros nuevos en la página de documentos del contexto, por SQL en la base de la web (no
dependen de la librería): `language`, `keyword` (contiene) y «propuesta de la IA distinta del dominio» (`ai_domain` no
nulo y distinto de `domain_slug`).

**Frontend** (`ContextPage.tsx`): en cada documento, autor, idioma, palabras clave y descripción (marcada «IA» si está
en `ai_filled`); detalle plegable «Cómo se clasificó» con reglas (dominio y confianza), IA (dominio propuesto,
confianza y justificación) y el modelo. Filtros por idioma y palabra clave.

### Fase D — Descripción y palabras clave con IA (opcional)

- `ai.py`: familia nueva `litellm_enrichment` con `DOC_ORGANIZE_LITELLM_ENRICHMENT_BASE_URL/_VIRTUAL_KEY/_MODEL`
  (mismo esquema que las otras familias LiteLLM, secreto cifrado en `ai_settings`); `config_for` construye
  `LiteLLMEnrichmentConfig`; `enrichment_client(connection)` devuelve `DocumentEnrichmentClient`.
- `ContextBuildParams.ai_enrichment: bool = False`; `ContextRequest.enrichment: AiConnection | None`.
- `build_context`: si hay `enrichment`, abrir su cliente con `async with` y pasar `ai_enrichment_enabled=True` y
  `ai_enrichment_client`. Los límites `ai_max_failures`/`ai_max_documents` son los mismos argumentos que la
  clasificación, pero **cada fase cuenta su propio presupuesto**: con las dos activas pueden enviarse hasta el doble de
  documentos.
- Progreso: el callback `_classified` hoy trata todo `ProgressEvent` como `context_ai`. Distinguir `event.phase`
  (`"classification"` → `context_ai`, `"enrichment"` → `context_enrichment`, etapa nueva del run).
- `classification_stats` gana un hermano `enrichment_stats` (`ai_enrichment_sent/_applied/_failed/_stopped`) para el
  run y el panel de uso.
- Frontend: tarjeta nueva en `AiSettingsPage.tsx` y casilla «Completar descripción y palabras clave con IA» al construir
  el contexto, deshabilitada si la familia no está configurada (mismo patrón que `ai_classification`).

### Fase E — Historial del contexto

- `export.py`: `context_history(output_root)` con `load_context_history([ProjectLayout(output_root).context_history])`
  y `write_context_history_xlsx` con el mismo puente de cancelación y progreso que `write_cache_xlsx`.
- API: `GET /api/v1/projects/{id}/context/history?limit=` (resumen de las últimas construcciones y sus cambios, rutas
  hechas relativas como en el resto de la API) y la exportación «Historial del contexto (Excel)» en el mismo flujo de
  exportaciones que la caché y los errores.
- Frontend: en `ContextPage.tsx`, bloque «Historial» con las últimas N construcciones (fecha, versión, modelos,
  clasificados/sin clasificar, nº de cambios) y, al desplegar una, sus cambios (entra / sale / cambia, antes → después).
  Botón en `ExportPanel.tsx`.

### Orden y entregas

1. **A** (PR propio; puede ser web 1.4.8).
2. **B**, **C** y **E**: independientes entre sí; cada una en su PR.
3. **D** al final: depende de C para mostrar `ai_filled`.
4. Web 1.5.0 al cerrar B–E. OpenAPI exportado y cliente TS regenerado en cada PR que cambie la API.

### Pruebas

- **A**: suite completa del backend y del frontend; test de una caché de 1.4.0 abierta en solo lectura por la API
  (columnas nuevas a `None`); test de que una carpeta reorganizada llamada `historial_contexto` se rechaza; un
  `context.json` no UTF-8 y `[]` dan un error de dominio y no un 500.
- **B**: `ScanOptions` sin `capture_owner` por defecto y con él cuando se marca; `owner_name` oculto sin el permiso;
  render de las columnas.
- **C**: migración en las dos direcciones; el job copia todos los campos; filtros SQL; contexto anterior a 1.5.0 (campos
  vacíos) se muestra sin errores.
- **D**: familia nueva cifrada como las demás; sin configurar, la opción no se ofrece; el progreso distingue las dos
  fases; con clave rechazada, se registra `ai_enrichment_stopped="auth"` y la construcción termina; los dobles de
  cliente necesitan `config.model` (la librería anota `client.config.model` en el `Context`).
- **E**: historial vacío, con una línea dañada (se ignora), y con varias construcciones; rutas relativas en la API; Excel
  descargado con dos hojas.
- **e2e**: construir el contexto dos veces cambiando el catálogo y ver el cambio en «Historial».

## AUDIT_PLAN

### Riesgos funcionales

1. **Construcción más lenta en ubicaciones de red.** Desde 1.5.0, `ContextBuilder` abre cada original (PDF con PDFium;
   Office leyendo `docProps/core.xml` del zip) para sus propiedades. Sobre SMB son N aperturas más por construcción.
   **Medir en la red de pruebas** con un proyecto real antes de publicar, y anotar el tiempo en el CHANGELOG si sube de
   forma apreciable. Si es un problema, pedir a la librería una opción para no leer las propiedades.
2. **Documentos que cambian de dominio al reconstruir** por la corrección de tildes. Es correcto pero sorprende: aviso
   en el CHANGELOG, y el historial (Fase E) lo hace visible.
3. **Presupuesto doble de IA** con clasificación y enriquecimiento activos: cada fase puede enviar hasta
   `ai_max_documents`. Explicarlo en la casilla de la Fase D o reducir el presupuesto de cada fase (ver Decisiones).
4. **El propietario se borra con un escaneo sin la opción**: comportamiento de la librería (sin `capture_owner`, la
   caché guarda `None`). Si la web lo quiere persistente, la opción debe ir a nivel de proyecto o de ubicación y no por
   escaneo (ver Decisiones).
5. **Historial que sobrevive al borrado del contexto**: tras borrar y reconstruir, la primera construcción aparece sin
   «anterior» y todo como «entra».

### Riesgos técnicos

- **Rollback**: la migración de `cache.db` es aditiva. Una web con doc_organize 1.4.0 lee y escribe columnas explícitas
  y no se ve afectada por las nuevas. `context_documents` gana columnas con `downgrade`.
- **Imagen**: `py3langid` añade unos 4,6 MB y su modelo se carga una vez por proceso (~0,4 s) en el primer contexto.
- **Escrituras concurrentes al historial**: la librería no bloquea `CONTEXT_HISTORY.jsonl`. La web ya serializa los runs
  de un proyecto; comprobar que dos `context_build` del mismo proyecto no pueden solaparse.
- **Tamaño del historial**: la primera construcción de un proyecto grande escribe una línea con todos sus documentos y
  el fichero no rota. La API debe leer con `limit` y no devolver todos los cambios de todas las construcciones.
- **Contrato sync/async**: sin cambios; todo sigue dentro del subproceso del job o de la API, como hoy.

### Riesgos de seguridad y privacidad

- **`owner_name` es un dato personal** (usuario y dominio de Windows) que llegaría a la caché, a `DEDUP_REPORT.json` y a
  la API. Desactivado por defecto en la librería; en la web, quién lo activa y quién lo ve es una decisión (abajo).
- **Contenido enviado a un tercero**: con la Fase D, hasta 4000 caracteres de cada documento van al LiteLLM Proxy, como
  ya pasa con la clasificación. Debe seguir siendo opt-in por construcción y quedar registrado en la auditoría.
- **Texto del LLM en la interfaz**: `ai_reasoning` y la descripción vienen del modelo. Se muestran como texto (React
  escapa; nunca `dangerouslySetInnerHTML`).
- **Excel del historial**: la librería neutraliza fórmulas (`_excel_safe`); las rutas que salen por la API se hacen
  relativas como en el resto.
- Autorización antes que existencia en los endpoints nuevos (otro tenant → 404).

### Simplificaciones

- Las columnas de documentos de la Fase B se muestran sin filtros (la librería aún no los ofrece).
- El historial se lee del fichero de la librería, sin copiarlo a la base de la web.
- La retención y el origen del documento quedaron fuera de la librería en 1.5.0: no se plantean aquí.

### Decisiones pendientes (del usuario)

1. **Propietario**: ¿quién puede activar «guardar propietario» (`owner` del proyecto, administrador de ubicaciones) y
   quién lo ve en Documentos (todos los roles del proyecto o solo administración)? ¿Opción por escaneo o fija por
   proyecto/ubicación, para que no se borre con escaneos sin ella?
2. **Presupuesto de IA** con clasificación y enriquecimiento: ¿mismo `budget` para cada fase (hasta el doble) o
   repartirlo?
3. **Historial y borrado del contexto**: ¿la vista previa del borrado lo lista y se conserva (lo que hace la librería), o
   la web lo borra también?
4. **Versionado de la web**: ¿Fase A como 1.4.8 y el resto como 1.5.0, o todo en 1.5.0?

### Veredicto: GO_CONDICIONAL

1. Responder las decisiones 1 y 2 antes de las Fases B y D. La 3 y la 4 pueden esperar a la Fase E y al cierre.
2. Medir la Fase A en la red de pruebas (riesgo funcional 1) antes de publicarla.
3. La Fase A va primero y sola: el resto da por hecho doc_organize 1.5.0 instalado.
