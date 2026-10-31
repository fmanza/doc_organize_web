# Glosario

| Término | Significado |
|---|---|
| **doc_organize** | Librería + CLI consumida (wheel fijado): escanea, convierte con Docling (OCR), deduplica, cachea y genera contexto |
| **Web integrada** | `src/doc_organize/web/` (FastAPI + Jinja): congelada, referencia de paridad; se retira en doc_organize 1.0.0 |
| **Paridad** | Inventario `docs/plan/PARIDAD.md` de pantallas, endpoints y opciones de la web integrada con la fase que los cubre |
| **Ubicación** | Carpeta raíz registrada por un admin bajo `/mnt`, local o de red, con uso (origen/destino) y acceso (`ro`/`rw`) |
| **Origen / destino** | Ubicación de la que un proyecto lee documentos / en la que escribe sus salidas |
| **Sondeo** | Comprobación de una ubicación (existe, legible, escribible, latencia, espacio): `ok`, `degraded`, `unavailable` |
| **Resolvedor de ubicaciones** | Código que convierte `location_id` + ruta relativa en ruta segura del contenedor |
| **Proyecto** | Espacio de trabajo con miembros (`owner`/`editor`/`viewer`), un origen (con subrutas) y un destino |
| **Carpeta guardada** | Subcarpeta del origen que un proyecto escanea con frecuencia |
| **Ejecución (run)** | Una operación encolada (escaneo, duplicados, contexto, IA, exportación…) con estado, progreso, logs y artefactos |
| **Cola** | `cpu` o `gpu`; cada worker atiende las suyas (`DOW_WORKER_QUEUES`) |
| **Artefacto** | Fichero producido por una ejecución en el workspace (informe JSON, ZIP, Excel, log) |
| **Workspace** | Volumen con las carpetas de las ejecuciones |
| **Manifiesto** | `run.json` de una ejecución (sin secretos) |
| **Caché** | `cache.db` de un proyecto (SQLite de doc_organize): documentos convertidos, hashes y metadatos |
| **Escaneo incremental** | Solo se reconvierten los documentos cuyo tamaño + mtime (y después hash) cambiaron |
| **Grupo de duplicados** | Conjunto de documentos exactos o similares (difusos) con uno a conservar |
| **Vista previa (modo seco)** | Ejecución que calcula lo que haría sin mover ni borrar ficheros; obligatoria antes de aplicar |
| **Contexto** | Reorganización de las salidas por dominios y taxonomía, con sitio navegable (Zensical) |
| **Taxonomía** | Plantilla (incluida o personalizada) que define dominios y categorías del contexto |
| **Manifiesto de taxonomía** | Borrador de taxonomía generado con IA a partir de los documentos |
| **Familia IA** | Grupo de ajustes IA con su credencial: uso LiteLLM, clasificación de dominio, clasificación de taxonomía, borrador de manifiesto, GitHub Copilot |
| **Capacidades de la instancia** | GPU, audio/vídeo, LibreOffice y modelos presentes en la imagen desplegada |
| **Tenant** | Organización aislada (Fase 9); hasta entonces existe solo `default` |
| **Capa anticorrupción** | `backend/app/integrations/doc_organize/`, único importador de doc_organize |
| **GAP** | Hueco de la API de doc_organize registrado en `docs/plan/DOC_ORGANIZE_GAPS.md` (`G<n>`) |
