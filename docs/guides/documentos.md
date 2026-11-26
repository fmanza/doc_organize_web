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

- **Buscar por nombre o subcarpeta** filtra por cualquier parte de la ruta dentro de la carpeta de origen, sin
  distinguir mayúsculas.
- **Estado** muestra solo los documentos convertidos, con error, pendientes…
- **Carpeta** limita la lista a una carpeta de origen.
- **Tipo de fichero** filtra por uno o varios tipos MIME; el desplegable dice cuántos documentos hay de cada uno (los
  escaneados antes de la 1.5 no lo tienen).
- **Ordenar por**: ruta, última actualización, estado de conversión, fallos seguidos, tipo o fecha de creación; los
  propietarios del proyecto, también por propietario. Sin elegir nada, por carpeta y ruta.
- Debajo de cada ruta, el tipo, la fecha de creación y los permisos, si el sistema de ficheros los da, y el
  propietario si el proyecto lo guarda y eres propietario del proyecto
  ([Usuarios y sesiones](usuarios_y_sesiones.md#propietario-de-los-ficheros)).
- La lista va **por páginas** de 25 y cada página la pide al servidor: funciona igual con cien documentos que con cien
  mil. La página está en la dirección (`?page=3`), así que «Atrás» y los enlaces compartidos vuelven a ella. Cambiar la
  búsqueda o un filtro vuelve a la primera.

## Visor

«Ver» abre el documento convertido:

- **Markdown**: el texto con sus títulos, tablas e imágenes (las que extrajo el escaneo con «Extraer imágenes»). Por
  seguridad, el visor no ejecuta nada del documento: quita scripts, formularios, estilos y marcos, no carga imágenes de
  otros sitios y los enlaces externos se abren en otra pestaña.
- **JSON**: los fragmentos (*chunks*) con sus títulos y páginas, tal como los usan el contexto y la IA. La ruta del
  documento de origen aparece relativa a su carpeta. En los convertidos con doc_organize anterior a 0.12.0 (web
  anterior a la 0.6.x), desde la 3.0 solo aparece el nombre del fichero: usa «Forzar reconversión» para recuperar la
  ruta relativa.
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
| **Excel del historial del contexto** (1.5.0) | Hoja «Construcciones» (una fila por construcción del contexto) y «Cambios» (documentos que entraron, salieron o cambiaron de dominio). Ver [Historial](contexto.md#historial) |
| **Excel del contexto** (2.0) | Hoja «Documentos» (una fila por documento con su dominio, tipo de material, quién lo clasificó y su confianza, y una columna por cada eje que solo etiqueta; los sin clasificar al final, con el motivo) y «Ejes» (cada valor del catálogo y cuántos documentos lo tienen). Rutas relativas a la carpeta de origen. Ver [Contexto](contexto.md) |

Las rutas de los documentos van relativas a su carpeta de origen y los mensajes de error, sin rutas del servidor. Los
JSON que van dentro del ZIP son los que escribió doc_organize: desde la versión 0.6.x de la aplicación llevan la ruta
del documento relativa a su carpeta (`source_path`), pero los convertidos antes conservan la ruta completa en el
servidor hasta que se reconviertan («Forzar reconversión» en [Escaneo](escaneo.md#forzar-reconversión)). Tenlo en
cuenta antes de compartir un ZIP de un proyecto antiguo fuera de la organización.

Con un proyecto grande, calcula antes el tamaño: si el ZIP no cabe en tu cuota o en el espacio libre del servidor, la
exportación falla antes de escribir nada («La exportación ocupa hasta … MB»).
