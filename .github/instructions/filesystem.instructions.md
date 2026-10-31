---
applyTo: "backend/app/domain/locations/**,backend/app/domain/projects/**,backend/app/workspace/**,backend/app/jobs/**,backend/app/integrations/doc_organize/**"
---
# Sistema de ficheros, ubicaciones y red — reglas

> **TL;DR** — Toda ruta pasa por el resolvedor de ubicaciones: resolver, comprobar que está dentro de una ubicación
> autorizada **después** de seguir enlaces, y solo entonces comprobar existencia. SQLite nunca en red. Origen `ro`
> no se toca.

## Ubicaciones (ADR-007, Fase 2)
- Una ubicación es una carpeta raíz registrada por un admin, bajo `DOW_LOCATIONS_ROOT` (`/mnt`), con `usage`
  (`source | destination | both`), `access` (`ro | rw`), `kind` (`local | network`) y `display_path` solo informativo.
- SMB/NFS se montan **fuera de la app** (host o volumen de compose). La app no guarda credenciales de red ni ejecuta
  `mount`.
- Estado por sondeo: `ok | degraded | unavailable` (existe, legible, escritura temporal, latencia de `stat`, espacio
  libre). Una ubicación `unavailable` → `503` *problem details*, nunca un 500.

## Resolución segura de rutas
- Entrada: `location_id` + ruta relativa. Rechazar rutas absolutas, UNC (`\\servidor`), letras de unidad, `..` que
  escapen y bytes nulos.
- `Path.resolve(strict=True)` y después `is_relative_to(raíz_resuelta_de_la_ubicación)`: un enlace simbólico que sale
  de la ubicación se rechaza.
- **Autorización antes que existencia**: un usuario sin acceso recibe la misma respuesta (`404`) exista o no la
  carpeta (sin oráculo de existencia).
- Ninguna función de dominio ni de job recibe un `str` de ruta del usuario: recibe el `ResolvedPath` (o equivalente)
  que devuelve el resolvedor.
- El explorador de carpetas pagina y no sigue enlaces fuera de la ubicación; nunca parte de `Path.home()`.

## Datos y estado (ADR-005)
- `config.db` y `projects/<project_id>/cache.db` (WAL) solo en el volumen local `DOW_DATA_DIR`. **Nunca SQLite en una
  ubicación de red** (WAL no es fiable en SMB/NFS).
- Salidas del proyecto (Markdown, JSON, imágenes, duplicados, sitio) en la ubicación destino `rw`.
- Artefactos de cada ejecución en `DOW_WORKSPACE_DIR`, con rutas construidas solo con IDs.

## Robustez en red
- Reintentos con *backoff* ante `OSError` transitorios (`EIO`, `ETIMEDOUT`, `ESTALE`) hasta `DOW_NETWORK_RETRIES`.
- Timeout por documento (`DOW_DOCUMENT_TIMEOUT_SECONDS`); un fallo por documento no aborta la ejecución.
- Sin `inotify` ni *watchers*: los cambios se detectan por escaneo incremental (tamaño + mtime antes de hashear).

## Mover, copiar y borrar
- Rol autorizado (owner/editor del proyecto o admin), ubicación `rw`, vista previa previa y confirmación explícita.
- Origen `ro`: solo «informe» o «copiar a cuarentena en destino» (G6, ADR-009).
- Auditoría por fichero movido o borrado (origen, destino, usuario, run).
