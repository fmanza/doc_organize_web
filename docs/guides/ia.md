# Inteligencia artificial

La IA es opcional. La aplicación funciona sin ella. Cuando se configura, sirve para:

- **Clasificar con IA** lo que las reglas dejan sin clasificar al [construir el contexto](contexto.md): los ejes de la
  plantilla o del manifiesto (dominio, tipo de material y los que solo etiquetan), con la **cita** del texto que lo
  justifica.
- **Completar descripciones** y palabras clave de los documentos clasificados.
- La **clasificación semántica** (embeddings), antes de la IA, para los ejes que las reglas dejan vacíos.
- Pedir un **borrador del manifiesto** de taxonomía y los **agentes**: diseñar la taxonomía y el revisor de la
  clasificación.
- Ver el **uso**: el gasto y el presupuesto de la clave de LiteLLM, y los tokens, documentos y caché de cada
  ejecución.

Todo pasa por un [LiteLLM Proxy](https://docs.litellm.ai/docs/simple_proxy) de tu organización. Desde la 2.1 ya no hay
uso de GitHub Copilot.

!!! warning "El contenido de los documentos sale de la aplicación"

    Al clasificar, describir, pedir un borrador o lanzar un agente se envían al servicio configurado el **título y un
    extracto** de cada documento (los agentes y los embeddings, también fragmentos del texto). No se envían rutas del
    servidor. Nunca se hace por defecto: cada ejecución lo pide de forma explícita y la
    pantalla lo avisa. No lo actives con documentos que no puedan salir de tu organización.

    Las **credenciales** que aparezcan en ese título o extracto (contraseñas,
    tokens, claves de API, claves privadas, usuario y contraseña en una URL) se envían como `«REDACTADO»`. Es una red de
    seguridad, no una garantía: una contraseña solo de letras, por ejemplo, no se detecta.

    La redacción es un **ajuste de cada proyecto** («Contexto e IA del proyecto» en la página del proyecto,
    activado por defecto). Lo cambian el propietario y los editores, con el destino de lectura y escritura; queda en la
    auditoría y se aplica desde la siguiente construcción (y al pedir un borrador). Desactivarlo envía las credenciales
    tal cual a la IA y las publica en el sitio del contexto.

## Configuración IA (administradores)

**Administración → IA → Configuración** tiene una tarjeta por servicio:

| Servicio | Para qué | Campos |
|---|---|---|
| Modelos de IA | Todas las tareas: clasificar, completar descripciones, borrador de manifiesto, agentes y embeddings | URL y clave virtual generales; por tarea, modelo, clave propia y (clasificar y describir) máximo de documentos por ejecución, todos opcionales |
| Uso de LiteLLM | Gasto y presupuesto de la clave en el panel de uso | URL, clave virtual |

- La tarjeta «Modelos de IA» tiene arriba la URL y la clave general y, debajo, un bloque por tarea (clasificar,
  describir, diseñar la taxonomía, agentes y embeddings) con su modelo (vacío: el alias recomendado, que se ve en el
  campo), su clave propia y, en clasificar y describir, su máximo de documentos por ejecución.
- Un **cliente único** hace todas las tareas con el mismo LiteLLM Proxy. Cada tarea usa su modelo o, si no se
  configura, el alias recomendado `doc-organize-<tarea>`: `doc-organize-classify`, `doc-organize-enrich`,
  `doc-organize-taxonomy-design`, `doc-organize-agent` y `doc-organize-embed`. Si usas los alias, defínelos en el
  proxy. Las **claves propias por tarea son opcionales**: sin ella, la tarea usa la general. Sin máximo propio, una
  tarea usa «Documentos con IA por ejecución» de los parámetros.
- La tarea **`embed`** (embeddings) solo se usa si un proyecto activa la clasificación semántica («Contexto e IA del
  proyecto»). Su modelo tiene que ser de embeddings, no de chat.
- Al actualizar desde la 1.x, la migración pasa las cuatro tarjetas antiguas a «Modelos de IA»: la clasificación (con
  plantilla o manifiesto manda la de taxonomía), las descripciones y el borrador conservan cada una su clave y su
  modelo. Si usaban URL distintas, queda la de la clasificación por taxonomía (el aviso queda en el log de la
  migración). Volver a la 1.x desde la 2.0.0 rehace las cuatro tarjetas antiguas desde la configuración de 2.0 (la URL,
  la clave de cada tarea o la general y su modelo): no se guarda una copia de la de 1.x.
- Cada campo indica de dónde sale su valor: **Guardado aquí**, **Variable del servidor** (`DOC_ORGANIZE_LITELLM_BASE_URL`,
  `_VIRTUAL_KEY`, `_MODEL_<TAREA>`, `_VIRTUAL_KEY_<TAREA>`: los mismos nombres que doc_organize 2.0) o **Sin valor**.
  Lo guardado aquí tiene prioridad.
- Las variables de entorno de la 1.x (`DOC_ORGANIZE_LITELLM_CLASSIFICATION_*`, `_TAXONOMY_CLASSIFICATION_*`,
  `_ENRICHMENT_*`, `_TAXONOMY_MANIFEST_DRAFT_*`) **ya no se leen** (decisión D15, sin periodo de transición). Si siguen
  definidas, la página lo avisa con la equivalente de cada una y, si la IA queda sin configurar, encolar una ejecución
  con IA falla con un error que dice qué variable usar en su lugar: nunca se queda sin IA en silencio. La API de
  configuración las lista, sin valores.
- Las **claves y tokens** se guardan cifrados y nunca se vuelven a mostrar: solo «Guardada: …ab12» (los 4 últimos
  caracteres, o `***` si son muy cortos). Para cambiar una, escribe la nueva. Para volver a la variable del servidor,
  pulsa «Borrar valor guardado».
- La URL tiene que ser `http://` o `https://`, sin usuario ni contraseña, sin parámetros ni fragmento.
- Guardar claves exige el secreto `dow_fernet_keys` (lo crea `scripts/generate_secrets.py`). Si falta, la página lo
  avisa y solo deja guardar URL, modelo y usuario.
- Cada cambio queda en la [auditoría](usuarios_y_sesiones.md) con los nombres de los campos, nunca con las claves.

### Probar la conexión

Cada tarjeta tiene **Probar conexión**. Prueba con lo que haya en el formulario, **sin guardarlo**; lo que no has tocado
se toma de lo guardado o de la variable del servidor. Así puedes comprobar un cambio antes de guardarlo.

- **Probar conexión** comprueba que el servidor responde y que la clave es válida, sin gastar tokens:
  - LiteLLM: consulta los datos de la clave (`/key/info`). Si el servidor dice que la clave no tiene acceso al modelo
    configurado, lo avisa.
- **Probar el modelo** (en cada tarea de «Modelos de IA») envía además una petición mínima al modelo de esa tarea, con
  su clave, y con salida `json_schema` estricta (en embeddings, pide un vector), que gasta unos pocos tokens. Es la
  prueba que detecta un nombre de modelo mal escrito, y dice si el modelo admite `json_schema` (si no, doc_organize usa
  `json_object` y valida la respuesta igualmente). Si «Probar conexión» dice que la clave fue rechazada, prueba el
  modelo: algunos proxies no dejan a la clave consultar sus propios datos.
- El resultado dice el tiempo que tardó o el tipo de error: clave rechazada, sin conexión (o sin respuesta a tiempo), el
  modelo no respondió u otro error. Nunca muestra lo que contestó el servidor.
- Si cambias la URL, escribe también la clave general: la guardada nunca se envía a otro servidor, y las claves propias
  de cada tarea guardadas tampoco (la prueba usa la general).
- Como mucho una prueba por tarjeta cada 10 segundos. Cada prueba queda en la auditoría, sin URL ni claves.

En **Administración → IA → Parámetros** hay cinco ajustes más:

| Ajuste | Por defecto | Qué hace |
|---|---|---|
| Tiempo máximo por petición de IA | 120 s | Cada petición de clasificar, describir y embeddings (el panel de uso espera como mucho 10 s). Con un modelo local de 14B, una clasificación tarda de media unos 25 s y algunas pasan de 30 s (5–300) |
| Reintentos de conexión con la IA | 2 | Solo ante fallos de conexión |
| Documentos con IA por ejecución | 500 | Tope de documentos que una construcción del contexto puede enviar a la IA, por tarea: clasificar y completar descripciones cuentan cada uno el suyo. Una tarea con máximo propio en «Modelos de IA» usa el menor de los dos |
| Tiempo máximo del borrador y los agentes de IA | 300 s | Para las tareas largas: la petición del borrador (una sola y larga) y cada llamada de los agentes; con un modelo local puede tardar minutos (5–900) |
| Reintentos del borrador y los agentes de IA | 0 | Ante un fallo de conexión o de tiempo. Reintentar un timeout vuelve a pedir la misma generación al modelo |

### Modelos locales (Ollama)

Si el proxy sirve modelos de Ollama, revisa su **ventana de contexto** (`num_ctx`). Ollama usa **4096 tokens** por
defecto y **recorta en silencio** lo que no cabe: el modelo no ve el final de las instrucciones o del documento y
responde peor, sin ningún error. Para clasificar y describir suele bastar con 8192; **los agentes necesitan 32768**,
porque acumulan las herramientas y sus resultados en la conversación. Se fija en el proxy (`num_ctx` en los
`litellm_params` del modelo) o en Ollama (`PARAMETER num_ctx` del modelo, o `OLLAMA_CONTEXT_LENGTH` en el servidor).
Más contexto ocupa más memoria de la GPU.

## Clasificar con IA

En la página **Contexto**, marca «Clasificar con IA lo que las reglas dejen sin clasificar» antes de construir.
Solo está disponible si «Modelos de IA» está configurado. Con dominios descubiertos o con un catálogo propio la IA
asigna el dominio; con plantilla o manifiesto, los ejes que las reglas (y la semántica) dejaron vacíos.

- El modelo responde con salida `json_schema` estricta: solo puede elegir valores del catálogo, nunca inventa otros.
- Con cada valor da una **cita** literal del documento. Si la cita no aparece en el texto enviado, el valor queda con
  la confianza por debajo del umbral y el documento va a [Revisar clasificación](contexto.md#revisar-clasificación-20)
  («Cita no verificada»). En la página del contexto, «Cómo se clasificó» enseña la cita y con qué prompt y modelo se
  clasificó.
- El **perfil del proyecto** (contexto, reglas de desempate, glosario y ejemplos) va en el prompt; la vista previa
  enseña lo que recibiría el modelo sin llamarlo (ver [Contexto](contexto.md)).
- Las respuestas se guardan en la caché de IA del proyecto: **reconstruir sin cambios no vuelve a llamar al modelo**.
  El resultado de la ejecución dice cuántos documentos se resolvieron con la caché.
- Las decisiones de las personas se aplican antes y la IA no las cambia.
- Si el servicio rechaza la clave, deja de llamarse en esa ejecución. También deja de llamarse tras 3 fallos de
  conexión seguidos o al llegar al tope de documentos. El contexto se construye igualmente y los documentos que
  faltan quedan sin clasificar.
- El resultado de la ejecución dice cuántos documentos se enviaron, cuántos clasificó la IA, cuántos dieron error y,
  si paró, por qué. En la lista de documentos, los valores que asignó la IA llevan la marca **IA**.

## Completar descripciones con IA

En la página **Contexto** se puede marcar «Completar descripción y palabras clave con IA» antes de construir. Solo está disponible si «Modelos de IA» está configurado (tarea `enrich`: variables
`DOC_ORGANIZE_LITELLM_MODEL_ENRICH` y, si quiere clave propia, `DOC_ORGANIZE_LITELLM_VIRTUAL_KEY_ENRICH`).

- Solo se envían los documentos **clasificados** a los que les falta la descripción o las palabras clave en sus
  propiedades. Lo que declara el documento nunca se sustituye, y el autor nunca lo pone la IA.
- Lo que rellena la IA lleva la marca **IA** en la lista de documentos del [contexto](contexto.md).
- Tiene su propio tope de documentos por ejecución: con clasificar y completar marcados, la construcción puede enviar
  hasta el doble.
- Se detiene igual que la clasificación: si el servicio rechaza la clave, tras 3 fallos de conexión seguidos o al
  llegar al tope. El contexto se construye igualmente, y los documentos que faltan se quedan con lo que declaran.
- La ejecución muestra su propia etapa, «Completando descripciones con IA», y al terminar dice cuántos documentos se
  enviaron, cuántos se completaron y cuántos dieron error.

## Borrador de manifiesto

En la tarjeta **Manifiesto de taxonomía** de la página Contexto, «Pedir borrador» envía una muestra de documentos
convertidos al servicio y propone dominios y tipos de material. Por defecto son 25 documentos, como mucho 60,
repartidos entre carpetas.

Es una [ejecución](ejecuciones.md) que **no guarda nada**. Al terminar, el borrador se carga en el editor: revísalo,
cámbialo si hace falta y pulsa «Guardar manifiesto». Después puedes construir el contexto con «Manifiesto del
proyecto». Lo pueden pedir los editores y propietarios. Queda en la auditoría como «Borrador de manifiesto con IA».

Si la ejecución falla con «El servicio de IA no respondió a tiempo», el servicio aceptó la petición pero el modelo no
terminó en el plazo: sube «Tiempo máximo del borrador y los agentes de IA», pide una muestra más pequeña o usa un modelo más rápido.
«No se pudo conectar con el servicio de IA» es otra cosa: la URL no responde (el proxy está parado o no se alcanza).

## Clasificación semántica

Con «Clasificación semántica» activada en «Contexto e IA del proyecto», la construcción pide un vector (tarea `embed`)
por documento y por cada valor del catálogo, y asigna por similitud los ejes que las reglas dejaron vacíos, antes de la
IA. Los vectores se guardan en un índice del proyecto (`.doc_organize/embeddings/` del destino): reconstruir solo pide
los de lo que cambió. Ver [Contexto](contexto.md#clasificación-semántica-20).

## Agentes

Los agentes (tarea `agent`) trabajan con herramientas, varios pasos seguidos, y nunca aplican nada solos:

- **Diseñar taxonomía con IA**, en el bloque del manifiesto: propone cambios del manifiesto (o de una plantilla, o
  desde cero) comprobados por reglas contra todos los documentos. La propuesta se carga en el editor y se guarda a
  mano.
- **Propuestas del revisor**, en «Revisar clasificación»: propone una decisión por documento de la cola, que una persona
  acepta o descarta.

Cada uno tiene un **tope de pasos** (llamadas al modelo) y su resultado dice cuántos pasos, herramientas y tokens usó.
Usan el plazo y los reintentos de las tareas largas («Tiempo máximo del borrador y los agentes de IA») y necesitan un
modelo con llamadas a herramientas y contexto amplio (ver [Modelos locales](#modelos-locales-ollama)).

## Uso de IA (administradores)

**Administración → IA → Uso** (2.1) reúne dos cosas:

- **Clave de LiteLLM**: el gasto acumulado de la clave de «Uso de LiteLLM» (USD) y, si la clave tiene presupuesto en
  LiteLLM, cuánto queda y cuándo se reinicia. Lo dice el proxy (`/key/info`); se guarda 5 minutos y «Actualizar» pide
  datos nuevos, como mucho una vez cada 30 segundos.
- **Consumo por ejecución**, que registra la propia aplicación al terminar cada ejecución con IA (construir el
  contexto, borrador de manifiesto, agentes y la prueba de clasificación de Calidad), en el periodo elegido (7 días,
  30 días, este mes o todo):
  - indicadores: ejecuciones con IA, documentos enviados, resueltos con la caché (y qué parte del total), tokens de
    entrada y de salida;
  - **tokens por día**, en la hora local del navegador (la zona se indica en el gráfico), también como tabla;
  - tablas **por tarea**, **por modelo**, **por proyecto** y las **ejecuciones que más tokens gastaron**, con enlace.

El proxy no da el coste de cada llamada, así que no hay coste por ejecución ni por tarea: el coste es el de la clave.
Los tokens de los agentes son estimados (marcados con «≈») cuando el proxy no los informa.

Cada ejecución con IA muestra también, en su detalle, la tarjeta **Consumo de IA** (tarea, modelo, enviados, caché y
tokens), que ven los miembros del proyecto.

- El consumo se conserva aunque se borre la ejecución o el proyecto (queda el nombre del proyecto).
- No guarda texto de los documentos ni prompts: solo recuentos y el modelo.
- Al actualizar a la 2.1 se rellena con las ejecuciones anteriores, sin modelo (la 2.0 no lo guardaba).

## Rotar la clave de cifrado

1. Añade una clave Fernet nueva **al principio** de `secrets/fernet_keys.txt`, separada por una coma de la anterior.
   La primera cifra; todas descifran.
2. Reinicia `web` y `worker` y vuelve a cifrar con la nueva:

    ```bash
    docker compose exec web python -m app.cli rotate-secrets
    ```

3. Cuando termine sin errores, ya puedes quitar la clave antigua.

Si se pierde la clave, las credenciales guardadas no se pueden recuperar: la página las marca como «no se descifra» y
hay que volver a introducirlas. La copia de `config.db` no incluye `secrets/`: guárdalos aparte.
