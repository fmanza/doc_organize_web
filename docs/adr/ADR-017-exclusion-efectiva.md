# ADR-017 — Exclusión efectiva de carpetas en todo el proyecto

- **Estado**: Aceptado (web 2.7.0)
- **Fecha**: 2026-11-25
- **Amplía**: exclusiones por carpeta guardada y patrones por ubicación de la web 1.4.0 (G41)

## Contexto

Desde la 1.4.0 el escaneo no recorre las subcarpetas excluidas de cada carpeta guardada
(`scanned_folders.excluded_subpaths`) ni los nombres que encajan con los patrones de la ubicación de origen
(`locations.ignore_patterns`). Quedaban cuatro huecos:

1. **No había exclusiones a nivel de proyecto.** Había que repetirlas en cada carpeta guardada, y los patrones solo los
   fijaba un admin, para toda la ubicación.
2. **Duplicados, contexto y exportaciones no aplicaban ninguna exclusión.** Leen la caché, y sin «forzar» lo excluido
   sigue en `cache.db`: una carpeta excluida seguía saliendo en duplicados, en el contexto y en los ZIP o Excel.
3. **Las carpetas de sistema de NAS y Windows** (`#recycle`, `@eaDir`, `.snapshot`, `$RECYCLE.BIN`, `Thumbs.db`,
   temporales `~$*` de Office…) no las salta la librería y había que escribirlas a mano.
4. **doc_organize 2.5.0 no permite borrar entradas de la caché por ruta** (`CacheManager` solo tiene `clear()` y
   `save_entries()`), ni filtrar `load_cache_page` por una lista de exclusiones.

## Decisión

1. **Exclusión efectiva.** Es la unión de:
    - las rutas y patrones del proyecto (`projects.excluded_paths`, relativas a la ubicación de origen, e
      `ignore_patterns`; migración `0033`), que gestiona el `owner` con `GET`/`PUT /api/v1/projects/{id}/exclusions`;
    - las subcarpetas excluidas de cada carpeta guardada;
    - los patrones de la ubicación de origen;
    - el **preset de carpetas de sistema** (`exclude_system_folders`, `SYSTEM_PATTERNS`).

    Una carpeta excluida queda **fuera del proyecto a todos los efectos**.
2. **Validación.**
    - Las rutas pasan por el resolvedor de ubicaciones, con la misma regla que las de una carpeta guardada: dentro de
      alguna carpeta del proyecto, sin `..` y sin enlaces. Si no existen, se guardan tal como se escribieron.
    - Los patrones siguen las reglas de una ubicación y, solo en el proyecto, se rechazan los que lo excluirían todo
      (`*`, `**`, `*.*`, `?*`).
    - Como mucho, 100 rutas y 30 patrones por proyecto.
3. **Copia al encolar.**
    - **Escaneo**: `ScanParams` recibe la exclusión efectiva, ya convertida a relativas de cada carpeta. Los máximos
      suben a 150 rutas por carpeta y 100 patrones. Si cambian las exclusiones del proyecto, la vista previa de «forzar»
      deja de valer, como ya pasaba con las de carpeta.
    - **Búsqueda de duplicados**: `DedupPreviewParams.exclusion` copia la exclusión efectiva y su huella, más
      `extra_excluded_paths`, que solo valen para ese análisis.
        - Aplicar esa vista previa responde `409 exclusions_changed` si la exclusión efectiva cambió después (regla 7:
          se mueve lo que se vio).
        - `GET /duplicates/last` avisa con `exclusions_changed`.
4. **Filtro en el worker.** Lo excluido que siga en la caché se descarta en memoria antes de usarlo:
    - en duplicados;
    - en el contexto y lo que lo lee: borradores, agentes, evaluación, calidad, entrega y su frescura (`SourceFolder.skip`);
    - en las exportaciones de la caché (ZIP y Excel: `ExportRequest.skip`).

    Las operaciones sin copia en sus parámetros usan la exclusión vigente al empezar el run. El filtro (`PathFilter`)
    replica el criterio de `EntryFilter.covers_cached` de doc_organize, que es de uso interno y no se importa (como ya
    hacía la vista previa de «forzar»): prefijo de ruta con `normcase` y patrones `fnmatch` sobre el nombre en
    minúsculas de cada tramo por debajo de la carpeta escaneada.
5. **Proyectos nuevos con el preset; los existentes, sin él.** Activarlo en un proyecto existente cambiaría sus
   resultados sin avisar.

## Consecuencias

- **Positivas**:
    - una sola regla para todo el proyecto;
    - las carpetas de sistema de un NAS quedan fuera por defecto;
    - duplicados y contexto ya no muestran lo que el usuario excluyó.
- **Negativas**:
    - **Lo excluido sigue ocupando la caché** hasta un «forzar reconversión» (hueco G47).
    - **El listado de documentos no lo filtra**: se pagina en SQL dentro de doc_organize. Muestra un aviso, sin
      recuento, porque contarlo exigiría leer toda la caché en cada petición.
    - **El índice de búsqueda de texto** se construye recorriendo el Markdown de `Conversión/`, no la caché: sigue
      incluyendo lo ya convertido de una carpeta excluida.
    - **Un contexto construido antes de excluir una carpeta** aparece como desfasado (sus documentos cuentan como
      «quitados») hasta reconstruirlo.

## Alternativas descartadas

- **Excluir solo en el escaneo**: el problema real era lo que sigue en la caché.
- **Exclusiones distintas por operación** (unas para duplicados, otras para el contexto): confunde. Para un caso puntual
  basta `extra_excluded_paths` en un análisis de duplicados.
- **Importar `EntryFilter`**: es de uso interno de doc_organize y no está en su API pública.
- **Purgar la caché desde la web** escribiendo en `cache.db`: la caché es de doc_organize (regla 1). Queda como hueco
  G47.
