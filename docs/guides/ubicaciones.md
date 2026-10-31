# Ubicaciones

Una **ubicación** es una carpeta de documentos que la aplicación puede usar: como **origen** (de donde se leen los
documentos), como **destino** (donde se escriben las salidas) o ambas. Puede ser local o de red; las de red las monta
el administrador del servidor ([Montar carpetas de red](carpetas_de_red.md)).

## Ver y explorar (todos los usuarios)

**Ubicaciones** lista las disponibles con su estado:

| Estado | Significa |
|---|---|
| ● Disponible | Responde con normalidad |
| ▲ Degradada | Responde, pero lenta, con poco espacio libre o sin permiso de escritura siendo de lectura y escritura |
| ■ No disponible | No existe, no se puede leer o no responde a tiempo (p. ej. el recurso de red está caído) |
| ? Sin comprobar | Aún no se ha comprobado |

Pasa por encima del estado para ver el motivo. Abre una ubicación para explorar sus carpetas: solo puedes moverte
dentro de ella. Si la ubicación no está disponible, el explorador lo indica y no muestra nada.

## Registrar y gestionar (administradores)

- **Nueva ubicación**: nombre, carpeta (navega por `/mnt` y pulsa «Elegir esta carpeta»), uso, acceso
  (**solo lectura** o **lectura y escritura**), tipo (local o red) y, opcionalmente, una ruta para mostrar (por
  ejemplo, la ruta UNC que conocen los usuarios). La carpeta **no se puede cambiar** después.
- **Comprobar** vuelve a medir el estado. Con «lectura y escritura» también prueba a escribir y borrar un fichero
  temporal.
- **Editar** cambia nombre, ruta para mostrar, uso, acceso y tipo.
- **Borrar** quita la ubicación de la aplicación; **la carpeta y sus documentos no se tocan**. Pide escribir el nombre
  para confirmar.

No se puede registrar la propia `/mnt`, una carpeta dentro de otra ubicación (ni al revés) ni una que contenga los
datos de la aplicación.

## Ajustes y capacidades (administradores)

**Administración → Ajustes** permite cambiar, sin reiniciar, la duración de las sesiones, el bloqueo por intentos, la
longitud mínima de contraseña y los umbrales de las comprobaciones de ubicaciones (tiempo máximo, latencia para
«degradada» y espacio libre mínimo). Cada ajuste indica su origen: cambiado aquí, variable del servidor o por defecto;
«Restablecer» lo devuelve al valor del servidor.

La **ficha de capacidades** muestra si esta instalación puede hacer OCR con GPU, convertir audio y vídeo y leer `.xls`
antiguos (LibreOffice). La primera comprobación tarda unos segundos.
