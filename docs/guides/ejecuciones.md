# Ejecuciones

Todo lo que tarda (escanear, convertir, deduplicar, mover o borrar) se hace como una **ejecución**: la aplicación la
pone **en cola** y el *worker* la ejecuta en segundo plano. Por eso puedes **cerrar la pestaña**: la ejecución sigue y
al volver ves cómo va.

## Estados

| Estado | Significa |
|---|---|
| … En cola | Esperando a que haya un worker libre |
| ▶ En marcha | Ejecutándose; el detalle muestra el progreso en vivo |
| ✓ Terminada | Acabó bien; mira el resultado y los ficheros |
| ✕ Fallida | Acabó con un error; el detalle explica el motivo |
| ■ Cancelada | Se canceló |

En cada proyecto solo puede haber **una operación que escriba a la vez** (mover, vaciar, borrar y, desde la Fase 4,
escanear). Si lanzas otra, la aplicación avisa de que hay una en curso. Las vistas previas y las pruebas no cuentan.

## Historial

**Ejecuciones** lista las de tus proyectos de la más reciente a la más antigua, con filtros por estado y operación;
desde un proyecto, «Ver todas» muestra solo las suyas. Cada fila es una ejecución completa: operación, proyecto,
estado, cuándo se lanzó, cuánto duró y quién la lanzó.

## Detalle

- **Progreso**: fase, elementos procesados (de un total, si se conoce) y elemento actual. Se actualiza solo; los
  lectores de pantalla anuncian los cambios de fase y cada 10 %.
- **Avisos**: mensajes de la operación (p. ej. «Cancelación solicitada»).
- **Resultado**: recuentos al terminar (ficheros, tamaños, documentos convertidos…). En un escaneo, enlace a los
  documentos con errores ([Escaneo](escaneo.md)).
- **Ficheros**: lo que deja la ejecución (resultados y su registro, `run.log`, sin rutas internas del servidor ni
  trazas de error, con un máximo de 20 MB) para descargar. Se borran pasados
  `run_retention_days` días (30 por defecto); el historial se conserva.

## Cancelar

«Cancelar ejecución» (quien la lanzó, un propietario del proyecto o un administrador). Si estaba en cola, se cancela
al momento. Si estaba en marcha, se detiene en el siguiente punto seguro y lo ya hecho se conserva; si no responde en
30 segundos, el worker la termina.

## Si algo falla

| Mensaje | Qué pasó |
|---|---|
| El worker dejó de responder | El worker se cayó con la ejecución en marcha; se marcó al volver a arrancar |
| El worker se detuvo | Se paró el worker (p. ej. en un despliegue) |
| Superó el tiempo máximo; se guardó lo hecho hasta parar | Duró más de `DOW_JOB_TIMEOUT_SECONDS` (6 h por defecto). Se pidió una parada ordenada: un escaneo conserva lo convertido y el siguiente continúa desde ahí |
| El worker no puede atender alguna de las opciones del escaneo | El worker que la reclamó no tiene GPU, audio/vídeo o el modelo pedido |
| La ubicación «…» no está disponible | El origen o el destino no respondía |

Se puede volver a lanzar. Si una ejecución se queda en cola mucho tiempo, comprueba en **Inicio** que el worker está
«en marcha».
