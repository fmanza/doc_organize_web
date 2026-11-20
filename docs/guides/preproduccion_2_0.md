# Preproducción de la 2.0

Runbook para probar la 2.0 con datos reales **antes** de actualizar producción, sin tocar
producción ni los documentos. Tres pruebas, cada una con su script:

1. **Migraciones de ida y vuelta** sobre una copia de la base de datos de producción.
2. **Diagnóstico sin errores** en una instancia aislada.
3. **Contexto y entregas** (Excel, sitio sin conexión y paquete para IA) sobre una copia, o un montaje de solo lectura,
   de los documentos (por ejemplo, CALIDAD_VD).

!!! danger "Reglas"
    - Producción no se para ni se cambia. La base de datos real solo se lee para copiarla, con `app.cli backup`, y
      las copias se borran al terminar.
    - Los documentos se montan **de solo lectura** (`:ro`) y la ubicación de origen se registra de solo lectura. Las
      salidas van a una carpeta nueva y vacía, fuera de los documentos.
    - La instancia de preproducción es **otro proyecto de Compose** (`dow-preprod`), con otros volúmenes y otro puerto
      (18090), y nunca carga `docker-compose.override.yml`.
    - Ninguna clave se escribe en la línea de órdenes ni se imprime: la de LiteLLM se lee de una variable de entorno.

## Requisitos

- El repositorio en la rama que se prueba, con Docker y `uv` en el equipo.
- El nombre del contenedor web de producción (por defecto `doc_organize_web-web-1`).
- Una carpeta nueva y vacía para las salidas (`DOW_PREPROD_OUT`) y la ruta de los documentos (`DOW_PREPROD_SOURCE`).
  Si se usa una copia de CALIDAD_VD, mejor; si no, se monta el original de solo lectura.

En Windows, ejecuta los scripts desde Git Bash con `export COMPOSE_PATH_SEPARATOR=";"` (`up.sh` y `down.sh` usan `:`
para separar los ficheros de Compose si no). Los tres scripts se han probado con datos sintéticos: una instancia
aislada de los E2E y la carpeta `dev-data/e2e/w9`.

## 1. Migraciones de ida y vuelta

```bash
sh scripts/preprod/roundtrip.sh doc_organize_web-web-1
```

`app.cli backup --dest` (existe desde la 0.6.0) hace una copia coherente de `config.db` (y de las cachés) en el `/tmp`
del contenedor de producción, que es memoria (`tmpfs`): no escribe en el volumen de datos. El script la saca al host
con `tar` y la borra del contenedor. Después la prueba con `backend/scripts/migration_roundtrip.py`
(sube a `head`, lee todos los modelos, baja a la revisión de partida y compara tabla a tabla), sobre otra copia
temporal. Al salir borra la copia del host; si Windows no deja borrar la temporal, lo dice con su ruta para
borrarla a mano.

**Correcto** si termina con «0 distintas, sobran []» y código 0. Solo imprime tablas, recuentos y revisiones.

## 2. Instancia aislada y diagnóstico

```bash
export COMPOSE_PATH_SEPARATOR=";"          # solo en Windows
export DOW_PREPROD_SOURCE="/ruta/a/la/copia/de/CALIDAD_VD"
export DOW_PREPROD_OUT="/ruta/a/una/carpeta/nueva"
sh scripts/preprod/up.sh                   # construye la imagen del árbol y levanta web y worker en :18090
```

Crea el admin de la instancia aislada (la contraseña por la entrada estándar, como se indica al final de `up.sh`).
Los modelos de Docling, si hacen falta (PDF e imágenes), se descargan en el volumen `dow-preprod_models` como en
producción, con las mismas variables de `up.sh` (`COMPOSE_PROJECT_NAME=dow-preprod`, `COMPOSE_FILE`, `DOW_PREPROD_*`):
`docker compose --profile setup run --rm models-init`.

## 3. Contexto y entregas

```bash
export DOW_PREPROD_PASSWORD=…              # la del admin de la instancia aislada (no se imprime)
python backend/scripts/preprod_smoke.py --url http://127.0.0.1:18090 --user preprod-admin \
    --source origen --folder "" --destination salidas --template calidad \
    --ai-url http://host.docker.internal:4000 --ai --diagnostics-ai
```

El script hace, por la API:

- el **diagnóstico** (con `--diagnostics-ai`, también los modelos de cada tarea, el de embeddings incluido);
- las ubicaciones (origen **de solo lectura**, `/mnt/origen`; salidas, `/mnt/salidas`) y un proyecto nuevo;
- el **escaneo** y la **construcción del contexto** (con la plantilla dada y, con `--ai`, la IA para lo que las
  reglas no clasifican);
- las tres **entregas**: descarga cada fichero y comprueba que su SHA-256 es el que muestra la aplicación.

Sin `--ai-url`, la instancia no tiene IA y se construye solo por reglas. Con él, la clave se lee de la variable
`LiteLLM` (o la de `--ai-key-env`) y no aparece en ninguna salida. Solo se imprimen recuentos, estados y huellas.

**Correcto** si termina con «Todo correcto.» y código 0. Después revisa en la web aislada
(`http://127.0.0.1:18090`) el contexto, «Revisar clasificación» y «Calidad». Comprueba también que el ZIP del sitio sin
conexión no lleva ningún original ni `.json` de conversión.

## Limpieza

```bash
sh scripts/preprod/down.sh                 # para dow-preprod y borra SUS volúmenes
```

Después borra a mano `DOW_PREPROD_OUT` y la copia de los documentos, si la hiciste. Producción no ha cambiado.
