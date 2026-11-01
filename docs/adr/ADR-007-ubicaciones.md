# ADR-007 — Ubicaciones locales y de red

- **Estado**: Aceptado (implementado en la Fase 2, 0.3.0)
- **Fecha**: 2026-10-31

## Contexto

La web integrada de doc_organize deja escribir cualquier ruta del servidor y su explorador parte de `Path.home()`. Los
documentos están en carpetas locales y en recursos SMB/NFS de un servidor Linux (D3, D9), con ~1 TB por proyecto (D10).
Hay que limitar a qué carpetas llega la aplicación, sin guardar credenciales de red y sin que un montaje caído bloquee
la API.

## Decisión

1. **Montajes fuera de la app**: SMB/NFS se montan en el host (`/etc/fstab`, credenciales en un fichero `0600` del host)
   y se pasan al contenedor como *bind mount* bajo `DOW_LOCATIONS_ROOT` (`/mnt`), con `:ro` cuando corresponda. La app
   no ejecuta `mount` ni guarda credenciales de red.
2. **Ubicación** = carpeta bajo `/mnt` registrada por un admin, con nombre, `usage` (`source`/`destination`/`both`),
   `access` (`ro`/`rw`), `kind` (`local`/`network`, informativo) y `display_path` (solo texto). La carpeta del
   contenedor (`container_path`) se guarda resuelta y **no se puede cambiar** (otra carpeta = otra ubicación). Al
   registrarla se rechaza: fuera de `/mnt`, la propia `/mnt`, inexistente, solapada con otra ubicación o que contenga
   los volúmenes `data`/`workspace`.
3. **Resolvedor único** (`app/domain/locations/paths.py`): toda ruta que llega por la API es relativa a una ubicación;
   se rechazan rutas absolutas, UNC, letras de unidad, `\`, `..` y bytes nulos (400); después
   `resolve(strict=True)` + `is_relative_to(raíz)`, de modo que un enlace simbólico que sale de la ubicación no sirve.
   Fuera de la ubicación y no existe dan el **mismo** 404 (sin oráculo de existencia). Montaje caído → 503.
4. **Timeouts de E/S**: listados y sondeos corren en un *pool* de hilos con `location_probe_timeout_seconds`; un montaje
   colgado responde 503 en lugar de bloquear la petición.
5. **Sondeo** (`ok`/`degraded`/`unavailable`): existe y se lee, latencia de `stat`, espacio libre y, en `rw`, escritura
   y borrado de un fichero temporal. `degraded` por latencia (`location_latency_degraded_ms`), poco espacio
   (`location_min_free_gb`) o `rw` sin escritura. En la Fase 2 es bajo demanda (al registrar, al cambiar el acceso y
   con «Comprobar»); el periódico llega con el worker (Fase 3).
6. **Visibilidad**: todas las ubicaciones son `global` hasta la Fase 9 (tenants). Los usuarios ven nombre, uso, acceso
   y estado; la ruta del contenedor, la latencia y el espacio solo los ve un admin.
7. **SQLite nunca en una ubicación** (ADR-005): `config.db` y las `cache.db` viven en `data`.

## Consecuencias

- El admin del servidor monta las carpetas; el admin de la app las registra. Guía:
  [Montar carpetas de red](../guides/carpetas_de_red.md).
- Un hilo colgado en un montaje caído no se puede matar: queda ocupado hasta que el sistema operativo devuelva el
  control (el *pool* está acotado a 8 hilos).
- `/api/health` publica solo el peor estado agregado de las ubicaciones, sin nombres ni rutas.

## Notas de implementación (Fase 3, 0.4.0)

- **Sondeo periódico** en el worker cada `location_probe_interval_minutes` (administrable; 0 = desactivado). El sondeo
  bajo demanda de la Fase 2 sigue igual.
- **Borrar una ubicación** que usa algún proyecto (también borrado, que conserva su historial) responde 409.
- Las ubicaciones se montan **igual en `web` y en `worker`**: la API valida y explora; el worker lee y escribe.
