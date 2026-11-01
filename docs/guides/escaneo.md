# Escaneo y conversión

El **escaneo** busca los documentos de las carpetas de origen de un [proyecto](proyectos.md) y convierte a Markdown y
JSON los **nuevos o modificados** en su carpeta de salidas. Es una [ejecución](ejecuciones.md): sigue aunque cierres
la pestaña y su progreso se ve en vivo.

Abre el proyecto y pulsa **Escanear** (los lectores ven la pantalla, pero solo los editores y propietarios escanean).

## Carpetas

La tabla muestra las **carpetas de origen** del proyecto: si ya se escaneó cada una («escaneada»), cuándo fue el último
escaneo (enlaza a la ejecución) y si ha dejado de existir en el origen («no existe»).

- Por defecto se escanean **todas**; desmarca las que no quieras esta vez.
- **Añadir carpeta** y **Quitar** (propietarios, sin ejecuciones en marcha). Una carpeta nueva **no puede estar dentro
  de otra del proyecto ni contenerla**: cada documento se convierte a una ruta que depende de la carpeta escaneada, y
  si las carpetas se anidaran el mismo documento acabaría en dos salidas distintas.
- Quitar una carpeta **no borra nada**: si ya se escaneó, sus salidas siguen en el destino.

## Opciones

Cada opción tiene un botón **?** con una explicación y un ejemplo. Las que la instancia no puede atender aparecen
desactivadas con el motivo (lo publica el worker: ver **Administración → Ajustes → Capacidades**).

| Opción | Qué hace | Necesita |
|---|---|---|
| OCR | Reconoce el texto de imágenes y PDF escaneados (activado por defecto) | Modelos de Docling |
| Usar GPU para el OCR | OCR con EasyOCR en la GPU; el escaneo va a la cola `gpu` | Un worker con GPU y los modelos de EasyOCR |
| Incluir audio y vídeo | Transcribe grabaciones con Whisper | Whisper y ffmpeg en la imagen |
| Extraer imágenes | Guarda las imágenes de cada documento en `img/` junto a su Markdown | — |
| Describir imágenes | Añade una descripción de cada imagen con un modelo de visión (lento) | El modelo de visión descargado |

## Incremental

Un escaneo solo convierte lo **nuevo o modificado** (compara el contenido con la caché del proyecto); el resto aparece
como «Sin cambios». Repetir un escaneo sin cambios en el origen no convierte nada. Los documentos que fallaron se
reintentan solos en los escaneos siguientes, hasta un límite («no se reintenta» en la página de errores).

Con varias carpetas, la aplicación las escanea **una detrás de otra**, y cada una es independiente: tiene su propia
caché y sus salidas van a su propia subcarpeta (`Conversión/<carpeta>/…` dentro de la carpeta de salidas del
proyecto). Así, dos documentos con el mismo nombre en carpetas distintas (`2024/facturas/enero.pdf` y
`2025/facturas/enero.pdf`) nunca se pisan. Si algo falla a mitad (un corte de la red, el tiempo máximo), lo convertido
en las carpetas ya terminadas queda guardado; si falla una carpeta, se siguen escaneando las demás y la ejecución
termina como fallida indicando cuántas no se pudieron escanear.

## Progreso y resultado

El detalle de la ejecución muestra la fase (**Buscando documentos**, **Convirtiendo**, **Aplicando OCR**), cuántos
documentos van de cuántos y el documento actual, con rutas relativas al origen. Al terminar:

| Dato | Significa |
|---|---|
| Documentos encontrados | Todos los documentos de las carpetas escaneadas |
| Nuevos / Modificados / Sin cambios | Comparados con la caché |
| Convertidos | Convertidos en esta ejecución |
| Documentos con errores | No se pudieron convertir (ver errores) |
| Avisos | Carpetas que ya no existen y otros avisos (en «Avisos» del detalle) |

**Cancelar** detiene el escaneo entre dos documentos: lo ya convertido se conserva y el siguiente escaneo continúa
desde ahí.

## Errores

**Errores del último escaneo** (en la pantalla de escaneo) o el enlace «Ver los N documentos con errores» del detalle
de una ejecución muestran, paginados, el documento, el error y cuántas veces seguidas ha fallado.

## Forzar reconversión

En la zona roja (solo propietarios): vacía la caché del proyecto y vuelve a convertir **todos** los documentos de
**todas** las carpetas con las opciones elegidas. Además **borra las salidas de los documentos que ya no están** en el
origen. Por eso sigue los mismos pasos que mover o borrar un proyecto: una **vista previa** sin cambios (cuántos
documentos hay en la caché, cuántos ya no existen y el tamaño de las salidas) y después escribir el nombre del
proyecto. La vista previa caduca a los 15 minutos o si cambian las carpetas del proyecto.

Actúa carpeta a carpeta: las salidas de carpetas que quitaste del proyecto no se tocan. Por seguridad, no se fuerza
nada si alguna carpeta no se puede leer (un montaje de red caído haría creer que sus documentos ya no existen) o si la
caché tiene documentos de fuera de su carpeta; en ese caso, usa «Vaciar histórico» y vuelve a escanear.

## Modelos y GPU (administradores)

Los PDF y las imágenes necesitan los **modelos de Docling**; la aplicación no los descarga mientras convierte (el
worker trabaja sin Internet). Se descargan una vez al volumen de modelos:

```bash
docker compose --profile setup run --rm models-init
# Con el modelo de visión (describir imágenes):
docker compose --profile setup run --rm models-init download --picture-description
# Para el worker con GPU (EasyOCR), con su imagen:
docker compose --profile setup-gpu run --rm models-init-gpu
```

Sin modelos, los documentos de texto (HTML, Word, TXT…) se convierten igual y los PDF y las imágenes aparecen como
errores; la ficha de capacidades lo indica. El worker con GPU se describe en [Despliegue](despliegue.md).
