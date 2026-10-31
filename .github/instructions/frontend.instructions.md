---
applyTo: "frontend/**/*.{ts,tsx}"
---
# Frontend (React + TypeScript) — reglas

> **TL;DR** — TypeScript estricto, componentes funcionales, datos solo vía TanStack Query y el cliente OpenAPI
> generado, UI con Mantine, textos en i18n, accesibilidad WCAG 2.2 AA, listados grandes virtualizados.

## Estructura
- `src/features/<área>/`: páginas, componentes y hooks de una funcionalidad (`useX.ts` con TanStack Query). Áreas:
  `auth`, `admin`, `locations`, `projects`, `scan`, `runs`, `cache`, `duplicates`, `context`, `taxonomies`, `ai`,
  `health`.
- `src/components/`: UI compartida sin lógica de negocio (explorador de carpetas, semáforo de estado, visor
  Markdown/JSON saneado, progreso de ejecución).
- `src/api/`: `client.ts` (único punto con `fetch`) y `schema.d.ts` (generado, no editar).
- Rutas en `src/app/router.tsx`, hijas de `Layout`; páginas de cada fase con `lazy` para dividir el bundle.

## Datos
- `queryKey` estables y jerárquicas (`['projects', projectId, 'runs']`); invalidar tras mutaciones.
- Errores: `ApiError` con *problem details*; mostrar `title`/`detail`, nunca trazas.
- Progreso de ejecuciones por SSE (`/api/v1/runs/{id}/events`, Fase 3) con *fallback* a `refetchInterval`; el run
  sigue aunque se cierre la pestaña.
- Caché, documentos y duplicados (hasta ~100 000 filas): paginación en servidor + tablas virtualizadas; nunca cargar
  la colección entera.

## UI y accesibilidad
- Mantine; tema en `app/Providers.tsx`; modo oscuro automático.
- Cada vista con estados de carga, vacío, error y sin permiso; ubicación `unavailable` visible con el semáforo.
- Formularios: React Hook Form + Zod; errores asociados al campo; opciones de escaneo validadas contra las
  capacidades de la instancia (GPU, AV, LibreOffice).
- Rutas elegidas siempre con el explorador de carpetas dentro de una ubicación; nunca campo de texto libre de ruta.
- Acciones que mueven o borran ficheros: modal de confirmación que repite el nombre del recurso y muestra la vista
  previa (modo seco); si la ubicación es `ro`, la acción no se ofrece.
- Markdown convertido renderizado saneado (DOMPurify); sitio de contexto en `iframe` con `sandbox` sin
  `allow-same-origin`.

## Estilo
- Sin `any`; tipos del cliente generado; `import type` para tipos.
- Textos con `useTranslation()`; claves en `src/i18n/es/core.json` (lo que se ve sin pasar por una ruta lazy) o
  `src/i18n/es/features.json` (pantallas; se carga con la primera ruta lazy).
- Prettier + ESLint (`npm run lint`) sin avisos.
