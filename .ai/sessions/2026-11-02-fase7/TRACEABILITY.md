# TRACEABILITY

## Session metadata
- id: 2026-11-02-fase7
- fecha: 2026-11-02
- rama: feature/fase-7 (desde develop 3373457, 0.7.0 con doc_organize 0.12.1)
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
/phase — Fase: 7. Inputs del mantenedor:
- alcance completo (WB-7.1, WB-7.2, WB-7.3, WF-7.1);
- mejora opcional «exportar plantillas» (descargar e importar `.md`);
- L-8 se pide a doc_organize antes de la fase, sin mkdocs en la imagen.

## Context supplied
- ROADMAP (Fase 7), PARIDAD, DOC_ORGANIZE_GAPS, TAREAS_DOC_ORGANIZE y TRACEABILITY de la Fase 6.
- doc_organize `v0.13.0` (clon local, solo lectura):
  - CHANGELOG con las «Firmas finales»;
  - `context/` (`context_builder`, `context_registry`, `reorganizer`, `site_generator`, `taxonomy_templates`,
    `taxonomy_manifest`) y `projects/layout.py`;
  - web integrada `routes/context.py` y `routes/taxonomy_templates.py` como referencia funcional.
- Release `v0.13.0` de doc_organize: wheel con SHA-256 `381ce668…c728`, el mismo que el hash de `uv.lock`.

## AI output summary
- **Antes de la fase**:
  - G10 (L-8) seguía abierto en 0.12.1;
  - se añadieron G27–G29 (L-8a…L-8c) y se dio el prompt para doc_organize, que publicó la 0.13.0.
- **PLAN + AUDIT_PLAN**: `GO_CONDICIONAL`; el mantenedor resolvió las condiciones y quedó en GO.
  - C1: sitio con token firmado y CSP `sandbox` en el mismo host;
  - C2: una personalizada no usa el nombre de una incluida;
  - C3: contexto proyectado en `config.db`;
  - C4: G30 se avisa y L-8d se pide después.
- **IMPLEMENT backend**:
  - migración `0007_context` (`taxonomy_templates`, `project_contexts`, `context_documents`);
  - `domain/context` (plantillas, manifiesto, validación de `context_build`, token y lectura del sitio);
  - capa anticorrupción `integrations/doc_organize/context.py`;
  - jobs `context_build` y `context_delete`; routers `api/v1/context.py` y `api/site.py` (fuera de `/api`);
  - `loggable_path` en el registro de accesos;
  - `sign(settings, purpose, message)` con subclave por uso;
  - `read_inside` público (documentos, manifiesto y sitio);
  - `source_folders` movido a `_files.py`.
- **Desviación del PLAN §3**: los documentos se listan en `GET /projects/{id}/context/documents?domain=` (sin
  `domain` = sin clasificar; `only=failed|collision`), en lugar de dos rutas.
- **IMPLEMENT frontend**:
  - `features/context` (ContextPage, SiteViewerPage) y `admin/TaxonomyTemplatesPage`;
  - «Borrar contexto» reutiliza `DangerousOperationModal`;
  - `Problem.code` en el cliente.
- **AUDIT_CODE**:
  - Security Reviewer: NO_GO por dos HIGH; los dos están corregidos.
    - HIGH-1: `context.json` del destino con `output_folder_name` = `..` o una ruta absoluta habría llevado a copiar o
      borrar fuera del proyecto. Ahora se valida al leerlo (G32) y el borrado exige la carpeta de la vista previa
      confirmada.
    - HIGH-2: los `.tmp` de doc_organize siguen enlaces (G31). La web quita los que no son ficheros normales antes de
      escribir.
    - MEDIUM-2: uvicorn registraba el token, ahora arranca con `--no-access-log`.
    - MEDIUM-1: la fuga del token por un script del sitio queda como riesgo aceptado en el ADR-010; además se quitó
      `allow-popups-to-escape-sandbox`.
    - LOW corregidos: COOP `unsafe-none`, `no-store` y subclave por uso.
  - Code Auditor: APROBADO CON CONDICIONES; corregidos:
    - un `.md` o `.json` ausente ya no tumba la construcción (se descarta y cuenta);
    - la cancelación usa el `CancelToken` mientras se clasifica, y solo copiar, el sitio y guardar son fase crítica;
    - la proyección se inserta por lotes con `executemany`;
    - `OSError` traducido;
    - una plantilla guardada que deja de ser válida ya no da 500;
    - las colisiones se detectan sin distinguir mayúsculas;
    - el borrado sin `context.json` borra la carpeta de la vista previa.
    - Pendiente: el sitio se lee entero en memoria (hasta 64 MB por fichero).
  - Frontend Reviewer: GO_CONDICIONAL; corregido:
    - crear, duplicar o importar ya no sobrescribe una plantilla existente;
    - estado reiniciado tras reconstruir (`key`), estado del dominio traducido, `aria-pressed`, cargando en el visor,
      `remove.reset()` e `isPending`.
- **VERSION**: 0.8.0 en backend, frontend, OpenAPI y `.env.example`; CHANGELOG, ROADMAP, PARIDAD, `product.md`, guía
  `contexto.md`, ADR-010, GAPS (G10 y G27–G29 resueltos; G30–G32 abiertos con rodeo) y TAREAS (L-8d…L-8f).
- **Validación final**:
  - backend en Linux (imagen `backend-dev`): ruff, mypy, pytest y OpenAPI;
  - frontend: format, lint, typecheck, 66 tests y build;
  - `zensical build --strict`;
  - imagen con `/api/health` 200 y doc_organize 0.13.0;
  - E2E 13/13 con un worker; `context.spec.ts` es nuevo: construir con «calidad», sitio en iframe sin las cookies de
    la app y borrar.

## Artefactos generados
- `backend/alembic/versions/0007_context.py`, `backend/app/domain/context/`,
  `backend/app/integrations/doc_organize/context.py`, `backend/app/jobs/operations/context.py`,
  `backend/app/api/v1/context.py`, `backend/app/api/site.py`
- `backend/tests/api/test_context.py`, `backend/tests/jobs/test_context_operation.py`
- `frontend/src/features/context/`, `frontend/src/features/admin/TaxonomyTemplatesPage.tsx`,
  `frontend/e2e/context.spec.ts`
- `docs/guides/contexto.md`, `docs/adr/ADR-010-sitio-de-contexto-aislado.md`
- `build/logs/fase7-*.txt` (local, ignorado por git)

## Directrices para Futuras IAs
- **[contexto]**: todo lo que doc_organize lee de `context.json` viene del destino y se puede cambiar desde el recurso
  de red. Valida `output_folder_name` con `check_folder_name` antes de copiar o borrar (G32). Nunca uses
  `Context.output_folder_name` sin validar.
- **[contexto]**: `context_delete` solo borra la carpeta que mostró su vista previa: el job compara
  `preview.result["output_folder_name"]`. No quites esa comparación.
- **[contexto]**: llama a `clear_temporaries` antes de cada escritura de doc_organize en el destino (contexto, sitio,
  manifiesto) mientras G31 siga abierto.
- **[contexto]**: la API lista el contexto desde `project_contexts`/`context_documents`, nunca desde `context.json`.
  `context_build`, `context_delete` y `history_clear` mantienen esa proyección.
- **[sitio]**: el sitio Zensical es contenido no confiable. Toda respuesta de `/site/` lleva `SITE_HEADERS` (CSP
  `sandbox` sin `allow-same-origin`). No lo sirvas desde `/api` ni con la cookie de sesión. El token no va a ningún
  registro (`loggable_path`, uvicorn `--no-access-log`).
- **[seguridad]**: `core.security.sign(settings, purpose, message)` deriva una subclave por uso. Cada firma nueva lleva
  su propio `purpose`.
- **[tests]**: los tests de contexto usan los clasificadores reales de doc_organize con conversiones falsas
  (`.json` con `title` y `chunks`); con catálogo propio, el texto debe contener el slug del dominio. Los tests con
  enlaces simbólicos solo corren en Linux.
- **[frontend]**: `Textarea` con `autosize` rompe en jsdom (`document.fonts`). Usa `rows` y `resize="vertical"`.
- **[e2e]**: el tsconfig de los E2E no incluye los tipos del DOM: para `frame.evaluate` con `document`, pasa la
  expresión como texto.

## Pendientes (no bloquean)
- El sitio se lee entero en memoria al servirlo (hasta 64 MB por fichero); conviene servirlo en streaming
  (Code Auditor M4).
- El buscador de Zensical con origen opaco no se ha probado a fondo; la E2E solo cubre la carga y la navegación.
- G30 (L-8d), G31 (L-8e) y G32 (L-8f) se piden a doc_organize; la web tiene rodeo.
- Las regiones `role="status"` se montan ya con su texto (Frontend LOW); se arreglará en todas las pantallas a la vez.

## Veredicto final
GO — Fase 7 cerrada en 0.8.0 con doc_organize 0.13.0.
