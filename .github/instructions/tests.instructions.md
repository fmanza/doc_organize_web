---
applyTo: "backend/tests/**,frontend/src/**/*.test.{ts,tsx},frontend/e2e/**"
---
# Tests — reglas

## Backend (pytest)
- `tests/unit`: lógica sin I/O. `tests/api`: `TestClient` con la fixture `client` (SQLite en `tmp_path`).
  `tests/integration`: `@pytest.mark.integration`, conversión real con Docling, GPU o montajes de red; fuera del CI.
- doc_organize sustituido en la capa anticorrupción en `unit` y `api`; un test de contrato por adaptador comprueba que
  las firmas usadas existen en la versión fijada.
- Cada endpoint nuevo: caso feliz, validación (422), sin sesión (401), sin permiso (403) y recurso ajeno (404, IDOR).
- Rutas: escape con `..`, ruta absoluta/UNC, enlace simbólico que sale de la ubicación, carpeta ajena inexistente
  frente a existente (misma respuesta), ubicación `unavailable` → 503.
- Jobs: cancelación a mitad, timeout de documento, huérfano por latido caducado, segunda escritura en el mismo
  proyecto → 409.
- Toda función que maneje secretos: test que verifique que el secreto no aparece en la respuesta ni en el log
  (`caplog`) ni en `run.json`.
- `tests/unit/test_architecture.py` no se relaja: solo la capa anticorrupción importa doc_organize.
- Documentos de prueba **sintéticos**, generados por el propio test en `tmp_path` (repositorio público).

## Frontend (Vitest + Testing Library)
- Renderizar con `renderRoute()` o `renderWithProviders()` de `src/test/render.tsx`.
- Consultas por rol y texto accesible; nada de `querySelector` ni `data-testid` salvo último recurso.
- `fetch` sustituido con `vi.stubGlobal('fetch', ...)`; cubrir carga, éxito, error, vacío y sin permiso.

## E2E (Playwright)
- Contra `docker compose up` (`DOW_E2E_URL`) con carpetas locales de prueba como ubicaciones; un fichero por flujo
  de usuario de la fase.
- Datos de prueba creados por la propia prueba vía API; sin dependencias entre tests.
