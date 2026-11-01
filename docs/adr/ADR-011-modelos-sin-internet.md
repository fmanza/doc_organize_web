# ADR-011 — Modelos de Docling sin Internet

- **Estado**: Aceptado (implementado en la Fase 4, 0.5.0)
- **Fecha**: 2026-11-01

## Contexto

Docling descarga sus modelos (detección de la maquetación, tablas, OCR, visión) de Hugging Face la primera vez que
convierte un PDF o una imagen. En producción eso significa que el worker necesita salida a Internet, que el primer
escaneo tarda minutos más de lo esperado y que una versión distinta de los modelos puede aparecer sin que nadie la haya
pedido. El contenedor corre sin privilegios y con el sistema de ficheros de solo lectura (MEJORAS P1).

## Decisión

1. Los modelos viven en un **volumen `models`** (`/models`), separado de la imagen. El worker lo monta **de solo
   lectura** y corre con `HF_HUB_OFFLINE=1` y `HF_HOME=/models/hf`: no descarga nada.
2. Un servicio puntual, **`models-init`** (perfil `setup` de compose), los descarga con
   `python -m app.integrations.doc_organize.models download` (`docling.utils.model_downloader.download_models`) a
   `/models/docling` y escribe `manifest.json` con las carpetas de cada grupo: base (maquetación, tablas, RapidOCR),
   `--picture-description` (SmolVLM) y `--easyocr` (OCR con GPU). EasyOCR solo está en la imagen `runtime-gpu`, así
   que `--easyocr` lo descarga **`models-init-gpu`** (perfil `setup-gpu`), el mismo servicio con esa imagen.
3. El subproceso del job apunta Docling a esa carpeta con `DOCLING_ARTIFACTS_PATH` (`AppSettings` de Docling, prefijo
   `DOCLING_`, verificado en docling 2.142) antes de importar doc_organize, si existe el manifiesto.
4. El worker publica en sus capacidades `models_ready`, `picture_description_ready` y `gpu_ready` (GPU activa y
   EasyOCR); la API solo acepta «describir imágenes» y «usar GPU» si algún worker de la cola los confirma.
5. Sin modelos, un escaneo no falla entero: los formatos que no los necesitan (HTML, Office, TXT…) se convierten y los
   PDF e imágenes quedan como errores de conversión, con un aviso al empezar.

## Consecuencias

- La imagen no crece con los modelos (≈1–2 GB) y se actualizan sin reconstruirla: `models-init` otra vez.
- El primer arranque necesita un paso más (documentado en Despliegue) y red solo para `models-init`.
- La versión de los modelos queda fijada por la versión de Docling del lock en el momento de la descarga; al
  actualizar Docling hay que repetir `models-init`.
- doc_organize no permite indicar la carpeta de modelos en `DocumentConverter`; se usa la variable de entorno de
  Docling (hueco G17).

## Alternativas descartadas

- **Modelos dentro de la imagen**: arranca sin red, pero la imagen crece 1–2 GB y cada cambio de modelos obliga a
  reconstruirla y redistribuirla.
- **Descarga al vuelo** (comportamiento por defecto de Docling): exige Internet en el worker y hace impredecible el
  primer escaneo.
