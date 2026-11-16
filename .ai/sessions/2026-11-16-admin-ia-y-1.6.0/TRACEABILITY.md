# TRACEABILITY

## Session metadata
- id: 2026-11-16-admin-ia-y-1.6.0
- fecha: 2026-11-16 a 2026-11-17
- rama: `feat/admin-ia-y-doc-organize-1.6.0` (W0–W2, PR #63); release 1.6.0 desde `develop`
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (W0, W1, W2) + VERSION (1.6.0)

## Prompt issued
«PLAN y AUDIT_PLAN por fases» para doc_organize 1.6.0 (librería) y, en la web, medir la construcción del contexto en
red (W0), reorganizar el menú de Administración (W1) y adoptar doc_organize 1.6.0 (W2); después, «W1 y luego W2
implement».

## Context supplied
- `.ai/sessions/2026-11-16-admin-ia-y-1.6.0/PLAN.md` (plan y AUDIT_PLAN, veredicto GO_CONDICIONAL).
- doc_organize 1.6.0 publicada (release del 2026-11-16, wheel con SHA-256 `d6f82123…`).
- Decisiones del usuario:
  - «Parámetros» de IA como página propia en el submenú IA;
  - medición sobre el único recurso SMB disponible (NFS sin medir).

## AI output summary
- **W0** (commit `docs:` en #63): scripts `bench_context_network.py` y `bench_properties_strategies.py`; red 7 veces
  más lenta que local (p95 141 ms por documento). Abre G44, que la librería resuelve en 1.6.0 con 4 lecturas a la vez
  (≈ 28 ms por documento en el NAS).
- **W1** (commit `feat:` en #63):
  - Menú por grupos (`app/adminMenu.ts`): un grupo sin páginas visibles no se pinta; el de la página actual se abre
    solo; grupos como botón con `aria-expanded`.
  - `SettingsTable` compartida por «Ajustes» (por secciones) e «IA › Parámetros»; `InfoPage` con versiones,
    capacidades y workers.
  - `SettingOut.group` desde `SETTING_GROUPS`, con test que falla ante una clave sin sección.
  - Redirecciones de `/admin/ai-settings` y `/admin/ai-usage`.
- **W2** (commit `feat:` en #63):
  - Pin `doc_organize==1.6.0`.
  - G42: `unclassified_reason` (migración 0014) y propiedades de los sin clasificar; columna «Motivo».
  - G43: filtro `mime_type` (repetible), `GET /documents/mime-types` y orden por tipo, creación y propietario (solo
    owners: 403 `owner_order_forbidden`).
  - `context_paths` lista `unclassified.json`.
- Verificación: backend 577 passed, 36 skipped; frontend 129 passed; docs `--strict`; CI de #63 en verde (el primer
  intento falló en los e2e de `login.spec.ts`, corregido en el mismo PR).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-11-16-admin-ia-y-1.6.0/PLAN.md` | emitido, con estado de W1 y W2 |
| Medición | `docs/plan/MEDICION_CONTEXTO_RED.md`, `backend/scripts/bench_*.py` | completado |
| Migración | `backend/alembic/versions/0014_context_unclassified_reason.py` | completado |
| Backend | `app/domain/settings/service.py`, `app/domain/documents/service.py`, `app/integrations/doc_organize/{cache,context}.py`, `app/api/v1/{admin,documents,schemas,listing}.py` | completado |
| Frontend | `app/{Layout,router,adminMenu}`, `features/admin/{SettingsTable,InfoPage,AiParametersPage}`, `features/{documents,context}` | completado |
| Guías | `docs/guides/{ia,ubicaciones,despliegue,ejecuciones,escaneo,contexto,usuarios_y_sesiones}.md` | completado |

## Directrices para Futuras IAs
- **[vitest en Windows]**: `npm test` desde Git Bash (`c:` en minúscula) falla en todas las suites con «Vitest failed to
  find the current suite»; desde PowerShell con `C:` funciona.
- **[menú]**: las páginas dentro de un grupo no son accesibles hasta abrirlo; los tests (unitarios y e2e) pulsan antes
  el botón del grupo («Acceso», «IA»).
- **[Mantine en jsdom]**: las opciones de un `MultiSelect` quedan fuera del árbol accesible; se eligen por su texto.
- **[orden sin mayúsculas]**: al mezclar páginas de varias cachés, `owner_name` se pliega solo en ASCII, como
  `COLLATE NOCASE` de SQLite.
- **[borrado del contexto]**: la librería borra `context.json`, `unclassified.json` y `domains/`; el historial (también
  sus copias giradas) se conserva.

## Veredicto final
Veredicto: CLOSED

Pendientes al cierre:
- e2e de W1/W2 ejecutados solo en el CI (job `image`), no en local.
- NFS sin medir (W0 solo pudo usar SMB).
- Opcionales de W1 sin hacer: migas de pan y sesiones en la ficha de cada usuario.
