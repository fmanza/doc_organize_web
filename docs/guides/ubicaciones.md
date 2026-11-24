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

Solo el administrador de la instancia, en el tenant activo ([Tenants y roles](tenants_y_roles.md)).

- **Nueva ubicación**: nombre, carpeta (navega por `/mnt` y pulsa «Elegir esta carpeta»), uso, acceso
  (**solo lectura** o **lectura y escritura**), tipo (local o red), opcionalmente una ruta para mostrar (por
  ejemplo, la ruta UNC que conocen los usuarios) y, si es de origen, los
  [nombres que no se escanean](#nombres-que-no-se-escanean). La carpeta **no se puede cambiar** después.
- **Comprobar** vuelve a medir el estado. Con «lectura y escritura» también prueba a escribir y borrar un fichero
  temporal.
- **Editar** cambia nombre, ruta para mostrar, uso, acceso, tipo y, si es de origen, los nombres que no se escanean.
- **Borrar** quita la ubicación de la aplicación; **la carpeta y sus documentos no se tocan**. Pide escribir el nombre
  para confirmar. No se puede borrar una ubicación que use algún proyecto activo: al abrir el borrado se ven, con
  enlace a cada uno, y mientras haya alguno «Borrar» queda desactivado. Los proyectos borrados no cuentan: al borrarse
  sueltan sus ubicaciones (desde la 2.3.1) y conservan su historial de ejecuciones; qué ubicaciones usaban queda en la
  auditoría.

No se puede registrar la propia `/mnt`, una carpeta dentro de otra ubicación (ni al revés) ni una que contenga los
datos de la aplicación.

## Nombres que no se escanean

En una ubicación de origen (uso «Origen» u «Origen y destino»), la tarjeta **Nombres que no se escanean** de su ficha
lista los ficheros y carpetas que no se escanean en **ningún proyecto** que lea de ella. El administrador de la
instancia los edita ahí o en el formulario («Patrones (uno por línea)»); el resto de usuarios solo los ve.

- Comodines `*` y `?`, sin distinguir mayúsculas, sin `/` ni `\`; hasta 30 patrones de hasta 64 caracteres. Ejemplos:
  `~$*`, `@eaDir`, `#recycle`, `$RECYCLE.BIN`, `System Volume Information`.
- Lo ya convertido que encaje se conserva, pero «Forzar reconversión» lo borra
  ([Escaneo](escaneo.md#forzar-reconversión)).
- Un escaneo en marcha sigue con los patrones que había al lanzarlo. El cambio queda en la auditoría.

## Ajustes, capacidades y workers (administradores)

**Administración → Ajustes** permite cambiar, sin reiniciar, la duración de las sesiones, el bloqueo por intentos, la
longitud mínima de contraseña y los umbrales de las comprobaciones de ubicaciones (tiempo máximo, latencia para
«degradada» y espacio libre mínimo), el intervalo del sondeo periódico, la retención de los ficheros de las
ejecuciones y la cuota por usuario. Cada ajuste indica su origen: cambiado aquí, variable del servidor o por defecto;
«Restablecer» lo devuelve al valor del servidor.

El **worker** sondea todas las ubicaciones cada `location_probe_interval_minutes` (5 por defecto), así que el estado
se mantiene al día sin pulsar «Comprobar».

Desde la 1.6, los ajustes se agrupan en «Sesión e inicio de sesión», «Ubicaciones» y «Retención y cuotas»; los de la
IA están en **Administración → IA → Parámetros** ([IA](ia.md)).

En **Administración → Información** (hasta la 1.5, al final de Ajustes), la **ficha de capacidades** muestra si esta instalación puede hacer OCR con GPU, convertir audio y vídeo y leer `.xls`
antiguos (LibreOffice). La calcula el worker al arrancar y cada hora; «Volver a comprobar» se lo pide en su siguiente
latido. Debajo, la tabla de **workers** indica cuáles están en marcha y sus colas.
