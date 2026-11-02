# Documentos, búsqueda y exportaciones

Después de [escanear](escaneo.md) un proyecto, la pantalla **Documentos** (botón «Documentos» en el proyecto) muestra
todo lo que hay en su caché: qué se convirtió, qué falló y el resultado de cada documento. Cualquier miembro del
proyecto la ve, incluidos los lectores.

## Lista de documentos

Una fila por documento de las carpetas de origen, con su ruta **relativa a la carpeta** (`2024/facturas/enero.pdf`),
la fecha de la última actualización y el estado de la conversión:

| Estado | Significa |
|---|---|
| Convertido | Tiene su Markdown y su JSON; «Ver» abre el visor |
| Error | No se pudo convertir; el mensaje aparece en la fila (y en [Errores del escaneo](escaneo.md#errores)) |
| Pendiente, Convirtiendo, OCR pendiente… | El escaneo no terminó con él (cancelado o en curso) |

- **Buscar por nombre o carpeta** filtra por cualquier parte de la ruta, sin distinguir mayúsculas.
- **Carpeta** limita la lista a una carpeta de origen.
- La lista carga los documentos poco a poco mientras te desplazas: funciona igual con cien que con cien mil.

## Visor

«Ver» abre el documento convertido:

- **Markdown**: el texto con sus títulos, tablas e imágenes (las que extrajo el escaneo con «Extraer imágenes»). Por
  seguridad, el visor no ejecuta nada del documento: quita scripts, formularios, estilos y marcos, no carga imágenes de
  otros sitios y los enlaces externos se abren en otra pestaña.
- **JSON**: los fragmentos (*chunks*) con sus títulos y páginas, tal como los usan el contexto y la IA. La ruta del
  documento de origen aparece relativa a su carpeta.
- **Descargar Markdown** y **Descargar JSON** guardan el fichero.

El visor muestra ficheros de hasta 20 MB; los más grandes se obtienen con el ZIP del proyecto. Si una salida ya no
existe (se vació el histórico o se movió el proyecto), vuelve a escanear.

## Buscar en el contenido

**Buscar en el contenido** encuentra documentos convertidos que contienen **todas** las palabras que escribas, sin
distinguir mayúsculas ni tildes («reunion» encuentra «Reunión»), y muestra un fragmento con las coincidencias
resaltadas. Cada palabra cuenta también como principio de palabra: «fact» encuentra «factura».

La búsqueda se pone al día sola al terminar cada escaneo. Para un proyecto escaneado antes de esta versión, un editor
pulsa **Actualizar la búsqueda** una vez (es una ejecución; tarda según el número de documentos).

## Exportar

Desde «Documentos», cualquier miembro puede exportar. Cada exportación es una [ejecución](ejecuciones.md): sigue
aunque cierres la pestaña y, al terminar, el fichero aparece en su detalle para descargarlo. Ocupa tu cuota del
workspace y se borra según la retención de ejecuciones.

| Exportación | Contenido |
|---|---|
| **Calcular tamaño del ZIP** | Cuántos ficheros y cuánto ocuparía el ZIP, sin crearlo |
| **Exportar ZIP** | Todo `Conversión/` (Markdown, JSON e imágenes de todas las carpetas) y `cache_export.json` con el estado de cada documento |
| **Excel de la caché** | Una fila por documento: ruta, hash, estado y errores |
| **Excel de errores** | Hoja «Estado actual» (documentos que fallan ahora) e «Histórico» (los errores de cada escaneo) |

Las rutas de los documentos van relativas a su carpeta de origen y los mensajes de error, sin rutas del servidor. Los
JSON que van dentro del ZIP son los que escribió doc_organize, con la ruta completa del documento en el servidor
(`source_path`): tenlo en cuenta antes de compartir el ZIP fuera de la organización.

Con un proyecto grande, calcula antes el tamaño: si el ZIP no cabe en tu cuota o en el espacio libre del servidor, la
exportación falla antes de escribir nada («La exportación ocupa hasta … MB»).
