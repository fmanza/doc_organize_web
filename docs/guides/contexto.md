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
| **Descubrir dominios** | Un dominio por cada carpeta: cada documento va al de la carpeta que lo contiene (los de la raíz, al de la carpeta escaneada). No lee el contenido |
| **Catálogo propio** | Solo los dominios que escribas (un eje: dominio) |
| **Plantilla** | Dominios y tipos de material de una [plantilla de taxonomía](#plantillas-de-taxonomía) (dos ejes) |
| **Manifiesto del proyecto** | Los del [manifiesto](#manifiesto-del-proyecto) del proyecto (dos ejes) |

También eligen:

- **Carpeta reorganizada** (`organizado` por defecto), solo la primera vez. Para cambiarla, borra antes el contexto.
  No puede ser una carpeta que ya use el proyecto (`Conversión`, `duplicados`, `site`…).
- **Umbral de clasificación**: con uno más alto quedan más documentos sin clasificar. No afecta a «Descubrir
  dominios»: ahí todo documento con carpeta puntúa 1,0.
- **Construir el sitio**: si lo desmarcas, se borra el sitio anterior.

**Construir** es una [ejecución](ejecuciones.md) con varias fases: reunir documentos, clasificar, copiar a la carpeta
reorganizada y construir el sitio. Se puede cancelar antes de que empiece a copiar; la copia y el sitio no se cortan a
medias. Reconstruir sustituye el contexto anterior.

Si un administrador ha configurado la IA, también puedes **clasificar con IA** lo que las reglas dejen sin
clasificar: ver [Inteligencia artificial](ia.md#clasificar-con-ia).

### ¿Descubrir dominios o manifiesto?

| | Descubrir dominios | Manifiesto del proyecto |
|---|---|---|
| Dominios | Uno por carpeta (nombre de la carpeta inmediata) | Lista cerrada del manifiesto |
| Ejes | Dominio | Dominio y tipo de material |
| Asignación | Por carpeta, sin puntuación (los de la raíz, al dominio de la carpeta escaneada) | Palabras del dominio y sus palabras clave (`keywords`) en el título y el contenido, más la carpeta, con umbral; el tipo de material, igual por separado |
| Dominios nuevos | Sí, uno por carpeta | No |
| Estado | Borrador | Confirmado |
| Cuándo | Carpetas ya temáticas; primer contexto rápido | Vocabulario propio, independiente de las carpetas |

Con «Descubrir dominios» solo quedan sin clasificar los documentos que no están bien convertidos o cuya carpeta no
tiene letras ni números.

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

### ¿Está al día? (2.0)

Cada escaneo (y cada construcción) compara el contexto con la caché: si un original **cambió**, si hay documentos
**nuevos** convertidos que el contexto no tiene, si alguno **ya no está**, o si el sitio es anterior a la última
construcción, la página Contexto lo avisa con los recuentos, unos ejemplos y «Ir a reconstruir». No se leen los
originales: la comparación usa la huella que guarda la caché del escaneo, así que solo es tan reciente como el último
escaneo. Los contextos construidos antes de la 2.0 no tienen huella de los originales: reconstruye una vez.

### Versiones de un documento (2.0)

Los documentos con marcador de versión en el nombre (`v1.2`, `rev2`, `versión 3`, `ed. 2`; las fechas no cuentan), en
la misma carpeta, con la misma extensión y el resto del nombre igual, son **versiones** del mismo documento. Qué hacer
con ellas se elige en «Contexto e IA del proyecto» (página del proyecto; propietario o editor, se aplica al
reconstruir):

- **Marcar la vigente** (por defecto): todas entran en el contexto y las antiguas llevan la insignia «Versión
  antigua»; «Solo vigentes» las oculta de la lista.
- **Solo la vigente**: las antiguas quedan fuera del contexto (la tarjeta «Versiones de un documento» las lista) y el
  historial lo anota como «Versión antigua», no como documento que sale.
- **Todas, sin marcar**: como antes de la 2.0.

La vigente es la versión más alta, salvo que una persona elija otra con «Marcar como vigente» (en la tarjeta de
versiones o en «Revisar clasificación»), que se guarda como decisión y se aplica al reconstruir.

### Clasificación semántica (2.0)

Con «Clasificación semántica» activada en «Contexto e IA del proyecto» (propietario o editor; desactivada por
defecto), cada construcción rellena, **antes de la IA**, los ejes que las reglas y las decisiones dejaron vacíos
comparando el texto de cada documento con el nombre, la descripción y las palabras clave de cada valor (embeddings).
Los valores que asigna llevan la marca «Semántica» y la «Similitud mínima» (0,75 por defecto) decide cuándo se
asigna. Con la IA activada, además, los documentos parecidos ya clasificados con fiabilidad le sirven de ejemplo.

Necesita «Modelos de IA» configurado (tarea «Embeddings»; sin modelo propio, el alias `doc-organize-embed`): si no lo
está, la construcción se hace sin semántica y lo avisa. El texto de los documentos sale hacia el servicio de
embeddings (redactado si la redacción está activada). Los vectores se guardan en `.doc_organize/embeddings/` de la
carpeta del proyecto, como `Conversión/`: reconstruir no vuelve a pedir los que no han cambiado, y borrar el contexto
no los borra. El resultado de la construcción dice cuántos textos se embebieron, cuántos salieron del índice y cuántos
documentos recibieron algún valor.

### Ejes: filtros, insignias y evidencia (2.0)

Con doc_organize 2.0 la taxonomía es una lista de **ejes**: el dominio (organiza las carpetas), el tipo de material y
los que solo etiquetan (marcos normativos, sistema de gestión...). En la lista de documentos:

- Hay un **filtro por eje** (salvo el dominio, que se elige en la tabla) con el número de documentos de cada valor.
  Valores del mismo eje se combinan con O («Marco A o Marco B») y ejes distintos con Y. Como mucho 20 valores a la vez.
- Cada documento muestra sus valores como insignias. Las que no salen de las reglas llevan quién las puso: **IA**,
  **Semántica** (embeddings) o **Persona** (una decisión).
- En «Cómo se clasificó», los valores de la IA traen su **cita** del documento y si se encontró en el texto enviado
  («Cita no encontrada»: su confianza queda bajo el umbral y conviene revisarlo), y el **prompt y el modelo** con los
  que se clasificó.

Los contextos construidos antes de la 2.0 solo tienen dominio y tipo de material; la cita y la procedencia aparecen al
reconstruir.

Al guardar un manifiesto o una plantilla se avisa de las **claves que no se usan** al clasificar y de los **ejes
implícitos** (listas de valores de nivel superior, formato de 1.x): conviene declararlos en `axes:` con su nombre y
descripción.

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

Desde la 1.9.0 (doc_organize 1.7.0), el sitio y la carpeta reorganizada se publican con las **credenciales**
(contraseñas, tokens, claves) sustituidas por `«REDACTADO»`, también en los títulos del menú. `Conversión/` y los
originales no cambian.

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

**Solo se usa al construir con el catálogo «Manifiesto del proyecto»**, y por eso el bloque del manifiesto solo
aparece al elegir ese catálogo (el borrador sin guardar se conserva si cambias de catálogo y vuelves). Quien no
construye (lectores, o destino de solo lectura) lo ve si el contexto se construyó con él y, si no, con el enlace «Ver el
manifiesto del proyecto».

Los editores lo editan en la página. Se valida al guardar y no se puede guardar mientras haya otra escritura en el
proyecto (un escaneo, otra construcción…). «Construir» usa el manifiesto **guardado**: con cambios sin guardar y este
catálogo, «Construir» se desactiva hasta que guardes. Hay tres formas de partir de algo:

- **Escribirlo** en el editor.
- **Partir de una plantilla**: con el catálogo «Plantilla» y una elegida, «Personalizar para este proyecto» copia su
  Markdown al editor y cambia al catálogo «Manifiesto del proyecto». No se guarda hasta que pulses «Guardar
  manifiesto»; «Deshacer» vuelve a lo que había. Es una copia: si la plantilla cambia después, el manifiesto no, y el
  contexto construido con él dice «Manifiesto del proyecto», no el nombre de la plantilla.
- **Pedir un borrador a la IA** («Pedir borrador»): propone uno a partir de una muestra de documentos y lo carga en el
  editor sin guardarlo ([borrador de manifiesto](ia.md#borrador-de-manifiesto)).

Si el editor ya tiene otro texto, cualquiera de las tres pide confirmación antes de sustituirlo.

### Versiones, restaurar y borrar (1.8.0)

Cada cambio del manifiesto guarda antes **lo que había**, para poder deshacerlo: al guardar, al borrar, al restaurar
una versión y al [vaciar el histórico](proyectos.md) del proyecto. Se conservan las **5 últimas** por proyecto.

- **Restaurar la versión anterior** recupera la más reciente, con confirmación. El texto actual se guarda a su vez como
  versión: restaurar también se puede deshacer. También funciona tras recargar la página, así que deshace una copia de
  plantilla ya guardada.
- **Versiones** lista fecha, quién hizo el cambio, qué cambio fue y el catálogo de cada una. «Ver» muestra su texto;
  «Restaurar» la recupera. Una versión «Sin manifiesto» borra el manifiesto al restaurarla; una «No válida» no se
  restaura: «Cargar en el editor» la lleva al editor para arreglarla.
- **Borrar manifiesto** lo borra, con confirmación; se puede recuperar desde «Versiones».

Si dos personas lo cambian a la vez (o alguien lo edita en la carpeta compartida), la segunda recibe «Otro usuario lo
ha cambiado: recarga para ver su versión»: la página vuelve a leerlo y conserva tu borrador.

Restaurar o borrar no cambia el contexto ya construido: si se construyó con el manifiesto antes del último cambio, la
página avisa de que hay que reconstruir.

Las versiones viven en la base de datos de la aplicación (`config.db`) y viajan en sus copias de seguridad; restaurar
una copia trae las versiones de ese momento, que pueden no coincidir con el manifiesto actual del destino.

## Revisar clasificación (2.0)

«Revisar clasificación» (botón del resumen del contexto) lista lo que conviene mirar tras la última construcción, de lo
más urgente a lo menos: decisiones desfasadas, documentos sin clasificar, reglas e IA que no coinciden en el dominio,
citas de la IA no encontradas en el texto, valores con confianza baja y versiones cuya vigente no se ha confirmado.

Sobre cada documento, el propietario y los editores (con el destino de lectura y escritura) pueden **decidir**:

- **Confirmar** la clasificación que tiene (todos sus ejes).
- **Cambiar…** los valores de un eje, solo entre los del catálogo (uno en el dominio y el tipo de material).
- **Excluir** el documento del contexto.
- **Marcar como vigente** una versión de un grupo de versiones.

Las decisiones se guardan en `.doc_organize/decisions.json` de la carpeta del proyecto, con quién decidió y cuándo, y
quedan en la auditoría. Se aplican en la **siguiente construcción**, antes de la IA, y ni las reglas ni la IA las
cambian (en el contexto aparecen con la marca «Persona»). Si el original cambia, la decisión deja de aplicarse y vuelve
a la cola como «Decisión desfasada»; si el documento desaparece o el valor ya no está en el catálogo, la tarjeta
«Decisiones» lo avisa. «Revocar» la retira (pasa al historial). Las decisiones solo se aplican con plantilla o
manifiesto.

## Calidad (2.0)

«Calidad» (botón del resumen del contexto) mide cuánto acierta la clasificación contra una **referencia**:

- **Excel etiquetado a mano** (hasta 5 MB): una fila por documento, con su clave en la columna `documento` (carpeta y
  ruta, como en «Revisar clasificación») y, por eje, el valor correcto en su columna (por defecto `dominio_ok` para el
  dominio y `tipo_ok` para el tipo de material; se pueden indicar otras, `eje:columna`). Varios valores separados por
  coma; `ninguno` si ninguno encaja; vacía = sin etiquetar. Se guarda en la app, no en el destino.
- **Decisiones del proyecto**: cada «Confirmar» y «Cambiar eje» cuenta como etiqueta.

**Evaluar** compara el contexto construido con la referencia: por eje, exactitud, cobertura, precisión y *recall*, la
exactitud según quién clasificó (reglas, IA, semántica, persona) y las confusiones más frecuentes.

**Comparar cambios** clasifica los documentos de la referencia con otra configuración (otra plantilla o el
manifiesto, la IA con otro modelo o alcance, o un perfil sin guardar) **sin guardar nada**, y enseña la exactitud de
cada eje frente a la del contexto actual. Con IA, el contenido de esos documentos sale hacia el servicio y el máximo de
documentos acota el gasto. Ambas son ejecuciones (con progreso y cancelación) que pueden lanzar el propietario y los
editores; la comparación queda en la auditoría.

## Perfil del proyecto y vista previa del prompt (2.0)

El **perfil** es lo que el modelo debe saber del proyecto al clasificar con IA: contexto, reglas de desempate,
glosario y ejemplos, cada uno en su sección:

```markdown
## Contexto del proyecto
Documentación de calidad y seguridad de una empresa de servicios.

## Reglas de desempate
- Una norma publicada es normativa aunque hable de procedimientos.

## Glosario
- SoA: declaración de aplicabilidad.

## Ejemplos
- «Política de seguridad» → gobernanza, política
```

- El de la **plantilla** o el **manifiesto** va en su cuerpo, tras el front matter; el de una plantilla lo editan quienes
  gestionan plantillas.
- El del **proyecto** («Perfil del proyecto» en la página Contexto) se guarda en `.doc_organize/profile.md` de la
  carpeta del proyecto y se **añade** detrás del de la plantilla o el manifiesto. Lo pueden cambiar el propietario y
  los editores, con el destino de lectura y escritura; queda en la auditoría sin el texto.
- **Vista previa del prompt** muestra lo que recibiría el modelo (instrucciones, perfil compuesto y catálogo con sus
  descripciones) con la plantilla elegida o el manifiesto, y con el perfil que hay en el editor aunque no esté guardado.
  **No llama al modelo** ni gasta nada. En el editor de plantillas hay la misma vista previa, con el perfil de la
  plantilla solo.
- Doc_organize envía como mucho 8000 caracteres y 20 ejemplos del perfil compuesto.

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
manifiesto y el [historial](#historial) se conservan. Vaciar el histórico del proyecto también borra el contexto, su
historial y el manifiesto (este se puede restaurar desde [Versiones](#versiones-restaurar-y-borrar-180)).

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
