# Inteligencia artificial

La IA es opcional. La aplicación funciona sin ella. Cuando se configura, sirve para tres cosas:

- **Clasificar con IA** los documentos que las reglas dejan sin dominio al [construir el contexto](contexto.md).
- Pedir un **borrador del manifiesto de taxonomía** a partir de una muestra de documentos.
- Ver el **uso y coste** de LiteLLM y de GitHub Copilot.

Los servicios se usan a través de un [LiteLLM Proxy](https://docs.litellm.ai/docs/simple_proxy) de tu organización
(salvo el uso de Copilot, que se consulta en la API de GitHub).

!!! warning "El contenido de los documentos sale de la aplicación"

    Al clasificar o pedir un borrador se envían al servicio configurado el **título y un extracto** de cada documento.
    No se envían rutas del servidor. Nunca se hace por defecto: cada ejecución lo pide de forma explícita y la
    pantalla lo avisa. No lo actives con documentos que no puedan salir de tu organización.

## Configuración IA (administradores)

**Administración → Configuración IA** tiene una tarjeta por servicio:

| Servicio | Para qué | Campos |
|---|---|---|
| Clasificación de dominios (un eje) | Contexto con dominios descubiertos o catálogo propio | URL, clave virtual, modelo |
| Clasificación por taxonomía (dos ejes) | Contexto con plantilla o manifiesto | URL, clave virtual, modelo |
| Borrador de manifiesto | Botón «Pedir borrador» | URL, clave virtual, modelo |
| Uso de LiteLLM | Panel de uso | URL, clave virtual |
| Uso de GitHub Copilot | Panel de uso | Usuario de GitHub, token personal (PAT) |

- Cada campo indica de dónde sale su valor: **Guardado aquí**, **Variable del servidor** (`DOC_ORGANIZE_*`, los mismos
  nombres que la web integrada de doc_organize) o **Sin valor**. Lo guardado aquí tiene prioridad.
- Las **claves y tokens** se guardan cifrados y nunca se vuelven a mostrar: solo «Guardada: …ab12» (los 4 últimos
  caracteres, o `***` si son muy cortos). Para cambiar una, escribe la nueva. Para volver a la variable del servidor,
  pulsa «Borrar valor guardado».
- La URL tiene que ser `http://` o `https://`, sin usuario ni contraseña, sin parámetros ni fragmento.
- Guardar claves exige el secreto `dow_fernet_keys` (lo crea `scripts/generate_secrets.py`). Si falta, la página lo
  avisa y solo deja guardar URL, modelo y usuario.
- Cada cambio queda en la [auditoría](usuarios_y_sesiones.md) con los nombres de los campos, nunca con las claves.

En **Administración → Ajustes** hay cinco ajustes más:

| Ajuste | Por defecto | Qué hace |
|---|---|---|
| Tiempo máximo por petición de IA | 30 s | Para clasificar documentos (el panel de uso espera como mucho 10 s) |
| Reintentos de conexión con la IA | 2 | Solo ante fallos de conexión |
| Documentos con IA por ejecución | 500 | Tope de documentos que una construcción del contexto puede enviar a la IA |
| Tiempo máximo del borrador de IA | 300 s | La petición del borrador es una sola y larga; con un modelo local puede tardar minutos (5–900) |
| Reintentos del borrador de IA | 0 | Ante un fallo de conexión o de tiempo. Reintentar un timeout vuelve a pedir la misma generación al modelo |

## Clasificar con IA

En la página **Contexto**, marca «Clasificar con IA lo que las reglas dejen sin clasificar» antes de construir.
Solo está disponible si el servicio que toca está configurado. Con dominios descubiertos o con un catálogo propio se
usa el de un eje. Con plantilla o manifiesto se usa el de dos ejes, que asigna dominio y tipo de material.

- La IA solo recibe los documentos que las reglas no supieron clasificar y solo elige entre los dominios del catálogo.
  Nunca inventa dominios nuevos.
- Si el servicio rechaza la clave, deja de llamarse en esa ejecución. También deja de llamarse tras 3 fallos de
  conexión seguidos o al llegar al tope de documentos. El contexto se construye igualmente y los documentos que
  faltan quedan sin clasificar.
- El resultado de la ejecución dice cuántos documentos se enviaron, cuántos clasificó la IA, cuántos dieron error y,
  si paró, por qué. En la lista de documentos, los que clasificó la IA llevan la marca **IA**.

## Borrador de manifiesto

En la tarjeta **Manifiesto de taxonomía** de la página Contexto, «Pedir borrador» envía una muestra de documentos
convertidos al servicio y propone dominios y tipos de material. Por defecto son 25 documentos, como mucho 60,
repartidos entre carpetas.

Es una [ejecución](ejecuciones.md) que **no guarda nada**. Al terminar, el borrador se carga en el editor: revísalo,
cámbialo si hace falta y pulsa «Guardar manifiesto». Después puedes construir el contexto con «Manifiesto del
proyecto». Lo pueden pedir los editores y propietarios. Queda en la auditoría como «Borrador de manifiesto con IA».

Si la ejecución falla con «El servicio de IA no respondió a tiempo», el servicio aceptó la petición pero el modelo no
terminó en el plazo: sube «Tiempo máximo del borrador de IA», pide una muestra más pequeña o usa un modelo más rápido.
«No se pudo conectar con el servicio de IA» es otra cosa: la URL no responde (el proxy está parado o no se alcanza).

## Uso de IA (administradores)

**Administración → Uso de IA** muestra el periodo actual de cada fuente:

- **LiteLLM**: el gasto acumulado de la clave configurada (en USD).
- **GitHub Copilot**: las peticiones premium del mes en curso, con su coste si GitHub lo indica.

Los datos se guardan 5 minutos. «Actualizar» pide datos nuevos, como mucho una vez cada 30 segundos. Si una fuente
falla o no está configurada, la otra se sigue mostrando.

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
