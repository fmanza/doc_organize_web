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
| P2 | Excluir subcarpetas de las carpetas de trabajo al escanear: el usuario marca en el árbol de una carpeta guardada las subcarpetas que no se escanean (borradores, copias, `old/`…); se guardan con la carpeta y la vista previa las muestra como excluidas (anotado el 2026-11-07) | Hoy solo se escanea una carpeta entera; para dejar fuera una subcarpeta hay que moverla o guardar por separado cada hermana. Requiere librería: `DocumentScanner.scan_folders` solo acepta un `exclude_dir` (lo usa `ScanCommand` para la salida del propio proyecto) y `ScanOptions` no tiene exclusiones, así que sería un hueco nuevo (G41, p. ej. `ScanOptions.exclude_paths`). Decidir qué pasa con lo ya convertido de una subcarpeta que se excluye después (se conserva o cuenta como eliminado con `force`) |
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
| P2 | El error «La carpeta se solapa con otra ubicación» dice con qué ubicación choca y cómo: «está dentro de «Salida Calidad-1»» o «contiene a …». Si la que choca es de otro tenant, no da su nombre y solo dice que la carpeta ya está en otro tenant, igual que «Ya hay una ubicación con esa carpeta». Si choca con una ubicación de destino del mismo tenant, sugiere usarla como destino del proyecto con un nombre de carpeta de salidas (anotado el 2026-11-07) | `_validate_container_path` (`domain/locations/service.py`) compara con las ubicaciones de todos los tenants, pero «Ubicaciones» solo lista las del tenant actual. El mensaje no da ninguna pista, y que la carpeta esté vacía no influye. Caso real: registrar `salida_calidad/salida_calidad` como destino, dentro de «Salida Calidad-1» (`/mnt/documentation/salida_calidad`), se rechaza sin explicar por qué |
| P3 | Re-escaneos programados | Proyectos con origen vivo. Los avisos al terminar llegaron en la Fase 10 (M2) |
| P3 | Segundo factor (TOTP) y comprobación de contraseñas filtradas | Riesgos aceptados de ASVS L2 en la 1.0 ([ASVS_L2.md](../security/ASVS_L2.md)) |
| P3 | Tokens de API personales | Integraciones sin sesión de navegador |
