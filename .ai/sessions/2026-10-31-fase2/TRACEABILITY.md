# TRACEABILITY

## Session metadata
- id: 2026-10-31-fase2
- fecha: 2026-10-31
- rama: feature/fase-2 (desde develop tras la 0.2.0)
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
/phase — Fase: 2. Alcance: completa. Mejoras opcionales: no. Restricciones: sin dependencias nuevas; doc_organize
0.9.3 sin cambios (capacidades con el rodeo de G12); en desarrollo solo carpetas locales.

## Context supplied
- `.ai/*.md`, ROADMAP, ARQUITECTURA_PROPUESTA, `filesystem.instructions.md`, PARIDAD
- doc_organize 0.9.3 (tag): `utils/{gpu,av,office}_detector.py`, `core/models.py`, `web/routes/filesystem.py`
- util_bbdd_web ADR-012 y `domain/storage/settings.py`

## AI output summary
- PLAN + AUDIT_PLAN: `GO_CONDICIONAL`; el mantenedor aprobó capacidades en subproceso, ajustes de identidad + sondeo,
  `container_path` inmutable y sondeo bajo demanda → GO.
- Medición: importar un detector de doc_organize carga Docling y torch (4 322 módulos, 49 s en frío) → G15.
- IMPLEMENT backend: migración `0003`, resolvedor `paths.py`, sondeo `probe.py`, servicio de ubicaciones, ajustes
  efectivos (`domain/settings`), capacidades en subproceso (`integrations/doc_organize/capabilities.py`), routers
  `locations`, `fs`, `admin`, `instance`, `/api/health` con `locations`; 187 tests (1 omitido en Windows: permisos POSIX).
- IMPLEMENT frontend: `FolderBrowser`, `StatusLight`, ubicaciones (lista, detalle, alta/edición, borrado con
  confirmación), ajustes y capacidades; 31 tests; E2E de ubicaciones con `docker-compose.e2e.yml` (7/7 contra la imagen).
- AUDIT_CODE (Code Auditor + Frontend Reviewer + Security Reviewer, en la sesión): rechazo sintáctico + resolución con
  enlaces; mismo 404 (test compara los cuerpos); 503 sin ruta del contenedor; `container_path` solo para admin;
  timeouts de E/S; volúmenes `data`/`workspace` vetados como ubicación; `app_settings` sin secretos y con rangos;
  capacidades fuera del proceso de la API. Corregido durante la auditoría: las carpetas del explorador eran `<a>` sin
  `href` (no accesibles por teclado) → `NavLink component="button"`.
- Validación: backend (ruff, format, mypy, pytest 187, OpenAPI), frontend (format, lint, typecheck, Vitest 31, build),
  `zensical build --strict`, imagen 3,02 GB, `/api/health`, capacidades en el contenedor (7,4 s), E2E 7/7.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-31-fase2/PLAN.md` | emitido (GO tras condiciones) |
| IMPLEMENT | `backend/app/domain/{locations,settings}`, `backend/app/integrations/doc_organize/capabilities.py`, `backend/app/api/v1/{locations,fs,admin,instance}.py`, `frontend/src/{components,features/locations,features/admin/SettingsPage.tsx}` | completado |
| Docs | ADR-007, ADR-012, `guides/ubicaciones.md`, `guides/carpetas_de_red.md` | nuevos |

## Directrices para Futuras IAs
- **[rutas]**: toda ruta que llegue por la API pasa por `app/domain/locations/paths.py` (`resolve_within`); devuelve
  `ResolvedPath`. Nunca construyas rutas con `Path(location.container_path) / texto_del_usuario` fuera de ahí.
- **[rutas]**: «fuera de la ubicación» y «no existe» deben dar el mismo cuerpo 404; `test_browse_escape_and_missing_give_same_404`
  lo comprueba. Los errores de ubicaciones nunca incluyen `container_path`.
- **[e-s-red]**: cualquier E/S sobre una ubicación va por `run_with_timeout` (pool de 8 hilos): un montaje colgado no
  bloquea la API pero deja el hilo ocupado.
- **[doc_organize]**: no importes `doc_organize` en el proceso de la API (G15: carga Docling y torch). Capacidades:
  `capabilities_cache` (subproceso). En la Fase 3, publicar las capacidades desde el worker.
- **[ajustes]**: `SettingsDep` son los ajustes **efectivos** (con `app_settings`); para añadir una clave administrable,
  añádela a `Settings` (con rango) y a `ADMIN_KEYS`, más su texto en `features.json` (`settings.keys.<clave>`).
- **[ajustes]**: los valores se validan con `TypeAdapter(Annotated[tipo, *metadata])` del campo de `Settings` en modo
  estricto (un `true` no vale como entero); no uses `validate_assignment` sobre `Settings` (dispara el validador de
  secretos de producción).
- **[tests]**: en este Windows de desarrollo los enlaces simbólicos sí se pueden crear (modo desarrollador); el test de
  permisos POSIX solo corre en el CI Linux.
- **[frontend-a11y]**: `NavLink` de Mantine sin `href` se renderiza como `<a>` sin rol: para acciones usa
  `component="button" type="button"`.
- **[i18n]**: escribir barras invertidas en JSON desde scripts de shell es frágil; edita el JSON directamente.
- **[e2e]**: `docker-compose.e2e.yml` monta `dev-data/e2e` en `/mnt/e2e` (`:ro`); el job `image` lo usa vía
  `COMPOSE_FILE`.

## Veredicto final
Veredicto: CLOSED (pendiente de CI del PR y de publicar)
Pendientes al cierre:
- PR `feature/fase-2` → `develop` y release 0.3.0 si el mantenedor lo pide.
- La Fase 3 requiere doc_organize 0.10.0 (L-1, L-4, L-5): sin esa versión publicada, habrá que planificarla con rodeos.
