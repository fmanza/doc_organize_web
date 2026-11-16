# Medición: propiedades de los originales al construir el contexto, en red

Medición W0 del plan `.ai/sessions/2026-11-16-admin-ia-y-1.6.0/PLAN.md`, hecha el 2026-11-16 con
`backend/scripts/bench_context_network.py` y doc_organize 1.5.0.

## Qué se mide

Desde doc_organize 1.5.0, `ContextBuilder.build()` abre cada original, de uno en uno, para leer su autor, descripción
y palabras clave (`read_document_properties`). Es lo único que la 1.5.0 añadió al coste de construir el contexto que
depende de dónde estén los originales. El script solo lee: no escanea, no convierte y no escribe en el origen.

## Entorno

| | |
|---|---|
| Origen | Recurso SMB de un NAS doméstico, carpeta de documentación de calidad |
| Contenido | 3096 ficheros, 2613 PDF/Office (4,2 GB en total) |
| Cliente | Windows 11, Python 3.12.15, doc_organize 1.5.0 (entorno del backend de la web) |
| Red | Latencia de `stat` (mediana): 9 ms en red, 0,03 ms en local |
| Muestra | 200 ficheros por pasada, aleatorios y sin repetir entre pasadas (semilla 1): 125 PDF, 39 DOCX, 21 XLSX, 14 PPTX, 1 XLSM |

**No medido**: NFS, y el cliente CIFS de Linux de un worker en Docker. No hay otro recurso disponible.

## Resultados (ms por documento)

| Pasada | Hilos | Total 200 docs | Efectivo por doc | Mediana | p95 | Máx |
|---|---|---|---|---|---|---|
| Red, primera lectura | 1 | 16,3 s | 81,7 | 55,2 | 140,9 | 763,9 |
| Red, primera lectura | 4 | 6,6 s | 32,8 | 94,4 | 203,0 | 1192,7 |
| Red, primera lectura | 8 | 6,0 s | 30,2 | 171,2 | 446,3 | 1039,0 |
| Red, repetida tras 15 s | 1 | 12,4 s | 62,0 | 42,6 | 97,2 | 739,5 |
| Local, primera lectura | 1 | 4,6 s | 23,2 | 7,9 | 20,5 | 702,1 |
| Local, repetida (80 docs, prueba aparte) | 1 | — | — | 0,4 | 0,8–0,9 | — |

Por tipo, red y primera lectura (mediana / p95): PDF 68 / 174; DOCX 37 / 90; PPTX 50 / 69; XLSX 40 / 51.

## Lectura

1. **La red multiplica el coste por 7** con la misma condición en los dos lados (primera lectura): mediana de 55 ms en
   red frente a 8 ms en local. Frente a la lectura repetida en local (0,4 ms, el dato del CHANGELOG de la web 1.5.0),
   el factor es de más de 100.
2. **La primera apertura en local tampoco es gratis**: unos 7 ms en Windows con un fichero recién copiado (antivirus en
   tiempo real); la segunda baja a 0,4 ms. El «menos de 0,5 ms» del CHANGELOG es correcto, pero solo para lecturas
   repetidas.
3. **Los máximos no son de red**: el XLSM de 2,4 MB (700 ms) y un PDF de 2 MB (650 ms) cuestan casi lo mismo en local.
   Es tiempo de proceso (pdfium, descompresión), no de E/S.
4. **La caché SMB caliente apenas ayuda** (mediana de 55 a 43 ms): el coste lo marcan las idas y vueltas al abrir el
   fichero y leer unos bloques (unas 6 veces la latencia de un `stat`), no el volumen de datos.
5. **Leer en paralelo compensa hasta 4 hilos**: de 81,7 a 32,8 ms efectivos por documento (2,5×). Con 8 hilos solo se
   gana un 8 % más, y la latencia de cada lectura se dispara (mediana de 171 ms): el NAS se satura.
6. **Pero PDFium no admite varios hilos a la vez** (documentación de pypdfium2 5.14, «Incompatibility with Threading»).
   Las pasadas con hilos llamaron a PDFium en paralelo sin fallar, pero eso no se puede llevar a la librería tal cual.
   Las cifras con hilos son el **techo** de la mejora: con OOXML (40 % de la muestra) se alcanza en hilos; con PDF hace
   falta otra vía (ver Decisión).

## Estimación para toda la carpeta (2613 documentos)

| Modo | Coste añadido por construcción del contexto |
|---|---|
| Secuencial (doc_organize 1.5.0) | ≈ 3 min 34 s |
| 4 hilos | ≈ 1 min 26 s |
| 8 hilos | ≈ 1 min 19 s |

Para comparar: el listado de la carpeta tarda 2,7 s; la conversión de esos documentos, horas.

## Decisión

Supera el umbral del plan (p95 de 141 ms > 20 ms; red 7× local > 3×):

- Se abre **G44** en `DOC_ORGANIZE_GAPS.md`: leer las propiedades de los originales en paralelo, con un límite
  (4 por defecto, configurable) y **sin llamar a PDFium desde dos hilos a la vez**. Vías para PDF, a decidir en la
  librería: leer los bytes del PDF en hilos (la E/S, que es lo caro en red) y extraer las propiedades de memoria bajo un
  cerrojo; o un pool de procesos. La primera lee el fichero entero (mediana de la muestra < 1 MB), así que hay que
  medirla antes de elegirla.
- La fase L5 de doc_organize 1.6.0 (metadatos de los sin clasificar, G42) no amplía la lectura sin G44: G44 entra en
  la 1.6.0 antes o junto con L5.
- Aunque el coste existe, no bloquea: 3,5 min sobre una construcción que ya lee el `.json` de cada documento, y con
  G44 queda en torno a 1,5 min.

## Cómo repetirla

```powershell
cd backend
.venv\Scripts\python.exe scripts\bench_context_network.py '\\SERVIDOR\recurso\carpeta' --sample 200 --report ..\build\logs\w0.json
```

Desde PowerShell: Git Bash estropea las rutas UNC. Sale con 2 si se supera el umbral. Desde esta medición, el script
añade una pasada `local-repetida`.

## G44: estrategias para leer en paralelo (2026-11-16)

Mismo NAS y equipo; 200 ficheros distintos por pasada, ninguno leído en la medición anterior (semilla 2).
`backend/scripts/bench_properties_strategies.py`; resultado en `build/logs/g44.json` y `g44.md`.

| Estrategia | Hilos | ms/doc efectivo | p50 | p95 | 2613 documentos |
|---|---|---|---|---|---|
| Secuencial (1.5.0) | 1 | 87,6 | 64 | 254 | 229 s |
| Hilos sin cerrojo (inseguro, solo referencia) | 4 | 32,4 | 107 | 289 | 85 s |
| Cerrojo con el PDF abierto por ruta | 4 | 66,0 | 198 | 780 | 173 s |
| **Bytes en el hilo, análisis bajo cerrojo (opción A)** | **4** | **28,2** | 97 | 210 | **74 s** |
| Opción A | 8 | 27,4 | 181 | 466 | 72 s |
| Pool de procesos (opción B) | 4 | 38,0 | 110 | 356 | 99 s |

- La opción A es tan rápida como los hilos sin cerrojo: lo caro es la E/S de red, no el análisis. En ninguna pasada
  hubo dos llamadas a PDFium a la vez.
- Abrir el PDF por ruta bajo el cerrojo deja la E/S de red serializada: solo mejora por los ficheros de Office.
- Con 8 hilos apenas baja el total y la lectura más lenta se duplica: el NAS se satura.
- Decisión: **opción A con 4 hilos** (doc_organize 1.6.0, `ContextBuilder(properties_concurrency=4)`). Una
  construcción de 2613 documentos pasa de unos 3,8 min a algo más de 1 min en leer las propiedades.

```powershell
cd backend
.venv\Scripts\python.exe scripts\bench_properties_strategies.py '\SERVIDOR\recurso\carpeta' --exclude-report ..\build\logs\w0.json --report ..\build\logs\g44.json
```
