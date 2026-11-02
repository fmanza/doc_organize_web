# TRACEABILITY

## Session metadata
- id: 2026-11-02-fase6
- fecha: 2026-11-02
- rama: feature/fase-6 (desde develop 210c62d, 0.6.0 con doc_organize 0.12.0)
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
/phase — Fase: 6. Inputs completados por el mantenedor: alcance completo (WB-6.1, WF-6.1); mejora opcional «exportar
el informe de duplicados»; restricciones doc_organize 0.12.0 (L-6 desde 0.10.0), dependencias nuevas permitidas si
hacen falta, sin GPU ni red en las pruebas.

## Context supplied
- ROADMAP (Fase 6), PARIDAD, DOC_ORGANIZE_GAPS, TAREAS_DOC_ORGANIZE, TRACEABILITY de la Fase 5
- doc_organize `v0.12.0` y `v0.12.1` (clon local, solo lectura): `dedup/deduplication.py` (`find_duplicates`,
  `move_group`, `finalize_report`, `_move_to_duplicates`, `check_duplicates_dir`), `core/models.py`
  (`DocumentMetadata`, `DuplicateGroup`, `DuplicateReason`), `projects/layout.py` (`duplicates_dir`,
  `dedup_report_dir`), `export` (`load_cache_entries`); web integrada `routes/duplicates.py` y
  `duplicates_resolver.html.j2` como referencia funcional
- Release `v0.12.1` de doc_organize: wheel con SHA-256 `8f32d629…93f0`, igual que el digest del asset y el hash de
  `uv.lock`; `dedup/deduplication.py` del wheel idéntico al del tag
- Nota del mantenedor sobre 0.12.1: una ruta que pase por un enlace del sistema falla aunque no se use `relative_to`;
  la web debe pasar rutas reales, resueltas una vez

## AI output summary
- PLAN + AUDIT_PLAN: `GO_CONDICIONAL` con 4 condiciones; el mantenedor las resolvió → GO:
  - C1: G24 (`duplicados/` replica la ruta absoluta) se pide a doc_organize como L-11a (0.12.1) y la fase se cierra
    con esa versión;
  - C2: la búsqueda usa el hash de la caché más un `stat` (G25) y se rehashean solo los grupos que se aplican;
  - C3: buscar, copiar y «solo informe» de editor; mover de propietario;
  - C4: modo «nombre parecido» limitado a 5 000 documentos sin agrupar.
- IMPLEMENT backend:
  - migración `0006_duplicates` (`duplicate_groups`, PK `run_id`+`group_id`, borrado en cascada);
  - `domain/duplicates` (vigencia de la vista previa: 60 min, sin escrituras posteriores ni cambios del proyecto;
    validación de grupos y `keep`; listados);
  - capa anticorrupción `integrations/doc_organize/dedup.py` (`cache_documents`, `find_groups`, `apply_groups` con
    `prepare` por grupo y `finalize_report` siempre);
  - operaciones `dedup_preview` (Excel de grupos como artefacto) y `dedup_apply` (`dry_run`, comprobación por grupo,
    auditoría por fichero y resumen);
  - router `api/v1/duplicates.py`; `public_params` resume los grupos de `dedup_apply` en `RunOut`;
  - `preview_matches` compara los parámetros serializados (`stored_params`), no los modelos.
- IMPLEMENT frontend: `features/duplicates` (pantalla de grupos con política y elecciones manuales guardadas por
  búsqueda en `sessionStorage`, modal de aplicar en dos pasos), ruta, botón en el proyecto, enlace desde el run y
  resultados traducidos.
- Hallazgo en la E2E: la copia quedó en `duplicados/mnt/e2e/proyectos/duplicados/acta copia.txt` (G24 confirmado).
- AUDIT_CODE:
  - Code Auditor: APROBADO CON CONDICIONES.
    - Corregidos:
      - M1: el informe y la auditoría resumen se escriben también ante un error a mitad;
      - M2: los grupos se borran al purgar el run y una búsqueda nueva sustituye a las anteriores;
      - M3: la lista de grupos no se devuelve en `params` (`keep` ≤ 1024);
      - L6: `group_id` repetidos rechazados;
      - L8 y L9.
    - M4 (más de 10 000 grupos): documentado, con aviso en la pantalla.
    - M5 (el ZIP no lleva el informe de duplicados): aplazado a propósito (rutas absolutas).
    - L10: doc_organize cuenta los parecidos como versiones en su informe.
    - L11: doble `find_duplicates`, aceptable.
  - Security Reviewer: sin CRITICAL.
    - Corregidos:
      - HIGH-1 (TOCTOU con enlaces entre el rehash y el movimiento): comprobación por grupo justo antes de moverlo, sin
        tramos enlazados (`lstat`), y G26 pedido en L-11a; cerrado con 0.12.1 (`O_NOFOLLOW`);
      - MEDIUM-1: `duplicados/` enlazado → `folder_replaced`;
      - LOW-1: carpeta de origen sustituida por un enlace → se salta;
      - LOW-2: error de doc_organize en un grupo → falla solo ese grupo;
      - LOW-3: `stat` dentro del `try`.
    - LOW-4 (coste del rehash en `dry_run`): pendiente, acotado por `MAX_ACTIVE_RUNS_PER_USER`.
  - Frontend Reviewer: GO_CONDICIONAL.
    - Corregidos:
      - M1–M5: modo bloqueado mientras se calcula, «Volver a calcular», aviso de más de 10 000 grupos, decisiones
        guardadas por búsqueda, nombres accesibles por grupo;
      - LOW: contraste sin opacidad, alerta de grupos cambiados, `role="status"`, `clampBehavior`.
    - Pendientes LOW: el foco y el scroll no vuelven arriba al paginar; las consultas siguen ~30 s antiguas tras mover.
- VERSION (tras publicarse doc_organize 0.12.1):
  - dependencia subida con hash verificado;
  - `relative_to` = raíz resuelta del origen en `move_group`; las copias quedan en `duplicados/<carpeta>/<ruta>`
    (E2E: `duplicados/duplicados/acta copia.txt`);
  - G24 y G26 a «Resueltos»;
  - 0.7.0 en backend, frontend, OpenAPI y `.env.example`; CHANGELOG, ROADMAP, PARIDAD, `product.md`, guía.
- Validación final:
  - backend: ruff, mypy, 359 tests en Linux (imagen `backend-dev`), OpenAPI exportado;
  - frontend: format, lint, typecheck, 60 tests y build;
  - `zensical build --strict`;
  - imagen con `/api/health` 200 y doc_organize 0.12.1;
  - E2E 12/12 con un worker de Playwright (`duplicates.spec.ts` nuevo).

## Artefactos generados
- `backend/alembic/versions/0006_duplicates.py`, `backend/app/domain/duplicates/`,
  `backend/app/integrations/doc_organize/dedup.py`, `backend/app/jobs/operations/dedup.py`,
  `backend/app/api/v1/duplicates.py`
- `backend/tests/api/test_duplicates.py`, `backend/tests/jobs/test_dedup_operation.py`
- `frontend/src/features/duplicates/`, `frontend/e2e/duplicates.spec.ts`
- `docs/guides/duplicados.md`
- `build/logs/fase6-*.txt` (local, git-ignored)

## Directrices para Futuras IAs
- **[duplicados]**: doc_organize ≥ 0.12.1 no mueve ni copia nada cuya ruta pase por un enlace simbólico, ni siquiera
  un enlace del sistema. Todo lo que se le pase (origen, `duplicados/`, `relative_to`) sale del resolvedor de
  ubicaciones (`resolve_within`, que resuelve la raíz una vez). Nunca construyas esas rutas desde
  `Location.container_path` sin resolver.
- **[duplicados]**: `dedup_apply` usa dos runs distintos. `groups_run_id` es la búsqueda (`dedup_preview`, grupos en
  `duplicate_groups`) y `preview_run_id` es el `dry_run` del propio `dedup_apply`, que exige la regla 7.
  `domain/duplicates/service.preview_run` decide si la búsqueda sigue vigente.
- **[duplicados]**: cada grupo se comprueba en `prepare` justo antes de `move_group` (`_no_links` + hash), no en una
  pasada previa. No muevas esa comprobación fuera de `apply_groups`: reabre la ventana entre comprobar y mover.
- **[duplicados]**: `apply_groups` siempre llama a `finalize_report` y `run_apply` siempre audita el resumen en su
  `finally`. Lo ya movido nunca queda sin rastro.
- **[runs]**: `preview_matches` compara `stored_params(params)` con el JSON guardado. Comparar con `getattr` falla con
  listas de modelos Pydantic.
- **[tests]**: los tests con enlaces simbólicos solo corren en Linux. La suite se valida con la imagen `backend-dev`.
- **[e2e]**: levanta la app con `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build`. Sin el
  override no existe `/mnt/e2e` y fallan 6 E2E con 503. Lanza `npx playwright test --workers=1`.

## Pendientes (no bloquean)
- Security LOW-4: el `dry_run` rehashea todos los grupos elegidos (coste en carpetas grandes de red).
- Frontend LOW: foco y scroll al paginar; consultas ~30 s antiguas tras mover.
- El ZIP de exportación no incluye el informe de duplicados (rutas absolutas en `DEDUP_REPORT.json`).
- Más de 10 000 grupos no se aplican de una vez.
- G25 (metadatos de la caché sin tamaño ni fecha): opcional en doc_organize.

## Veredicto final
GO — Fase 6 cerrada en 0.7.0 con doc_organize 0.12.1.
