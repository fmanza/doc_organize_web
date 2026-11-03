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

Se borran la carpeta reorganizada, el sitio, `context.json` y `domains/`. Las conversiones, los originales y el
manifiesto se conservan. Vaciar el histórico del proyecto también borra el contexto.
