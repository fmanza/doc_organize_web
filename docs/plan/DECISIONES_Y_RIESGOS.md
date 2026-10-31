# Decisiones y riesgos

## Decisiones (2026-10-31)

| # | Pregunta | Decisión | Estado | Consecuencias en el plan |
|---|---|---|---|---|
| P1 | Host de despliegue | **Servidor Linux en producción**; Docker Desktop (Windows) **solo para desarrollo** | ✅ Confirmada | Montajes SMB/NFS en el host Linux (`/etc/fstab` + `cifs-utils`/`nfs-common`) pasados como *bind mount* bajo `/mnt`; en desarrollo, carpetas locales como volumen. GPU solo en producción Linux (NVIDIA Container Toolkit). Guía de F2 con las dos vías |
| P2 | Volumen esperado | **~100 000 documentos y ~1 TB por proyecto** como objetivo de diseño | ✅ Confirmada | Paginación en servidor `limit/offset` (máx. 500) + tablas virtualizadas; escaneo incremental `size+mtime`; `DOW_DOCUMENT_TIMEOUT_SECONDS=600`, `DOW_JOB_TIMEOUT_SECONDS=21600`; `DOW_WORKER_CONCURRENCY=1`; un fallo por documento no aborta el run. Revisar a partir de 1 M documentos (PostgreSQL) |
| P3 | Subida desde el navegador | **No en el plan base**; mejora opcional (fase 4b) | Recomendación aceptada | Sin `python-multipart`. Si se activa: destino fijo del proyecto, límite de tamaño, `python-magic`, ClamAV opcional |
| P4 | Herramienta de documentación | **Zensical** en doc_organize_web **y también en doc_organize** | ✅ Confirmada | Web: `zensical.toml` desde F0. Librería: tarea nueva **L-13b** (migrar `mkdocs.yml` → `zensical.toml`, CI `docs.yml`, `CLAUDE.md`/SHARED con `zensical build --strict` en lugar de `mkdocs build`). **mkdocs se retira por completo** (dejará de tener soporte): también el sitio de contexto de los proyectos de usuario pasa a Zensical (`MkDocsGenerator` → `SiteGenerator`, L-8) |
| P5 | Repositorio | **Ya creado y público** | ✅ Confirmada | Seguridad desde F0, no en F10 (ver «Repositorio público» abajo) |
| P6 | Idiomas | **Solo español, con i18n desde F0** | Recomendación aceptada | Todos los textos en `i18n/es/*.json`; añadir inglés = traducir |
| P7 | Retirada de la web integrada | **Deprecar en 0.12.0 (tras F8) y eliminar en 1.0.0 (tras F10)**; la web integrada queda congelada (solo hotfix) desde F0 | Recomendación aceptada | Fecha real gobernada por `PARIDAD.md`, no por calendario |
| P8 | Sitio de contexto | **`iframe sandbox` (sin `allow-same-origin`) + CSP propia** en F7; subdominio opcional en F10 si el proxy TLS lo permite | Recomendación aceptada | ADR-010 con las dos opciones; la primera implementada |

### Repositorio público: cambios respecto al plan

Al ser público desde el primer commit, se adelantan a la **Fase 0** (WD-0.4):

- Ningún secreto versionado: `secrets/` y `.env` en `.gitignore` desde el primer commit; `.env.example` sin valores reales.
- GitHub: *secret scanning* + *push protection*, **CodeQL** (Python y JavaScript/TypeScript), Dependabot *alerts* y
  *security updates*, `SECURITY.md` con canal privado de reporte (*private vulnerability reporting*).
- Protección de ramas `main`/`develop`: PR obligatorio, CI en verde, sin *force push*.
- Sin datos reales en tests, fixtures, capturas ni E2E (documentos de prueba sintéticos).
- Ejemplos de montaje con servidores ficticios (`//nas.example.internal/...`), nunca rutas internas reales.
- Licencia MIT, `CONTRIBUTING.md` y plantillas de issue/PR.
- La imagen Docker, si se publica en GHCR, solo desde *tags* firmados del CI.
- Repositorio: <https://github.com/fmanza/doc_organize_web> (público; vacío a 2026-10-31).

## Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | Montajes de red en desarrollo con Docker Desktop (Windows): las unidades mapeadas no son visibles | Resuelto por P1: en desarrollo solo carpetas locales; las pruebas de red se hacen en el servidor Linux |
| R2 | Imagen GPU muy grande y host sin NVIDIA Container Toolkit | Variante opcional; perfil `gpu`; la UI oculta la opción si no hay worker GPU vivo |
| R3 | Docling consume mucha memoria por documento | Concurrencia 1, subproceso por job, timeout por documento, límites de memoria en compose |
| R4 | Doble mantenimiento mientras conviven las dos webs | Web integrada congelada desde F0 (P7) |
| R5 | Cambios de API de la librería rompen la web | Wheel fijado + test de contrato + SemVer |
| R6 | Rendimiento en red con 1 TB (latencia de `stat`, ficheros bloqueados) | Prechequeo `size+mtime`, reintentos, errores por fichero sin abortar |
| R7 | Mover ficheros en un origen compartido afecta a otros | Por defecto `copy`/`report_only`; `move` solo en `rw` con confirmación y auditoría |
| R8 | Repositorio público: fuga de secretos o de rutas internas | Medidas de «Repositorio público» en F0 |
| R9 | Migrar doc_organize a Zensical rompe enlaces o la referencia de API (hoy `mkdocstrings`) | L-13b con `zensical build --strict`; verificar cómo genera Zensical la referencia desde *docstrings* — PENDIENTE DE VERIFICAR |
| R10 | El sitio de contexto con Zensical cambia de aspecto o de estructura respecto al de mkdocs | L-8 con test de generación (navegación por dominio, índice) y regeneración al reconstruir el contexto |
