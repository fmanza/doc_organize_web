# ADR-010 — Sitio de contexto aislado

- **Estado**: Aceptado (implementado en la Fase 7, 0.8.0)
- **Fecha**: 2026-11-02

## Contexto

El contexto de un proyecto genera un sitio estático con Zensical (doc_organize 0.13.0, L-8) a partir del Markdown de
los documentos convertidos. Ese Markdown es **contenido no confiable**: el HTML incrustado en un documento llega tal
cual al sitio (comportamiento por defecto de Zensical; doc_organize solo escapa los títulos del `nav` y `site_name`).
Si el sitio se sirviera en el origen de la app, un documento con `<script>` podría usar la sesión de quien lo abre
(llamar a la API, leer la cookie CSRF, cambiar plantillas si es admin).

La cookie de sesión es `HttpOnly`, `Secure` y `SameSite=Lax` (ADR-003). Un documento en `sandbox` sin
`allow-same-origin` tiene un origen opaco: sus peticiones son de otro sitio y el navegador **no** envía esa cookie, así
que el sitio no puede servirse con la sesión. Un subdominio propio aislaría aún más, pero exige DNS, TLS y proxy
adicionales en cada despliegue.

## Decisión

Decisión C1 del mantenedor (Fase 7): el sitio se sirve **en el mismo host** con una URL con capacidad y una CSP
`sandbox` propia.

1. `POST /api/v1/projects/{id}/context/site-session` (cualquier miembro, con sesión y CSRF) devuelve
   `/site/<token>/` y su caducidad. El token es `project_id.session_id.caducidad.firma`, con firma
   `HMAC-SHA256` con una subclave derivada de `app_secret_key` solo para este uso, sobre
   `"site|proyecto|sesión|hash del token de sesión|caducidad"`. Caduca en una hora (nunca
   después que la sesión) y no se guarda.
2. `GET /site/<token>/<ruta>` (fuera de `/api`, sin cookie) comprueba en cada petición la firma, la caducidad, que la
   sesión sigue activa (no caducada ni del usuario desactivado) y que el usuario sigue siendo miembro del proyecto.
   Cualquier fallo da el mismo 404. Ligar la firma al hash del token de sesión invalida el acceso al cerrar la sesión,
   aunque se reutilice su id.
3. Los ficheros se leen de `<carpeta del proyecto>/site` a través del resolvedor de ubicaciones. `site/` debe ser una
   carpeta real, y el fichero, una vez abierto, seguir dentro (`O_NOFOLLOW` y comprobación del descriptor). Los tipos
   salen de una lista blanca; lo demás se descarga (`application/octet-stream` y `attachment`). Hay un límite de 64 MB
   por fichero.
4. Toda respuesta bajo `/site/` (también los errores) lleva:
   - `Content-Security-Policy: sandbox allow-scripts allow-popups; default-src 'self';
     script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;
     connect-src 'self'; worker-src 'self' blob:; object-src 'none'; form-action 'none'; base-uri 'self';
     frame-ancestors 'self'`;
   - `X-Frame-Options: SAMEORIGIN`, para que la SPA lo pueda enmarcar y nadie más;
   - `Referrer-Policy: no-referrer`, para que el token no salga en los enlaces externos;
   - `Cross-Origin-Resource-Policy: cross-origin` y `Access-Control-Allow-Origin: *`, porque el documento es de
     origen opaco y sus CSS y JS son de «otro origen». No hay credenciales que proteger: el acceso va en la URL;
   - `Cross-Origin-Opener-Policy: unsafe-none`: con la de la SPA (`same-origin`) el navegador no abre en otra pestaña
     un documento en sandbox;
   - `Cache-Control: no-store`: al cerrar la sesión no queda nada del sitio en la caché del navegador.
5. La SPA muestra el sitio en un `<iframe sandbox="allow-scripts allow-popups" referrerpolicy="no-referrer">`, con «Abrir en otra pestaña». En otra pestaña sigue en sandbox por la cabecera CSP.
6. El registro de accesos escribe `/site/***/<ruta>`: el token es una credencial y no va a los logs. Uvicorn arranca
   con `--no-access-log` (su registro llevaría la ruta completa); el proxy de delante debe enmascarar `/site/` igual
   ([despliegue](../guides/despliegue.md)).

## Consecuencias

- Los scripts del sitio (los del tema de Zensical y los que traiga un documento) se ejecutan en un origen opaco: sin
  cookies ni `localStorage` de la app y sin llamadas a la API con credenciales.
- Quien tenga la URL puede ver el sitio durante, como mucho, una hora y solo mientras la sesión que la creó siga
  activa y su usuario siga siendo miembro. «Renovar acceso» pide otra.
- Con origen opaco, lo que el tema guarde en `localStorage` (preferencias, buscador) no persiste. La E2E de la fase
  comprueba que el sitio carga, navega y no ve la cookie de la app.
- **Riesgo aceptado**: un script incrustado en un documento puede leer su propia URL (con el token) y sacarla
  navegando el iframe a otra web; la CSP no limita la navegación. Quien lo haga ya puede leer el proyecto: el token
  solo da lectura del sitio de ese proyecto, durante como mucho una hora y mientras siga la sesión. Una cookie
  `SameSite=None` limitada a `/site/` lo evitaría y queda, con el subdominio, para la Fase 10.
- Un subdominio propio (`DOW_SITE_ORIGIN`) queda como mejora para la Fase 10 si hiciera falta `allow-same-origin`.
