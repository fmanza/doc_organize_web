# TRACEABILITY

## Session metadata
- id: 2026-11-27-version-3.1.0
- fecha: 2026-11-27
- rama: `feat/ui-menu-iconos-y-alineacion` (PR #149) y `release/3.1.0` (desde `develop`)
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN (`GO_CONDICIONAL`, dos decisiones) → IMPLEMENT + AUDIT_CODE → VERSION

## Prompt issued
Lista de mejoras de UI (menú contraíble, filtros de Ejecuciones, alta de rol por menú, Plantillas, IA › Configuración,
Ajustes, Auditoría y una regla para alinear etiquetas y campos con descripción) → «PLAN y AUDIT_PLAN» → «Menú: barra
estrecha con iconos, descripción debajo del campo y global en el tema, IMPLEMENT» → «si» (commit, PR, fusión) →
«Adelante» (publicar).

## Context supplied
- `.github/SHARED_INSTRUCTIONS.md`, skill `new-feature`, `.github/instructions/frontend.instructions.md`.
- Código real de `Layout.tsx`, `adminMenu.ts`, `RunsPage.tsx`, `RolesPage.tsx`, `TaxonomyTemplatesPage.tsx`,
  `AiModelsPanel.tsx`, `AiFamilyCard.tsx`, `SettingsTable.tsx`, `AuditPage.tsx` y el `Operation` del backend.

## AI output summary
- PLAN: todo en frontend; detectado el bug del filtro de operaciones (4 de 21 fijadas a mano).
- Decisiones del usuario: barra de iconos (no plegado total) y descripción debajo del campo, global en el tema.
- PR #149 (`2080df5`): barra de iconos con `RailContext` y `useNavRail`; `Record<Operation, true>`;
  `permissionGroups()` desde `ADMIN_MENU`; tablas con `nowrap` y `layout="fixed"`; detalles de auditoría en `<dl>`;
  `InputWrapper.extend` en el tema; regla en `frontend.instructions.md` y `.ai/standards.md`.
- VERSION: 3.1.0 sincronizada (`pyproject.toml`, `app/__init__.py`, `package.json`/lock, `uv.lock`, `openapi.json`,
  `DOW_TAG`) y CHANGELOG `[3.1.0]`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Mejoras de UI | #149 · `2080df5` | fusionado |
| Release 3.1.0 | rama `release/3.1.0` | PR a `develop` |

## Directrices para Futuras IAs
- **[frontend formularios]**: el orden `label → input → description → error` está fijado para todos los campos en
  `app/Providers.tsx` (`InputWrapper.extend`, lo comprueba `app/theme.test.tsx`); no lo cambies en un campo sin dejar
  el motivo escrito al lado.
- **[frontend menú]**: una entrada nueva del menú lateral se pinta con `NavItem` (`app/Layout.tsx`), que resuelve la
  barra de iconos (`RailContext`); un `NavLink` directo perdería el aviso y el nombre accesible en la barra.
- **[frontend menú]**: la barra solo existe en pantallas anchas (`useMediaQuery` con
  `getInitialValueInEffect: false`); en Vitest el `matchMedia` simulado nunca casa, así que el test la activa con
  `vi.stubGlobal('matchMedia', …)` (`app/layout.test.tsx`).
- **[frontend roles]**: los grupos de permisos del formulario de rol salen de `ADMIN_MENU` (`permissionGroups()` en
  `app/adminMenu.ts`); un permiso nuevo que no abra una página va en `PROJECT_PERMISSIONS` o en un grupo nuevo, y
  `tenancy.test.tsx` falla si queda fuera.
- **[frontend ejecuciones]**: `OPERATION_FILTER` en `RunsPage.tsx` es un `Record<Operation, true>`: una operación
  nueva del backend no compila hasta añadirla allí (y su texto en `runs.operations`).
- **[frontend tests]**: con `env="test"` Mantine pinta los desplegables de todos los `Select` sin portal; para contar
  opciones, busca dentro del `listbox` de su `aria-controls`.

## Veredicto final
Veredicto: CLOSED (publicación: PR de release, fast-forward de `main`, tag y release en GitHub)
Pendientes al cierre:
- Revisión visual en navegador de los formularios de varias columnas y de Ajustes en inglés (no hecha: requiere sesión).
- Prueba E2E de la barra de iconos en escritorio.
