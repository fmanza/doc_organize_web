# ADR-015 — Endurecimiento para la 1.0

- **Estado**: Aceptado (implementado en la Fase 10, 1.0.0)
- **Fecha**: 2026-11-05

## Contexto

La Fase 10 cierra la 1.0. Faltaban cinco cosas para operar la aplicación con confianza:

- limitar el abuso desde una IP;
- medirla;
- restaurar las copias de seguridad;
- que los escaneos largos no murieran por falta de memoria;
- verificar ASVS L2.

La prueba con documentos reales dio el caso de la memoria: 521 documentos con OCR y el worker a 6 GiB. El kernel lo
mató tras 2 h 13 min (`exitcode -9`, `OOMKilled`, hueco G38).

## Decisión

1. **Límite por IP en la propia aplicación**: ventana deslizante de 60 s en memoria del proceso.
   - El inicio de sesión tiene su propio cubo (`DOW_RATE_LIMIT_LOGIN`, 10) y las escrituras a `/api/v1` otro
     (`DOW_RATE_LIMIT_WRITE`, 120).
   - Al pasarse, responde 429 con `Retry-After`.
   - Se suma al bloqueo por cuenta, que no frena a quien prueba muchas cuentas desde una IP.
   - Basta mientras la API sea un único proceso uvicorn. Con varios haría falta un almacén común: se revisará si se
     escala, y no antes.
   - Las claves se acotan (100 000) contra un barrido de IP.
2. **Cuerpo de petición acotado** (`DOW_MAX_REQUEST_MB`, 16).
   - Con `Content-Length` se decide sin leer nada (413).
   - Una escritura `chunked` se rechaza (411): FastAPI se traga las excepciones al leer el cuerpo, así que contar al
     vuelo no era fiable, y los navegadores siempre mandan el tamaño.
3. **`/metrics` sin dependencias**: formato de texto de Prometheus escrito a mano.
   - Solo existe con el secreto `dow_metrics_token`. Se pide con `Bearer`, se compara en tiempo constante y, sin él,
     responde 404.
   - Las etiquetas son acotadas: método, plantilla de ruta (el prefijo se reconstruye porque `scope["route"]` es la del
     router incluido) y estado.
   - Sin nombres, usuarios ni rutas reales. Fuera de OpenAPI.
4. **Restaurar es un comando, no una pantalla**: `app.cli restore <copia> [--yes]`.
   - Sin `--yes` solo hay vista previa.
   - Se niega si hay runs en marcha o un worker vivo.
   - Guarda cada base de datos como `.pre-restore-<UTC>` y vuelca la copia con la API de backup de SQLite.
   - Solo escribe `config.db` y `projects/*/…/cache.db`: un manifiesto manipulado no escribe otra cosa en `/data`.
   - Restaurar sustituye usuarios y sesiones: no tiene sentido desde la propia aplicación que se está sustituyendo.
5. **Escaneos en tramos** (rodeo de G38, petición L-16 a doc_organize).
   - La capa anticorrupción cuenta los documentos convertidos con los `ProgressEvent`. Al llegar a
     `DOW_SCAN_RECYCLE_DOCUMENTS` (200) para con el `CancelToken`, y la caché se guarda (G16).
   - El job lanza `JobRecycle` y el subproceso sale con 75 (`EX_TEMPFAIL`).
   - El worker relanza **el mismo run**, que sigue `running`. El timeout y la cancelación cuentan desde el primer tramo.
   - El tramo nuevo lee de `runs.result["resume"]` las carpetas terminadas y la que quedó a medias. Esa carpeta se
     retoma sin «forzar» (ya vació su caché) y sin volver a contar el descubrimiento. `resume` no sale por la API.
   - Si entretanto se pidió cancelar o venció el tiempo, el worker cierra el run en vez de relanzarlo.
   - Un OOM a mitad de tramo sigue siendo `out_of_memory`, y «Continuar el escaneo» (M1) lanza otro que convierte solo
     lo que falta.
6. **Cabeceras**: HSTS de un año fuera de `development` (las cookies ya son `Secure` y `__Host-`) y `Cache-Control:
   no-store` en todo `/api`.
7. **Recursos del worker a la vista** (M3): la columna `workers.resources` (migración 0010) guarda, en cada latido, el
   límite, el pico y el uso de memoria del cgroup, los OOM y el tamaño de tramo. Va aparte de `capabilities`, que
   leen el escaneo y la ficha de capacidades.

## Consecuencias

- Una IP compartida, como un NAT de oficina o un proxy mal configurado, comparte el límite. La guía de despliegue
  explica `FORWARDED_ALLOW_IPS`.
- Un escaneo largo vuelve a cargar los modelos de Docling en cada tramo, unos segundos cada 200 documentos. Repite el
  descubrimiento de la carpeta a medias: cuesta tiempo en carpetas enormes, a cambio de no agotar la memoria.
- La restauración exige parar la aplicación. Es lo esperado en una operación así, y está guiada en la documentación.
- Riesgos aceptados de ASVS L2 en [ASVS_L2.md](../security/ASVS_L2.md): sin segundo factor ni comprobación de
  contraseñas filtradas en la 1.0.
