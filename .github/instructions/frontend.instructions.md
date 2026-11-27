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
- **Etiquetas, campos y ayuda** (regla del proyecto, 2026-11-27): orden `etiqueta → campo → descripción → error`,
  fijado para todos los campos en el tema (`InputWrapper` en `app/Providers.tsx`); no se cambia por campo salvo con
  el motivo escrito al lado. Así, en un formulario de varias columnas, los campos de una misma fila quedan alineados
  aunque sus descripciones tengan distinta longitud. Además: etiquetas cortas (una línea); cuadrículas
  (`SimpleGrid`, `Group`) alineadas arriba; una ayuda larga va en un `Alert` o un párrafo encima del bloque, no en la
  `description` de un campo; casillas agrupadas por tema en `Fieldset` con leyenda.
- Tablas en varias secciones de una misma página (p. ej. «Ajustes»): mismo componente con `layout="fixed"` y anchos
  de columna compartidos, para que las columnas coincidan entre secciones. Nombres, fechas y acciones en una línea
  (`white-space: nowrap`); el texto libre se lleva el ancho que sobre.
- Rutas elegidas siempre con el explorador de carpetas dentro de una ubicación; nunca campo de texto libre de ruta.
- Acciones que mueven o borran ficheros: modal de confirmación que repite el nombre del recurso y muestra la vista
  previa (modo seco); si la ubicación es `ro`, la acción no se ofrece.
- Markdown convertido renderizado saneado (DOMPurify); sitio de contexto en `iframe` con `sandbox` sin
  `allow-same-origin`.

## Estilo
- Sin `any`; tipos del cliente generado; `import type` para tipos.
- Textos con `useTranslation()`; claves en `src/i18n/es/core.json` (lo que se ve sin pasar por una ruta lazy) o
  `src/i18n/es/features.json` (pantallas; se carga con la primera ruta lazy). Es requisito: `src/i18n/i18n.test.ts`
  falla con texto visible fuera de `t()` (JSX, `aria-label`, `title`, `placeholder`, `label`...), una clave usada que
  no existe o una clave sin uso. Una excepción (valor técnico, no texto) va en su `ALLOWED_LITERALS` con el motivo.
- Dos idiomas (2.6): todo texto nuevo va en `src/i18n/es/` **y** `src/i18n/en/` con la misma clave y los mismos
  `{{marcadores}}` (lo exige el mismo test). Inglés británico y términos del glosario (`.ai/glossary.md`). Los tests de
  Vitest y los E2E trabajan en español (`src/test/setup.ts`, `locale: 'es-ES'` en Playwright).
- Fechas y números con los formateadores de `src/components/format.ts` (o `cachedFormat` con `intlLocale()` de
  `src/i18n`), nunca con un locale fijo ni como constante de módulo: el idioma cambia en caliente.
- Título de un error de la API con `problemTitle` (`src/components/problem.ts`): traducido por `code` o estado HTTP
  fuera del español. Un `code` nuevo en el backend → su título en `errors.code` de ambos `core.json`.
- Prettier + ESLint (`npm run lint`) sin avisos.
