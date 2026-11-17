# PLAN + AUDIT_PLAN — Iconos en el menú y fuera de los emojis (2026-11-17)

Skill: `new-feature` (web). Solo PLAN y AUDIT_PLAN; sin implementar.

## Inputs

| Campo | Valor |
|---|---|
| Objetivo | Iconos en todas las entradas del menú lateral (primer nivel, grupos y páginas de cada grupo) y sustituir los emojis y símbolos Unicode que hacen de icono por iconos de la misma librería |
| Decisiones del mantenedor | Librería `@tabler/icons-react`; iconos en **todas** las entradas; sustituir también los emojis existentes |
| Rutas | `frontend/package.json`, `package-lock.json`; `src/components/icons.ts` (nuevo); `src/app/Layout.tsx`, `src/app/adminMenu.ts`; `src/components/{FolderBrowser,listing,StatusLight,BackLink (nuevo)}.tsx`; `src/features/runs/RunStatusBadge.tsx`; las 9 páginas con enlace «← Volver»; `src/i18n/es/features.json`; `docs/plan/DEPENDENCIAS.md`, `CHANGELOG.md` |
| Contrato HTTP | Sin cambios |
| Pantallas | Menú lateral; distintivos de estado (ejecuciones, ubicaciones); explorador de carpetas; cabeceras ordenables y «Ordenar por»; enlaces «Volver» |
| Permisos | Sin cambios |
| doc_organize | No interviene |
| Restricciones | Una dependencia nueva de runtime (MIT); versión con ≥ 14 días (`npm run safe`): **3.50.0** (2026-10-27; 3.51.0 y 3.52.0 aún no cumplen); sin migración ni backend |

## PLAN

### Inventario de lo que se sustituye

| Dónde | Hoy | Icono Tabler |
|---|---|---|
| `FolderBrowser.tsx:140` (subir un nivel) | ↑ | `IconArrowUp` |
| `FolderBrowser.tsx:156,188` (carpeta) | 📁 | `IconFolder` |
| `listing.tsx:19` (cabecera ordenable) | ↑ ↓ ↕ | `IconSortAscending`, `IconSortDescending`, `IconArrowsSort` |
| `listing.tsx:144` (botón de sentido en «Ordenar por») | ↑ ↓ | `IconSortAscending`, `IconSortDescending` |
| `StatusLight.tsx` (ubicaciones, salud) | ● ▲ ■ ? | `IconCircleCheck`, `IconAlertTriangle`, `IconCircleX`, `IconHelpCircle` |
| `RunStatusBadge.tsx` (ejecuciones) | … ▶ ✓ ✕ ■ | `IconClock`, `IconPlayerPlay`, `IconCheck`, `IconX`, `IconPlayerStop` |
| 9 enlaces «Volver» (texto en `features.json`: `back`, `backToProject`, `backToScan`, `backToRun`) | «← …» en el propio texto | `IconArrowLeft` delante; el texto pierde la flecha |

Se quedan como están los separadores tipográficos de los textos (`·`, `›` de «IA › Parámetros», `…` de «Guardada: …ab12»):
son puntuación, no iconos.

### Iconos del menú

| Entrada | Icono |
|---|---|
| Inicio | `IconHome` |
| Proyectos | `IconFolders` |
| ↳ Duplicados · Escaneo · Documentos · Contexto | `IconCopy` · `IconScan` · `IconFileText` · `IconSitemap` |
| Ejecuciones | `IconPlayerPlay` |
| Ubicaciones | `IconServer` |
| Acceso | `IconUsers` |
| ↳ Usuarios · Roles · Sesiones · Tenants | `IconUser` · `IconShieldCheck` · `IconDevices` · `IconBuilding` |
| Plantillas de taxonomía | `IconTemplate` |
| IA | `IconSparkles` |
| ↳ Configuración · Parámetros · Uso | `IconPlugConnected` · `IconAdjustmentsHorizontal` · `IconChartBar` |
| Ajustes | `IconSettings` |
| Información | `IconInfoCircle` |
| Auditoría | `IconListSearch` |

El rótulo «Administración» sigue siendo texto: no es una entrada que se pulse.

### Diseño

1. **Un solo módulo importa la librería**: `src/components/icons.ts` reexporta los iconos con nombres de la app
   (`NavIcons.home`, `StatusIcons.ok`…) y fija `ICON_SIZE` (18 px en el menú, 14 px en distintivos y botones pequeños)
   y `ICON_STROKE` (1.75). Cambiar un icono o la librería toca un fichero. Una regla de ESLint
   (`no-restricted-imports`) lo impone fuera de ese módulo.
2. **Imports por icono, no el barril**: con `import { IconHome } from '@tabler/icons-react'`, Vite en desarrollo y
   Vitest cargan el índice con unos 5000 módulos. Eso alarga el arranque y los tests, justo lo que acaba de dar
   problemas de tiempo. Se importa cada icono por su ruta ESM (`@tabler/icons-react/dist/esm/icons/IconHome.mjs`), si
   el paquete la exporta con tipos. Si no, se usa el barril con `optimizeDeps.include` y `server.deps.inline` en Vitest.
   Se decide midiendo (condición 2).
3. **Decorativos**: todos con `aria-hidden` (Tabler no pone `role` ni título). El nombre accesible sigue siendo el texto,
   así que los tests por rol y nombre no cambian. Estados y semáforo mantienen icono **y** texto (WCAG 1.4.1).
4. **Color del tema**: `stroke="currentColor"` (por defecto en Tabler) hereda el color del `NavLink` y del `Badge`, y
   sigue al tema claro y oscuro.
5. **Menú**: `adminMenu.ts` gana `icon` en cada `AdminPage` y en cada grupo; `Layout.tsx` lo pasa como `leftSection`
   de cada `NavLink`, también en «Inicio», «Proyectos» y sus secciones, «Ejecuciones» y «Ubicaciones»
   (`PROJECT_SECTIONS` pasa a llevar icono).
6. **`BackLink`** (nuevo): `<Anchor component={Link}>` con `IconArrowLeft` y el texto. Sustituye a los 9 enlaces de
   vuelta y quita «← » de sus textos en `features.json`.
7. **Dependencia**:
   - `npm run safe -- install --save-exact @tabler/icons-react@3.50.0`.
   - Fila en `DEPENDENCIAS.md` (Frontend).
   - Dependabot ya respeta el `cooldown` de 14 días.

### Tests

- **Menú:** test de que cada entrada visible lleva su icono, comprobando que hay un `svg[aria-hidden]` dentro de cada
  enlace o botón del menú. Los tests de permisos de W1 siguen igual.
- **Estados, semáforo y ordenar:** los tests existentes buscan por texto y por `aria-sort`. Se añade uno que compruebe
  que ya no queda ningún emoji en el DOM de las páginas principales: busca los caracteres sustituidos en
  `document.body.textContent`.
- **«Volver»:** los tests y los e2e que buscan «Volver a …» por nombre accesible siguen funcionando, porque la flecha
  deja de ser parte del texto. Se revisan los que usen el texto exacto con «←».
- **Medidas antes y después** (condición 2):
  - duración de `npm test` en la misma máquina;
  - tamaño de `dist/assets` en `npm run build`;
  - arranque de `npm run dev`.

## AUDIT_PLAN

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| F1 | Con iconos en todas las entradas, el menú de administración (13 entradas) queda cargado | 18 px y trazo fino; las páginas de un grupo van sangradas (`childrenOffset`). Revisar en pantalla y en móvil antes de cerrar |
| F2 | Un icono que no se entiende (Sesiones, Tenants) confunde más que ayuda | El texto sigue al lado; los iconos se eligen en un único módulo y se cambian sin tocar páginas |
| F3 | Los textos «← Volver…» pueden estar copiados en la documentación o en los e2e | Buscar «←» en `docs/` y `e2e/` y ajustarlos en el mismo cambio |
| F4 | Las flechas de ordenar cambian de forma (↑ por un icono) y alguien se fija en el símbolo | El estado sigue en `aria-sort` y en el `title`; el icono solo lo hace visible |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| T1 | **Barril de 5000 iconos** en Vite y Vitest: arranques y tests más lentos (ya hubo fallos por tiempo) | Imports por ruta de cada icono, o `optimizeDeps` y `server.deps.inline`; medir `npm test` antes y después (condición 2) |
| T2 | El build mete iconos de más | Tree-shaking de Vite con ESM; comprobar el tamaño de `dist/assets` (como mucho unos pocos KB por icono usado) |
| T3 | Tipos de las rutas profundas | Si `@tabler/icons-react` no exporta tipos para `dist/esm/icons/*`, declarar el módulo en `src/types/` o volver al barril con T1 mitigado |
| T4 | Política de versiones (≥ 14 días) | 3.50.0 con `npm run safe`; 3.51.0 (2026-11-08) entra cuando lo proponga Dependabot |
| T5 | Mantine `Badge` y `NavLink` con `leftSection` cambian un poco la altura | Ajuste visual; los tests no dependen de medidas |

### Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| S1 | Dependencia nueva en runtime (cadena de suministro) | MIT y mantenida; sus dependencias son solo `@tabler/icons`. Versión exacta, lockfile con integridad, cooldown de 14 días y auditoría de npm en CI |
| S2 | CSP | Los SVG van en línea desde React, sin cargar nada externo: la CSP actual no cambia |

### Simplificaciones posibles

- **Iconos solo en el primer nivel y los grupos**: descartada por el mantenedor, que quiere iconos en todas.
- **Mantener «←» en los textos y no crear `BackLink`**: menos cambios, pero deja un símbolo Unicode, cuando el objetivo
  es no tener ninguno haciendo de icono. No recomendada.
- **Sin módulo `icons.ts`**: importar en cada fichero. Más directo, pero dispersa la elección de iconos y el tamaño.
  No recomendada.

### Veredicto: **GO_CONDICIONAL**

Condiciones:

1. Toda importación de `@tabler/icons-react` pasa por `src/components/icons.ts`, con la regla de ESLint.
2. Medir `npm test` y el tamaño del build antes y después. Si `npm test` tarda más de un 20 % más, cambiar a imports
   por ruta o a `optimizeDeps` antes de cerrar.
3. Revisar el menú en pantalla (escritorio y ancho de móvil) con la app levantada antes del PR.

> **Estado (2026-11-17)**: implementado. Condiciones:
> 1. Cumplida: `src/components/icons.ts` es el único que importa la librería (`no-restricted-imports` en ESLint).
> 2. Cumplida, sin mitigación: `npm test` ≈ 10 s con iconos frente a ≈ 11,9 s antes (3 ejecuciones cada una); build
>    +10,8 KB (1 482 339 → 1 493 130 bytes). Se importa el barril: Vite hace tree-shaking (`sideEffects: false`) y los
>    tests no se alargan.
> 3. Cumplida con capturas (API simulada con Playwright, sin backend): escritorio claro y oscuro correctos. En móvil el
>    menú lateral ocupa todo el ancho y no se puede plegar: viene del `AppShell` de la Fase 0 (sin `collapsed` ni botón
>    de menú), no de los iconos. Queda como mejora aparte.
>
> Además: los tests del frontend usan Mantine con `env="test"` (sin transiciones ni portales). Con la suite en paralelo,
> el menú de usuario a veces se quedaba en `display: none` y «cierra sesión con la cabecera CSRF» fallaba aunque se
> esperara 5 s.

> **Menú en móvil (2026-11-17, a petición del mantenedor)**: `Burger` en la cabecera (`hiddenFrom="sm"`) y
> `navbar.collapsed.mobile`. El menú recuerda en qué ruta se abrió y se pliega al cambiar de ruta, sin efectos.
> Revisado con capturas a 390 px (cerrado y abierto) y a 1280 px (sin cambios). Pendiente: la cabecera en móvil sigue
> apretada (el título queda oculto y el nombre de usuario se recorta), porque el selector de tenant y el menú de usuario
> no se adaptan. Mejora aparte.
