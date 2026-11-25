# Duplicados

La pantalla **Duplicados** (botón «Duplicados» en el proyecto) encuentra documentos repetidos en **todas** las
carpetas de origen del proyecto y te deja decidir, grupo a grupo, cuál se conserva. Funciona en dos pasos: **buscar**
no toca ningún fichero, y **aplicar** solo actúa sobre los grupos que confirmes.

Necesita que el proyecto esté [escaneado](escaneo.md): la búsqueda usa el hash de cada documento que guardó el último
escaneo, así que es rápida incluso con cien mil documentos. Los documentos que se añadieron después no aparecen hasta
volver a escanear.

## Buscar

Los editores y propietarios pulsan **Buscar**. Es una [ejecución](ejecuciones.md) que agrupa:

| Motivo | Qué agrupa |
|---|---|
| **Exactos** | Documentos con el mismo contenido (mismo SHA-256), aunque tengan otro nombre o estén en otra carpeta |
| **Versiones** | Mismo nombre base y extensión con contenido distinto: `informe_v1.pdf`, `informe_v2.pdf`, `informe final.pdf` |
| **Nombre parecido** | Con «Incluir nombres parecidos», nombres similares a partir del porcentaje que elijas (`presupuesto obra` y `presupuesto obras`). Solo si quedan como mucho 5 000 documentos sin agrupar |
| **Mismo contenido** (2.2) | Con «Mismo contenido», el mismo texto en ficheros distintos, por ejemplo un `.docx` y el `.pdf` que se exportó de él. Sin IA |
| **Contenido parecido (IA)** (2.2) | Con «Contenido parecido (IA)», versiones reescritas, borradores o plantillas con otros datos, a partir de la similitud que elijas (0,90 por defecto). Usa el modelo de **Duplicados por contenido** de [IA](ia.md) |

### Por contenido (2.2)

Las dos búsquedas por contenido comparan el **texto de la conversión**, así que sirven **después de escanear y
convertir**: es la misma pantalla, en una segunda vuelta. Solo comparan los documentos que no quedaron agrupados como
exactos, versiones o nombre parecido; los que no tienen conversión, o casi no tienen texto, se cuentan como «Sin
comparar por contenido».

- «Contenido parecido (IA)» solo se puede activar si un administrador ha configurado el modelo propio de
  «Duplicados por contenido». Envía el texto completo de cada documento comparado a ese modelo (con las credenciales
  redactadas), por eso conviene que sea local. Los vectores se guardan en el proyecto: repetir la búsqueda no los vuelve
  a pedir.
- Cada grupo parecido muestra el **significado** (similitud según el modelo) y el **texto** (palabra a palabra): un
  texto bajo con un significado alto es un documento reescrito o la misma plantilla con otros datos. «Contenido en
  otro» marca un documento que está dentro de otro (un anexo dentro del informe completo).
- **Ver diferencias** abre los textos de dos documentos del grupo lado a lado, sin formato, con las líneas que no están
  en el otro resaltadas.

### Excluir carpetas

La búsqueda no compara nada de las [carpetas excluidas del proyecto](escaneo.md#excluir-carpetas), aunque siga en la
caché de un escaneo anterior; el resultado lo cuenta como «Excluidos». Para dejar fuera algo **solo en esta búsqueda**,
escribe sus carpetas (relativas al origen, como `2019/archivo`) en «Excluir además en este análisis».

Si las exclusiones del proyecto cambian después de una búsqueda, la pantalla lo avisa y **Aplicar** la rechaza: hay
que volver a buscar, para que solo se mueva lo que se revisó.

El resultado dice cuántos grupos hay de cada tipo, cuántos ficheros sobran y cuánto ocupan los duplicados exactos.
«En la caché pero ya no en el origen» cuenta los documentos que se borraron o movieron desde el último escaneo. La
ejecución deja también un **Excel** con todos los grupos (sin rutas del servidor), para revisarlos fuera de la
aplicación.

## Revisar

«Revisar los grupos de duplicados», en el detalle de la ejecución, abre los grupos. Se ven de 10 en 10 (la página
está en la dirección), filtrados por motivo, con búsqueda y «Ordenar por» (orden de la vista previa, motivo o número de
documentos). Un grupo de más de 5 documentos se ve plegado, con los 5 primeros y el
que se conserva; «Ver N documentos más» abre el resto. Cada grupo muestra sus documentos lado a lado: ruta, tamaño, fecha de modificación y el principio del hash.
«Ver convertido» abre su Markdown en el [visor](documentos.md#visor).

- **Conservar por defecto** decide qué documento se queda en cada grupo: el más antiguo (como doc_organize), el más
  reciente o el de ruta más corta. En cada grupo puedes elegir otro («Elegido a mano»); «Restablecer las elecciones»
  las deshace.
- **Aplicar este grupo** viene marcado en los exactos y las versiones, y desmarcado en los de nombre parecido y en
  los de contenido: revísalos y márcalos uno a uno.
- Tus decisiones se mantienen al pasar de página mientras no salgas de la pantalla.

Si alguien aplicó duplicados después de esta búsqueda, un aviso te pide que vuelvas a buscar.

## Aplicar

**Aplicar…** pide primero qué hacer con los documentos que no se conservan:

| Modo | Qué hace | Quién |
|---|---|---|
| **Copiar** | Los copia a la carpeta `duplicados` de las salidas; el origen no cambia | Editores y propietarios |
| **Mover** | Los saca del origen a `duplicados`; su conversión, si la tienen, va con ellos a `duplicados/Conversión` (2.2) y deja de entrar en el contexto: reconstrúyelo después | Solo propietarios, y con el origen de lectura y escritura |
| **Solo informe** | No toca ningún fichero; solo deja el informe | Editores y propietarios |

Después sigue los mismos pasos que mover o borrar un proyecto:

1. **Calcular qué se aplicaría** (vista previa): cuántos grupos y ficheros, qué ocupan y cuántos grupos han cambiado
   desde la búsqueda. Como mucho 10 000 grupos de una vez: con más, aplica por partes o vuelve a buscar sin nombres
   parecidos.
2. Escribir el nombre del proyecto y confirmar.

Antes de tocar nada, la aplicación recalcula el hash de los documentos de cada grupo elegido. Si alguno cambió o ya no
está, o si su ruta pasa por un enlace simbólico, ese grupo se salta («Grupos saltados»). En `duplicados` cada fichero
conserva su ruta dentro del origen (`duplicados/2024/factura.pdf`). Nunca se sobrescribe un fichero de `duplicados`: si ya existe uno con ese
nombre, se le añade un sufijo con el hash. Cada fichero movido o copiado queda en la auditoría, y el informe de
doc_organize (`DEDUP_REPORT.json` y su histórico) se guarda en el estado del proyecto.

**Cancelar** detiene la aplicación entre dos grupos: lo ya aplicado se queda y aparece en el informe.

La búsqueda caduca a la hora, o antes si otra operación escribe en el proyecto (un escaneo, otra aplicación…). Si
caduca, vuelve a buscar.
