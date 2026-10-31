---
applyTo: "backend/**,frontend/src/**,docker/**,docker-compose*.yml"
---
# Seguridad — reglas obligatorias

## Identidad (Fase 1, ADR-003)
- Contraseñas con Argon2id (`pwdlib`); política mínima de longitud y contraseñas comunes; bloqueo temporal tras
  intentos fallidos.
- Sesión de servidor (tabla `sessions`) en cookie `__Host-` `HttpOnly; Secure; SameSite=Lax; Path=/`; rotación al
  iniciar sesión; caducidad por inactividad y absoluta; revocación por el admin.
- CSRF: token de doble envío firmado (cookie legible + cabecera `X-CSRF-Token`) en todo método no seguro.
- Sin CORS: frontend y API comparten origen. Sin tokens en `localStorage`.
- El primer admin se crea por CLI (`app.cli create-admin`); no existen credenciales por defecto.

## Autorización
- Cada consulta filtra por pertenencia al proyecto (y, desde la Fase 9, por `tenant_id`) en el **servicio**, no solo
  en el router.
- Recurso ajeno → `404` (no revelar existencia de proyectos, ejecuciones ni carpetas).
- Ubicaciones visibles solo según su `visibility`; rutas siempre por el resolvedor (`filesystem.instructions.md`).

## Secretos (ADR-004)
- Credenciales IA (LiteLLM, GitHub Copilot) cifradas con Fernet (MultiFernet para rotación); clave por Docker secret
  `dow_fernet_keys`. Nunca se devuelven: solo «configurado» + últimos 4 caracteres.
- Nunca en respuestas, logs, `run.json`, mensajes de error ni excepciones re-lanzadas: sanear con el saneador común
  y registrar solo `type(exc).__name__`.

## Documentos no confiables
- Todo documento de una ubicación es entrada no confiable: se convierte en el subproceso del job, con timeout por
  documento y límites de memoria del contenedor; nunca en el proceso de la API.
- Markdown y JSON convertidos se sirven con `Content-Type` fijo y `X-Content-Type-Options: nosniff`; el frontend los
  sanea (DOMPurify).
- Sitio de contexto (Zensical) aislado: `iframe sandbox` sin `allow-same-origin` + CSP propia (ADR-010).
- Exportaciones ZIP en streaming con tamaño previsto y cuota (`DOW_USER_QUOTA_MB`).
- Sin subida desde el navegador en el plan base (P3).

## Conexiones salientes
- Solo hacia los endpoints IA configurados por un admin (LiteLLM, API de GitHub), con timeouts, reintentos acotados
  y presupuesto por run. Sin URLs arbitrarias de usuario.
- Modelos de Docling/OCR/Whisper precargados: `HF_HUB_OFFLINE=1` en runtime (ADR-011).

## Workspace y descargas
- Rutas construidas solo con IDs; `resolve()` + `is_relative_to(raíz_del_run)` antes de servir.
- `Content-Disposition: attachment` en descargas.

## Cabeceras y transporte
- CSP estricta (`default-src 'self'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
  `X-Frame-Options: DENY` (salvo el visor del sitio), HSTS detrás del proxy TLS.

## Contenedor
- Usuario no root (uid 10001), `read_only`, `tmpfs`, `cap_drop: ALL`, `no-new-privileges`, puertos en `127.0.0.1`
  por defecto, secretos solo por Docker secrets, imágenes con versión exacta; ubicaciones montadas con `ro` cuando la
  ubicación lo sea.

## Repositorio público
- Sin secretos, rutas internas, nombres de servidores reales ni documentos reales en código, tests, fixtures,
  ejemplos o capturas.
