# Mejoras propuestas (buenas prácticas)

Prioridad: **P1** entra en el plan base · **P2** recomendable en su fase · **P3** opcional.

## Arquitectura y librería

| P | Mejora | Por qué |
|---|---|---|
| P1 | Separar estado (SQLite) de salidas (ficheros), ADR-005 | SQLite+WAL en SMB/NFS corrompe la caché; hoy `cache.db` vive en la raíz del proyecto |
| P1 | Deduplicación en dos pasos (vista previa → confirmar), ADR-009 | Hoy «Deduplicar» en el escaneo mueve ficheros sin revisión y confunde la página de revisión |
| P1 | Runs persistentes con SSE en lugar de WebSockets ligados a la pestaña | Cerrar el navegador ya no cancela un escaneo de horas; historial y auditoría uniformes |
| P1 | Bloqueo por proyecto en BD | Sustituye el `set` en `app.state` protegido solo por el GIL (ADR-004 de doc_organize, roto con *free-threading*) |
| P1 | Fachada pública + SemVer + `py.typed` + wheel con hash | Permite fijar la librería como util_bbdd y detectar roturas en CI |
| P2 | `ScanOptions` en lugar de 12 parámetros posicionales | Evita errores de orden al llamar |
| P2 | Escaneo incremental por `size+mtime` antes del hash | En red, hashear todo cada vez es lo más caro |
| P2 | Cola GPU separada | Un escaneo con OCR GPU no bloquea los trabajos ligeros |
| P3 | Búsqueda de texto completo (FTS5) sobre el Markdown convertido | Valor directo para el usuario; portable a PostgreSQL (`tsvector`) |

## Seguridad

| P | Mejora | Por qué |
|---|---|---|
| P1 | Resolvedor único de rutas con allowlist, enlaces resueltos, autorización antes de existencia | Superficie principal de la app: rutas del servidor |
| P1 | Visor Markdown saneado (DOMPurify) y vistas de documentos con `Content-Type` fijo, `nosniff` y `Content-Disposition` | Documentos convertidos son contenido no confiable (XSS) |
| P1 | Sitio de contexto aislado (ADR-010) | El sitio generado trae JS propio |
| P1 | Credenciales IA cifradas, nunca devueltas; rotación de claves Fernet | Hoy ya cifradas; se añade rotación y redacción en logs |
| P1 | Contenedor no root, solo lectura, sin capacidades, sin Internet para modelos (ADR-011) | Docling descarga modelos al vuelo si no se precargan |
| P2 | Límites de recursos por job (memoria, timeout por documento) | PDFs malformados o enormes pueden agotar el worker |
| P2 | ASVS L2 completo en F10 | Igual que util_bbdd_web |

## Calidad, operación y UX

| P | Mejora | Por qué |
|---|---|---|
| P1 | Contrato OpenAPI → cliente TS generado y comprobado en CI | Evita la deriva de tipos |
| P1 | Estados de carga/vacío/error/sin permiso en cada vista; WCAG 2.2 AA; i18n | Estándar de util_bbdd_web |
| P1 | `/api/health` con worker, ubicaciones y modelos | Diagnóstico inmediato de montajes caídos |
| P2 | Métricas: documentos/minuto, errores de conversión, cola por tipo | Dimensionar OCR/GPU |
| P2 | Backup de `config.db` y de las `cache.db` | La caché evita reconvertir horas de OCR |
| P2 | Importador opcional desde la web antigua (aunque se empiece limpio) | Si más adelante interesa recuperar usuarios/ajustes |
| P3 | Re-escaneos programados y notificaciones | Proyectos con origen vivo |
