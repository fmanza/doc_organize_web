# Contexto y taxonomías

La pantalla **Contexto** (botón «Contexto» del proyecto) clasifica los documentos convertidos en los **ejes** de su
taxonomía (el dominio, el tipo de material y los ejes que solo etiquetan, como «Impuestos»), los copia a una **carpeta
reorganizada** del proyecto (`organizado/<dominio>/<tipo>/<documento>/`) y genera un **sitio**
navegable con Zensical. Todo se escribe en la carpeta del proyecto, en la ubicación de destino: los originales y las
conversiones no cambian.

Necesita que el proyecto esté [escaneado](escaneo.md): solo entran los documentos convertidos con éxito cuyo original
sigue en el origen. Los que se movieron a `duplicados` (desde la 2.2, con su conversión) o se borraron desde el último
escaneo no entran, y el resultado los cuenta en «Originales que ya no están».

## Los pasos (2.1)

Desde la 2.1, la pantalla sigue el orden de trabajo. Una cabecera común, también en Revisar, Calidad y el sitio, lleva
el estado del contexto, el aviso si está desactualizado y los pasos:

| Paso | Qué se hace |
|---|---|
| **1. Taxonomía** | Cómo se clasifican los documentos: catálogo, plantilla o [manifiesto](#manifiesto-del-proyecto), y el [perfil del proyecto](#perfil-del-proyecto-y-vista-previa-del-prompt-20) |
| **2. Construir** | Carpeta, umbral, sitio e IA; «Construir» o «Reconstruir» |
| **3. Resultado** | Resumen, dominios y documentos, versiones de un documento y «Borrar contexto» |
| **4. Revisar** | [Revisar clasificación](#revisar-clasificación-20) |
| **5. Calidad** | [Calidad](#calidad-20) |
| **6. Entregar** | [Sitio](#sitio) y [entregas](#entregar-el-contexto-20) |
| **Historial** | [Historial](#historial) de las construcciones |

- Sin contexto, la página se abre en «Taxonomía» y los pasos 3 a 6 están desactivados. Con contexto, se abre en
  «Resultado».
- «Construir» solo lo ven los editores y propietarios con el destino de lectura y escritura. Los demás ven la
  taxonomía en solo lectura.
- Cada paso tiene su dirección (`…/context?paso=construir`, por ejemplo).
- Cambiar de paso no pierde nada de lo que no esté guardado. Salir de la página con cambios sin guardar en el
  manifiesto o en el perfil pide confirmación.

## Construir

En el paso **Taxonomía**, los editores y propietarios eligen el **catálogo**, en dos grupos:

| Grupo | Catálogo | Qué hace |
|---|---|---|
| Sin taxonomía | **Por carpetas** (antes «Descubrir dominios») | Un dominio por cada carpeta: cada documento va al de la carpeta que lo contiene (los de la raíz, al de la carpeta escaneada). No lee el contenido |
| Sin taxonomía | **Lista de dominios** (antes «Catálogo propio») | Solo los dominios que escribas (un eje: dominio) |
| Con taxonomía | **Plantilla** | Los ejes de una [plantilla de taxonomía](#plantillas-de-taxonomía): dominio, tipo de material y los que solo etiquetan |
| Con taxonomía | **Manifiesto del proyecto** | Los ejes del [manifiesto](#manifiesto-del-proyecto) del proyecto |

«Siguiente: Construir» lleva al paso **Construir**, que dice con qué taxonomía se va a construir («Cambiar» vuelve al
paso 1). Allí eligen también:

- **Carpeta reorganizada** (`organizado` por defecto), solo la primera vez. Para cambiarla, borra antes el contexto.
  No puede ser una carpeta que ya use el proyecto (`Conversión`, `duplicados`, `site`…).
- **Umbral de clasificación**: con uno más alto quedan más documentos sin clasificar. No afecta a «Por carpetas»:
  ahí todo documento con carpeta puntúa 1,0.
- **Construir el sitio**: si lo desmarcas, se borra el sitio anterior.

**Construir** es una [ejecución](ejecuciones.md) con varias fases: reunir documentos, clasificar (decisiones de
personas, reglas, semántica si el proyecto la activa e IA si se pide, en ese orden), copiar a la carpeta reorganizada
y construir el sitio. Se puede cancelar antes de que empiece a copiar; la copia y el sitio no se cortan a
medias. Reconstruir sustituye el contexto anterior.

Si un administrador ha configurado la IA, también puedes **clasificar con IA** lo que las reglas dejen sin
clasificar: ver [Inteligencia artificial](ia.md#clasificar-con-ia). Con plantilla o manifiesto puedes pedir además que
rellene los ejes de etiqueta vacíos («Qué se envía a la IA», 2.1).

### ¿Por carpetas o manifiesto?

| | Por carpetas | Manifiesto del proyecto |
|---|---|---|
| Dominios | Uno por carpeta (nombre de la carpeta inmediata) | Lista cerrada del manifiesto |
| Ejes | Dominio | Dominio, tipo de material y los ejes que solo etiquetan |
| Asignación | Por carpeta, sin puntuación (los de la raíz, al dominio de la carpeta escaneada) | Palabras de cada valor y sus palabras clave (`keywords`) en el título y el contenido, más la carpeta, con umbral, eje por eje; lo que queda vacío, con semántica o IA si se activan |
| Dominios nuevos | Sí, uno por carpeta | No |
| Estado | Borrador | Confirmado |
| Cuándo | Carpetas ya temáticas; primer contexto rápido | Vocabulario propio, independiente de las carpetas |

Con «Por carpetas» solo quedan sin clasificar los documentos que no están bien convertidos o cuya carpeta no
tiene letras ni números.

## Ver el contexto

El paso **Resultado** muestra los dominios con sus documentos (con los valores de cada eje como insignias) y los **sin
clasificar**, paginados. Cada documento enlaza a su
conversión en el [visor](documentos.md#visor). Hay dos avisos posibles:

- **No copiados**: documentos que no se pudieron copiar. Por ejemplo, el original, su Markdown o sus imágenes pasan por
  un enlace simbólico: doc_organize nunca copia lo que hay al otro lado de un enlace. El resto se copia igual.
- **Sin sitio**: no se pidió o falló (por ejemplo, superó el tiempo máximo de `DOW_CONTEXT_SITE_TIMEOUT_SECONDS`, 600 s
  por defecto). La ejecución dice por qué.

### Metadatos y cómo se clasificó (1.5.0)

Desde la 1.5.0, cada documento clasificado muestra:

- **Autor**, **descripción** y **palabras clave** que declara el propio fichero (propiedades del PDF u Office).
    - Si el documento no las declara y se activó [completar con IA](ia.md#completar-descripciones-con-ia), las
      rellena la IA y llevan la marca **IA**.
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

**Agrupar versiones aunque cambie el formato** (2.5.0, debajo del modo de versiones; desactivado por defecto): con la
casilla, `Manual_v2.docx` y `Manual_v3.pdf` también son versiones del mismo documento. La misma versión en varios
formatos (`Manual_v3.docx` y `Manual_v3.pdf`) es vigente entera: «Solo la vigente» no deja fuera ninguno de los dos.
Actívala solo si en el proyecto el mismo nombre en otro formato es el mismo documento (no, por ejemplo, unos datos en
Excel y su informe en PDF).

### Clasificación semántica (2.0)

Con «Clasificación semántica» activada en «Contexto e IA del proyecto» (propietario o editor; desactivada por
defecto), cada construcción rellena, **antes de la IA**, los ejes que las reglas y las decisiones dejaron vacíos
comparando el texto de cada documento con el nombre, la descripción y las palabras clave de cada valor (embeddings).
Los valores que asigna llevan la marca «Semántica» y la «Similitud mínima» (0,75 por defecto) decide cuándo se
asigna. Con la IA activada, además, los documentos parecidos ya clasificados con fiabilidad le sirven de ejemplo.

Necesita la IA configurada (fila «Embeddings (semántica)» de «Modelos por funcionalidad»; sin modelo propio, el
alias `doc-organize-embed`): si no lo está, la construcción se hace sin semántica y lo avisa. El texto de los documentos
sale hacia el servicio de embeddings (redactado si la redacción está activada). Los vectores se guardan en `.doc_organize/embeddings/` de la
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

**Ver el sitio** (paso «Entregar») lo abre dentro de la aplicación. El sitio se genera a partir del contenido de los documentos, que
puede traer HTML o scripts, así que se muestra **aislado** ([ADR-010](../adr/ADR-010-sitio-de-contexto-aislado.md)):

- Sus scripts no pueden usar tu sesión ni leer datos de la aplicación.
- La dirección lleva un acceso temporal que caduca en una hora o al cerrar tu sesión. **Renovar acceso** pide otro.
- **Abrir en otra pestaña** mantiene el mismo aislamiento.
- **Volver a 6. Entregar** (2.2) regresa al paso, aunque se haya navegado dentro del sitio.

Desde la 1.9.0 (doc_organize 1.7.0), el sitio y la carpeta reorganizada se publican con las **credenciales**
(contraseñas, tokens, claves) sustituidas por `«REDACTADO»`, también en los títulos del menú. `Conversión/` y los
originales no cambian.

### Entregar el contexto (2.0)

La tarjeta **Entregar el contexto** del paso «Entregar» prepara el contexto para quien no tiene cuenta en la aplicación o
para un chat de IA. Cada entrega es una ejecución (con progreso y cancelación) que puede lanzar cualquier miembro, como las
[exportaciones](documentos.md); el fichero se descarga desde su detalle y caduca con la retención de siempre.

- **Excel del contexto**: los documentos con sus ejes (también desde Documentos → Exportar).
- **Sitio sin conexión (ZIP + SHA-256)**: el sitio para abrirlo desde el disco (doble clic en `sitio/index.html`; si el
  navegador limita la búsqueda, `start_server.py` lo sirve en `127.0.0.1`). No pide nada a terceros y el HTML de los
  documentos se **neutraliza** (se ve como texto), porque fuera de la aplicación no hay aislamiento. Las credenciales
  se redactan según «Contexto e IA del proyecto». Antes de empaquetarlo se comprueba (sin recursos de terceros,
  enlaces que existen, búsqueda sin conexión); si no pasa, la ejecución falla y el log dice por qué. Se construye sobre
  una copia en el espacio de trabajo: **el sitio que ves aquí no cambia**. Opción: `llms.txt` en la raíz.
- **Paquete para IA**: `llms.txt`, un `.md` por documento con su ficha (ejes, quién lo clasificó, versión, ruta del
  original relativa a su carpeta) y `context.json`, para subirlo a un proyecto de un chat o a un agente. Opciones: sin
  el texto, también las versiones antiguas, un tope de caracteres por documento y `llms-full.txt`. Las credenciales se
  redactan **siempre**; solo un administrador de la instancia puede desactivarlo.

El detalle de la ejecución enseña la **huella SHA-256** del ZIP (el mismo contexto da el mismo ZIP) para comprobar
que el fichero que recibe el destinatario es el mismo, y queda en la auditoría junto con las opciones. Ambos ZIP
llevan el texto de los documentos: sale de la aplicación y puede ser confidencial.

El sitio sin conexión lleva solo las páginas (redactadas y neutralizadas), sus imágenes, `llms.txt` y los recursos
del tema: ni la copia de cada original ni su conversión (`.json`), que no se pueden redactar.
Las imágenes de los documentos sí van tal cual.

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
aparece, en el paso «Taxonomía», al elegir ese catálogo (el borrador sin guardar se conserva si cambias de catálogo y vuelves). Quien no
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

El bloque sigue el orden de trabajo: estado del manifiesto → **Crear o mejorar con IA** (el borrador y el
[agente](#diseñar-con-ia-y-comprobar-por-reglas-20); abierto si aún no hay manifiesto y plegado si lo hay) → editor →
«Comprobar manifiesto» y «Guardar manifiesto» → versiones → «Borrar manifiesto».

### Diseñar con IA y comprobar por reglas (2.0)

En el bloque del manifiesto hay dos ayudas más, que **nunca guardan nada**:

- **Diseñar taxonomía con IA (agente)**: un agente (fila «Agentes» de «Modelos por funcionalidad») explora los
  documentos y mejora el manifiesto, una plantilla o empieza de cero, con cambios pequeños que comprueba con las reglas contra
  todos los documentos, siguiendo tus indicaciones si las das. El «Tope de pasos» limita las llamadas al modelo. Al
  terminar enseña si mejora el de partida (cobertura y conflictos por eje, antes y después), su justificación y el
  coste; «Cargar la propuesta en el editor» la pone en el editor para revisarla y guardarla (con sus versiones, como
  cualquier cambio), y si un borrador anterior era mejor, «Cargar el mejor borrador comprobado». Quien gestiona las
  plantillas puede «Guardar como plantilla…». Si no termina (tope o cancelación), se puede cargar su último borrador.
  El texto de los documentos sale hacia el servicio de IA; queda en la auditoría.
- **Comprobar manifiesto**: clasifica por reglas, sin IA, todos los documentos convertidos con el texto del editor
  (aunque no esté guardado) y da por eje la cobertura, los conflictos (dos entradas casi empatadas) y las entradas
  vacías.

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

«Revisar clasificación» (paso «4. Revisar» de la cabecera) lista lo que conviene mirar tras la última construcción, de lo
más urgente a lo menos: decisiones desfasadas, documentos sin clasificar, reglas e IA que no coinciden en el dominio,
citas de la IA no encontradas en el texto, valores con confianza baja y versiones cuya vigente no se ha confirmado.
Desde la 2.5.0 también las decisiones de documentos que ya no están (como «Decisión desfasada», sin documento).

Se filtra por **motivo** y, desde la 2.5.0, por **nombre**: el buscador mira el título, la carpeta y la ruta del
documento (también la clave de una decisión sin documento). El total y el número de cada motivo del desplegable cuentan
solo lo que coincide con la búsqueda.

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

### Propuestas del revisor (2.0)

La tarjeta **Propuestas del revisor (IA)** pide a un agente (fila «Agentes» de «Modelos por funcionalidad») que repase los
primeros documentos de la cola (20 por defecto, hasta 100) y proponga una decisión para cada uno, con su motivo y una
cita del texto. Es una ejecución con progreso y cancelación; el **tope de pasos** (llamadas al modelo, 40 por defecto)
acota el gasto y el resultado dice cuántos pasos, herramientas y tokens usó. El texto de esos documentos sale hacia el
servicio de IA.

Las propuestas **no se aplican**: cada una se **acepta** (se guarda como decisión de quien la acepta, con las mismas
comprobaciones que una decisión hecha a mano, y se aplica al reconstruir) o se **descarta**. Una nueva pasada sustituye
las propuestas pendientes. Lanzar el revisor, aceptar y descartar: propietario o editor con el destino de lectura y
escritura; todo queda en la auditoría.

## Calidad (2.0)

«Calidad» (paso «5. Calidad» de la cabecera) mide cuánto acierta la clasificación contra una **referencia**:

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

**Informe del auditor** (sin IA, cualquier miembro): por eje, cuántos documentos tienen valor, cuántos hay de cada valor,
cuántos con confianza baja o con la cita sin verificar, y lo que conviene revisar en el catálogo (valores sin
documentos, valores que acaparan casi todo…). Se calcula sobre el último contexto construido.

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
- El del **proyecto** («Perfil del proyecto» en el paso «Taxonomía») se guarda en `.doc_organize/profile.md` de la
  carpeta del proyecto y se **añade** detrás del de la plantilla o el manifiesto. doc_organize lo usa con **cualquier**
  catálogo, al clasificar y al describir con IA. Lo pueden cambiar el propietario y
  los editores, con el destino de lectura y escritura; queda en la auditoría sin el texto.
- **Vista previa del prompt** muestra lo que recibiría el modelo (instrucciones, perfil compuesto y catálogo con sus
  descripciones) con la plantilla elegida o el manifiesto, y con el perfil que hay en el editor aunque no esté guardado.
  **No llama al modelo** ni gasta nada. En el editor de plantillas hay la misma vista previa, con el perfil de la
  plantilla solo.
- Doc_organize envía como mucho 8000 caracteres y 20 ejemplos del perfil compuesto.

Desde la 2.1, el perfil del proyecto se muestra según el catálogo elegido:

| Catálogo | Perfil del proyecto |
|---|---|
| Plantilla | Siempre: es la forma de añadir lo propio del proyecto a una plantilla, que no se edita desde el proyecto |
| Por carpetas, Lista de dominios | Si hay IA configurada (clasificar o describir) o si ya existe; no hay perfil de taxonomía, así que es todo lo que recibe la IA |
| Manifiesto del proyecto | No se muestra: el perfil va en el cuerpo del manifiesto. Si ya existe un perfil aparte, sale un aviso con «Ver el perfil» y «Copiar al cuerpo del manifiesto», que lo añade al final del borrador sin guardar nada. Después de guardar el manifiesto, borra el perfil aparte para tenerlo en un solo sitio |

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
manifiesto y el [historial](#historial) se conservan.

**Contexto a medio guardar (2.1).** Si una construcción se interrumpe (por ejemplo, porque se reinicia el worker)
después de escribir en el destino y antes de guardar el contexto, la página dice que no hay contexto pero en la carpeta
del proyecto quedan `context.json` y la carpeta reorganizada. La página lo detecta y avisa «Hay un contexto a medio
guardar», con **Ir a Construir** (la construcción reutiliza esa carpeta y sustituye lo que hay) y **Borrar contexto**
(propietarios, con el destino de lectura y escritura). Construir de nuevo aprovecha la caché de IA de lo que ya se
había clasificado o descrito. Vaciar el histórico del proyecto también borra el contexto, su
historial y el manifiesto (este se puede restaurar desde [Versiones](#versiones-restaurar-y-borrar-180)).

## Historial

Desde la 1.5.0, cada construcción del contexto deja una línea en `historial_contexto/CONTEXT_HISTORY.jsonl`, en la
carpeta del proyecto. Lo escribe doc_organize y la web solo lo lee.

El paso **Historial** de la página del contexto muestra las últimas 10 construcciones, la más reciente primero. Cada
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
