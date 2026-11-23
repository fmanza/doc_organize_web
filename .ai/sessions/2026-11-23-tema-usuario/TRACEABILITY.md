# TRACEABILITY

## Session metadata
- id: 2026-11-23-tema-usuario
- fecha: 2026-11-23
- rama: feat/2.3.0-tema-usuario (#108)
- skill: new_feature
- fase: PLAN + AUDIT_PLAN (en la conversación, sin fichero) + IMPLEMENT

## Prompt issued
- «Revisar la web para añadir modo claro, oscuro, como opción por usuario, solo PLAN»; «Acepto recomendaciones,
  AUDIT_PLAN»; «Empieza el IMPLEMENT del tema por la web 2.3.0».
- Decisiones del mantenedor (recomendaciones aceptadas): el tema se guarda en el servidor (por usuario) con copia
  local en el navegador; la copia local se conserva al cerrar sesión.

## Context supplied
- `frontend/src/app/Providers.tsx`, menú de usuario, CSP de la imagen (`script-src 'self'`), `docs/guides/usuarios_y_sesiones.md`.

## AI output summary
- **Backend**: `users.color_scheme` (`String(8)`, `server_default="auto"`; migración **`0028`**, aditiva);
  `set_color_scheme` en `domain/identity/users.py` (valida y solo hace commit si cambia); `Me.color_scheme`
  obligatorio y `PUT /api/v1/auth/me/preferences` con `Preferences` (`extra="forbid"`), solo el propio usuario, CSRF
  como todo `/api/v1`, sin auditoría (preferencia visual).
- **Frontend**: `app/colorScheme.ts` (gestor `localStorage` con clave `mantine-color-scheme-value`, en memoria en
  tests); `public/color-scheme.js` aplica la copia local antes de React (sin destello; fichero aparte por la CSP);
  `ColorSchemeSync` aplica el del servidor al llegar `/me`; `useUpdateColorScheme` optimista con vuelta atrás y aviso
  flotante si falla; grupo «Tema» en `UserMenu` («Como el sistema», «Claro», «Oscuro») con `aria-current`.
- **Desviación A5 del AUDIT_PLAN**: Mantine fija `role="menuitem"` en `Menu.Item`, así que no hay
  `menuitemradio`/`aria-checked`; la elegida lleva `aria-current="true"`.
- **Pruebas**: tests de auth (por defecto, guardar, por usuario, 422, 401/403, sin auditoría); 5 tests Vitest
  (`colorScheme.test.tsx`, con `?raw` para `index.html` y `color-scheme.js`); E2E `theme.spec.ts` con usuario propio
  creado por API. E2E también en local contra un stack aislado (`-p dow-e2e`, puerto 8091); revisión visual en claro y
  oscuro hecha por el mantenedor, sin incidencias.
- CI: el primer intento falló en `tsc` de `e2e/` (`window` no existe en ese tsconfig) → `evaluate` con cadena.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Feature 2.3.0 | PR #108 (`db004bc`) | fusionado |
| Guía | `docs/guides/usuarios_y_sesiones.md` («Tema claro u oscuro») | actualizada |

## Directrices para Futuras IAs
- **[e2e]**: tras escribir o tocar `frontend/e2e/*.ts`, pasar `tsc` también sobre ese proyecto: su tsconfig no tiene
  `dom`, y el CI lo comprueba antes de `vitest`.
- **[e2e/local]**: para probar en local sin tocar el stack de trabajo, proyecto aislado
  (`COMPOSE_FILE="docker-compose.yml;docker-compose.e2e.yml" COMPOSE_PATH_SEPARATOR=";" DOW_PORT=8091 docker compose -p dow-e2e`),
  imagen con `docker buildx build --load` y admin con `python -m app.cli create-admin --password-stdin`; al acabar,
  `down -v` y borrar la imagen.
- **[mantine]**: `Menu.Item` siempre es `role="menuitem"`; para estado seleccionado usar `aria-current`.
- **[csp]**: nada de scripts en línea en `index.html`; van a `frontend/public/`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: ninguno propio de la funcionalidad.
