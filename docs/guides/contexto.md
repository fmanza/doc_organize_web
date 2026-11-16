# Contexto y taxonomías

La pantalla **Contexto** (botón «Contexto» del proyecto) clasifica los documentos convertidos por **dominios**, los
copia a una **carpeta reorganizada** del proyecto (`organizado/<dominio>/<tipo>/<documento>/`) y genera un **sitio**
navegable con Zensical. Todo se escribe en la carpeta del proyecto, en la ubicación de destino: los originales y las
conversiones no cambian.

Necesita que el proyecto esté [escaneado](escaneo.md): solo entran los documentos convertidos con éxito cuyo original
sigue en el origen. Los que se movieron a `duplicados` o se borraron desde el último escaneo no entran, y el resultado
los cuenta en «Originales que ya no están».

## Construir

Los editores y propietarios eligen el **catálogo de dominios**:

| Catálogo | Qué hace |
|---|---|
| **Descubrir dominios** | doc_organize propone los dominios a partir del contenido |
| **Catálogo propio** | Solo los dominios que escribas (un eje: dominio) |
| **Plantilla** | Dominios y tipos de material de una [plantilla de taxonomía](#plantillas-de-taxonomía) (dos ejes) |
| **Manifiesto del proyecto** | Los del [manifiesto](#manifiesto-del-proyecto) del proyecto (dos ejes) |

También eligen:

- **Carpeta reorganizada** (`organizado` por defecto), solo la primera vez. Para cambiarla, borra antes el contexto.
  No puede ser una carpeta que ya use el proyecto (`Conversión`, `duplicados`, `site`…).
- **Umbral de clasificación**: con uno más alto quedan más documentos sin clasificar.
- **Construir el sitio**: si lo desmarcas, se borra el sitio anterior.

**Construir** es una [ejecución](ejecuciones.md) con varias fases: reunir documentos, clasificar, copiar a la carpeta
reorganizada y construir el sitio. Se puede cancelar antes de que empiece a copiar; la copia y el sitio no se cortan a
medias. Reconstruir sustituye el contexto anterior.

Si un administrador ha configurado la IA, también puedes **clasificar con IA** lo que las reglas dejen sin
clasificar: ver [Inteligencia artificial](ia.md#clasificar-con-ia).

## Ver el contexto

La página muestra los dominios con sus documentos y los **sin clasificar**, paginados. Cada documento enlaza a su
conversión en el [visor](documentos.md#visor). Hay tres avisos posibles:

- **No copiados**: documentos que no se pudieron copiar. Por ejemplo, el original, su Markdown o sus imágenes pasan por
  un enlace simbólico: doc_organize nunca copia lo que hay al otro lado de un enlace. El resto se copia igual.
- **Nombre repetido** (solo en contextos construidos con doc_organize 0.13.0 o anterior): dos documentos con el mismo
  nombre en el mismo dominio y tipo iban a la misma carpeta de `organizado` y la copia de uno sustituía a la del otro.
  Ahora cada uno va a su carpeta (`<nombre>-<código>`); reconstruye el contexto para corregirlo.
- **Sin sitio**: no se pidió o falló (por ejemplo, superó el tiempo máximo de `DOW_CONTEXT_SITE_TIMEOUT_SECONDS`, 600 s
  por defecto). La ejecución dice por qué.

### Metadatos y cómo se clasificó (1.5.0)

Desde la 1.5.0, cada documento clasificado muestra:

- **Autor**, **descripción** y **palabras clave** que declara el propio fichero (propiedades del PDF u Office).
  - Si el documento no las declara y se activó [completar con IA](ia.md#completar-descripciones-con-ia), las rellena la IA y llevan la marca **IA**.
  - El autor nunca lo pone la IA.
- **Idioma**, detectado en el texto convertido. Si no es seguro, no se muestra.
- **Cómo se clasificó** (plegable):
  - el dominio que propusieron las reglas y su confianza;
  - si se preguntó a la IA, su propuesta, su confianza y su motivo;
  - en las plantillas, la confianza del tipo de material.

  «No aplicada» marca una propuesta de la IA que no se usó, porque las reglas ya habían decidido ese eje.

El resumen indica con qué versión de doc_organize se construyó y qué modelos de IA se usaron.

Los documentos se pueden filtrar por **idioma** (código de dos letras, como `es`), por **palabra clave** (alguna la
contiene) o por **La IA propuso otro**. La búsqueda también mira el autor y la descripción.

Los contextos construidos antes de la 1.5.0 no tienen estos datos hasta que se reconstruyen.

### Por qué no se clasificó un documento (1.6.0)

En **Sin clasificar**, la columna **Motivo** dice por qué cada documento se quedó fuera:

- **Sin convertir**: le falta el Markdown o el JSON de su conversión. Vuelve a escanear la carpeta.
- **Por debajo del umbral**: las reglas no llegaron al umbral y la IA (si se usó) no le asignó dominio. «Cómo se
  clasificó» muestra el dominio que propusieron las reglas y con qué confianza: bajar el umbral o ajustar la plantilla
  puede bastar.

Los sin clasificar muestran también su autor, descripción, palabras clave e idioma (la IA no los completa). En los
contextos construidos antes de la 1.6 la página pide reconstruir para verlos.

## Sitio

**Ver el sitio** lo abre dentro de la aplicación. El sitio se genera a partir del contenido de los documentos, que
puede traer HTML o scripts, así que se muestra **aislado** ([ADR-010](../adr/ADR-010-sitio-de-contexto-aislado.md)):

- Sus scripts no pueden usar tu sesión ni leer datos de la aplicación.
- La dirección lleva un acceso temporal que caduca en una hora o al cerrar tu sesión. **Renovar acceso** pide otro.
- **Abrir en otra pestaña** mantiene el mismo aislamiento.

## Manifiesto del proyecto

El **manifiesto de taxonomía** (`taxonomy_manifest.md` en la carpeta del proyecto) es el catálogo propio del
proyecto. Tiene el mismo formato que una plantilla:

```markdown
---
title: Obras
domains:
  - slug: facturas
    name: Facturas
    keywords: [factura, iva]
material_types:
  - slug: original
    name: Original
---
Notas libres.
```

Los editores lo editan en la página. Se valida al guardar y no se puede guardar mientras haya otra escritura en el
proyecto (un escaneo, otra construcción…). Con la IA configurada, «Pedir borrador» propone uno a partir de una muestra
de documentos y lo carga en el editor sin guardarlo ([borrador de manifiesto](ia.md#borrador-de-manifiesto)).

## Plantillas de taxonomía

**Administración → Plantillas de taxonomía** (solo administradores):

- Las **incluidas** en doc_organize (`calidad`, `sgi-integrado`, `sgi-iso27001`) son de solo lectura. **Duplicar** crea
  una copia personalizada con otro nombre para adaptarla.
- Las **personalizadas** se crean, editan y borran. El nombre admite minúsculas, dígitos y guiones, y no puede ser el
  de una incluida. El Markdown se valida al guardar.
- **Descargar .md** exporta cualquier plantilla. **Importar .md** abre el editor con un fichero (hasta 256 KiB) para
  revisarlo antes de guardarlo.

Construir con una plantilla usa su contenido de ese momento: cambiarla o borrarla después no afecta a los contextos ya
construidos.

## Borrar el contexto

Solo los propietarios, con el destino de lectura y escritura, y en dos pasos como el resto de operaciones que borran
ficheros:

1. Vista previa: cuántos ficheros y cuánto ocupan.
2. Escribir el nombre del proyecto y confirmar.

Se borran la carpeta reorganizada, el sitio, `context.json` y `domains/`. Las conversiones, los originales, el
manifiesto y el [historial](#historial) se conservan. Vaciar el histórico del proyecto también borra el contexto y su
historial.

## Historial

Desde la 1.5.0, cada construcción del contexto deja una línea en `historial_contexto/CONTEXT_HISTORY.jsonl`, en la
carpeta del proyecto. Lo escribe doc_organize y la web solo lo lee.

El bloque **Historial** de la página del contexto muestra las últimas 10 construcciones, la más reciente primero. Cada
una indica la fecha, los documentos clasificados y sin clasificar, el número de cambios, la versión de doc_organize y
los modelos de IA. Al desplegar una construcción se ven sus cambios:

- **Entra**: un documento nuevo en el contexto.
- **Sale**: un documento que ya no está.
- **Cambia**: un documento que pasa de un dominio o tipo de material a otro; también si pasa de clasificado a sin
  clasificar, o al revés.

La página muestra como mucho los primeros 200 cambios de cada construcción. **Descargar Excel** genera el historial
completo, con las hojas «Construcciones» y «Cambios». Lo mismo está en
[Documentos → Exportar](documentos.md), con el botón «Excel del historial del contexto».

- El historial se ve aunque se haya borrado el contexto.
- Una línea dañada del fichero se ignora.
- Si el fichero pasa de 16 MB, la página no lo muestra y remite al Excel.
