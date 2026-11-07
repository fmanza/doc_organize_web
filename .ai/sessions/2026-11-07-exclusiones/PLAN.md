# PLAN + AUDIT_PLAN — Exclusiones en el escaneo (2026-11-07)

Mejoras de [`MEJORAS.md`](../../../docs/plan/MEJORAS.md): **A** (P2) excluir subcarpetas de las carpetas guardadas,
por proyecto; **B** (P3) patrones de ruido por ubicación. Comparten el cambio de librería (hueco **G41**, tarea
**L-19**).

## PLAN

### Objetivo

- **A**: en cada carpeta guardada del proyecto se marcan subcarpetas que el escaneo no recorre.
- **B**: en una ubicación de origen, un administrador define patrones de nombre que no escanea ningún proyecto.
- Las dos se pueden quitar en cualquier momento.

### Comportamiento (decidido)

| Situación | Escaneo normal | Escaneo con `force` |
|---|---|---|
| Subcarpeta o fichero que pasa a estar excluido (A) o encaja con un patrón (B) | Se conservan su salida y su entrada de caché; no se vuelve a procesar | Cuenta como eliminado: se borran su salida y su entrada de caché |
| Se quita la exclusión o el patrón | Vuelve al recorrido; si se conservó, sale como «sin cambios» y no se reconvierte | Igual |
| Se quita después de un `force` que lo borró | Vuelve como «nuevo» y se reconvierte, incluido el OCR | Igual |

«En cualquier momento» incluye con un escaneo en marcha: al encolar el run se copian las exclusiones y los patrones
en sus parámetros, todos los tramos de ese run usan esa copia y el cambio se aplica desde el siguiente escaneo. No se
bloquea la edición (a diferencia de añadir o quitar carpetas, que exige no tener ejecuciones en marcha).

### Librería: doc_organize 1.3.0 (MINOR, G41 / L-19)

Cambios en `core/models.py`, `scanner/document_scanner.py` y `scan/scan_command.py`; documentación en
`docs/api/scan.md` y `docs/api/scanner.md`.

- `ScanOptions.exclude_paths: list[str] = []`: rutas absolutas, resueltas como las carpetas escaneadas; no se
  recorren ni ellas ni su contenido.
- `ScanOptions.ignore_patterns: list[str] = []`: patrones `fnmatch` sobre el nombre de cada entrada (nunca la ruta),
  sin distinguir mayúsculas, para ficheros y carpetas. Se suman al `IGNORED_NAMES` fijo (`.git`, `__pycache__`,
  `.DS_Store`).
- `DocumentScanner.scan_folders(..., exclude_paths=, ignore_patterns=)`, *keyword-only*. Lo excluido no va a
  `unreadable_*`: no es un error.
- Con `force`, lo que se deja de ver por una exclusión o un patrón es huérfano, como un fichero borrado (sin código
  nuevo; se documenta).
- `ScanSummary.excluded_cached: int` (clave nueva de `COMPLETED`): entradas de la caché bajo una exclusión o que
  encajan con un patrón, calculado desde la caché sin recorrer el disco.
- Con listas vacías, el comportamiento es el de la 1.2.0.

### Web: doc_organize_web 1.4.0

**Modelo de datos**: migración `0011_scan_exclusions`.

- `scanned_folders.excluded_subpaths: JSON` (rutas relativas a la carpeta guardada), `[]` por defecto. Si se quita la
  carpeta guardada, sus exclusiones desaparecen con la fila.
- `locations.ignore_patterns: JSON`, `[]` por defecto.

**API HTTP** (aditiva; OpenAPI exportado y cliente TS regenerado en el mismo cambio):

| Endpoint | Rol | Error de validación |
|---|---|---|
| `PUT /api/v1/projects/{id}/folders/{subpath}/exclusions` con `{"excluded": [...]}` | `owner` del proyecto | 400 |
| `PATCH /api/v1/locations/{id}`: campo `ignore_patterns` en `LocationChanges` | administrador de ubicaciones | 400 |

`PUT …/exclusions` devuelve la carpeta con sus exclusiones y si cada una existe ahora. Auditoría:
`SCAN_FOLDER_EXCLUSIONS` y el registro de cambios de la ubicación ya existente.

**Backend**

- `domain/scan/folders.py`: cada exclusión se normaliza (`normalize_relative`) y se resuelve (`resolve_within`) bajo
  la carpeta guardada; se rechaza la propia carpeta, lo que sale de ella y más de 50; las redundantes (una dentro de
  otra) se colapsan; una que ya no existe se guarda y se muestra como «no existe». Se guarda la ruta tal como la
  devuelve el resolvedor (la real del disco), no la que escribe el usuario.
- `domain/locations/service.py`: hasta 30 patrones de hasta 64 caracteres, sin `/` ni `\`, sin vacíos.
- `ScanParams`: copia de las exclusiones de cada carpeta y de los patrones de la ubicación al encolar.
- `ScanRequest` gana `exclude_paths` (absolutas) e `ignore_patterns`; `run_scan` los pasa a `ScanOptions`; el job
  loguea «N subcarpetas excluidas» por carpeta.
- Vista previa de `force` (`_preview`): recuento nuevo `excluded` (documentos en caché bajo una exclusión o que
  encajan con un patrón, que se van a borrar), calculado en la web con `cached_paths`.

**Frontend**

- «Carpetas» del proyecto: «Excluir subcarpetas» en cada carpeta guardada, con el explorador existente
  (`GET /fs/browse`) limitado a ella y casillas; las excluidas aparecen tachadas con la etiqueta «Excluida» y se pueden
  quitar, con el aviso «si se forzó desde entonces, se volverá a convertir».
- Ficha de ubicación de origen: editor de patrones con ejemplos (`~$*`, `@eaDir`, `#recycle`, `$RECYCLE.BIN`,
  `System Volume Information`).
- Confirmación de «Forzar reconversión»: «X documentos excluidos se borrarán» (A y B).
- Estados de carga, vacío, error y sin permiso; WCAG 2.2 AA.

### Riesgos

1. Un `force` borra salidas que el usuario no esperaba porque excluyó algo antes: recuento `excluded` en la vista
   previa obligatoria.
2. Un patrón de ubicación afecta a todos los proyectos de esa ubicación (decidido: también se borra con `force`).
3. La exclusión se calcula distinto en la librería y en la web (rutas resueltas, mayúsculas en Windows/SMB).

### Pruebas

- Librería: exclusión de subárbol; patrón en fichero y en carpeta; mayúsculas; `force` con lo excluido como huérfano;
  sin `force`, caché intacta; quitar la exclusión no reconvierte; `excluded_cached`; valores por defecto iguales a 1.2.0.
- Web: validaciones; permisos (no `owner` → 403, otro tenant → 404); la copia del run se mantiene entre tramos;
  recuento de la vista previa; migración en las dos direcciones; e2e del explorador con exclusiones.

## AUDIT_PLAN

### Riesgos funcionales

1. **Patrones y `force`** (corrige lo anotado antes en MEJORAS): si un patrón se añade después de que esos ficheros se
   convirtieran, un `force` posterior los borra en cualquier proyecto de la ubicación (p. ej. las miniaturas `.jpg` de
   `@eaDir`). **Decidido (2026-11-07): se borran**, igual que con la exclusión por proyecto, y la vista previa del
   `force` de cada proyecto lo avisa.
2. Quitar una exclusión tras un `force` reconvierte todo lo de esa subcarpeta: aviso en la interfaz.
3. Lo excluido pero conservado sigue en las pantallas que leen la caché (Documentos, duplicados, contexto, búsqueda).
   Coherente con «se conserva»; no se marca en 1.4.0.
4. Una exclusión que deja la carpeta vacía es válida: se escanea vacía y, con `force`, se borra todo.

### Riesgos técnicos

- Aditivo en las dos capas: columnas JSON con `[]` y `ScanParams` sin exclusiones mantienen el comportamiento. La web
  exige doc_organize ≥ 1.3.0 solo cuando hay exclusiones o patrones (si no, `missing_options` lo rechaza con mensaje).
- Mayúsculas: se guarda la ruta del resolvedor; la librería compara rutas resueltas.
- Rendimiento: excluir solo quita trabajo; hasta 30 patrones por entrada es despreciable frente al hash.
- Sin interfaces nuevas: campos en tipos existentes; el contrato sync/async no cambia.

### Riesgos de seguridad

- Una exclusión solo reduce el alcance; resuelta con el resolvedor único y dentro de la carpeta guardada.
- Patrones `fnmatch` sobre nombres, sin regex (sin ReDoS), con límites y sin separadores.
- Autorización antes que existencia: otro tenant → 404; sin `owner` → 403.
- Auditoría de quién excluye o cambia patrones, porque seguido de un `force` borra salidas.

### Simplificaciones

- Exclusiones en una columna JSON de `scanned_folders`, sin tabla nueva.
- Sin recuento de excluidos que recorra el disco: basta `excluded_cached`.
- Sin marca de «excluido» en Documentos.
- B puede entregarse después de A: comparte la librería, pero en la web es independiente.

### Veredicto: GO_CONDICIONAL

1. ~~Decidir si lo que encaja con un patrón se borra con `force`~~ — decidido: se borra (2026-11-07).
2. La vista previa de `force` muestra el recuento `excluded` antes de habilitar la confirmación.
3. Publicar primero doc_organize 1.3.0 (wheel y SHA-256) y después la web 1.4.0.
