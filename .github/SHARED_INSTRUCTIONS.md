# Instrucciones Compartidas: Claude Code + GitHub Copilot

Fuente canónica para trabajar en `doc_organize_web` con asistentes de código. Los entry points de cada plataforma
(`CLAUDE.md`, `.github/copilot-instructions.md`) solo añaden especialización y remiten aquí.

---

## Rol esperado

Actúa como **ingeniero de software senior especializado en entorno web**:

- SPAs con React + TypeScript (Vite, React Router, TanStack Query, Mantine), accesibilidad WCAG 2.2 AA.
- APIs HTTP con FastAPI + Pydantic v2, contrato OpenAPI, errores RFC 9457, progreso por SSE.
- Seguridad de aplicaciones web (OWASP ASVS nivel 2 / Top 10), sistemas multiusuario, manejo seguro de rutas del
  sistema de ficheros.
- Contenedores Docker (variantes CPU/GPU), CI/CD, SQLite en producción (WAL), jobs largos en segundo plano.
- Volúmenes grandes de documentos (~100 000 documentos / ~1 TB por proyecto) en carpetas locales y de red (SMB/NFS).
- Conoces `doc_organize` (Docling, OCR, deduplicación, contexto) como **librería consumida**, no como código propio.

---

## Proyecto

`doc_organize_web` es la aplicación web multiusuario (backend FastAPI + frontend React) que expone la funcionalidad de
la librería [doc_organize](https://github.com/fmanza/doc_organize) (versión fijada en `backend/pyproject.toml`):

- **Ubicaciones** origen/destino registradas por un admin (carpetas locales o SMB/NFS montadas fuera de la app).
- **Proyectos** con miembros que leen de un origen y escriben en un destino.
- **Ejecuciones** encoladas (cpu/gpu): escaneo y conversión a Markdown/JSON con OCR, caché, duplicados, contexto y
  taxonomías, clasificación con IA y exportaciones; progreso en vivo y resultados **agrupados por ejecución**.

Sustituye a la web integrada de doc_organize (`src/doc_organize/web/`, congelada: solo hotfix). Esa web es la
**referencia funcional** de paridad (`docs/plan/PARIDAD.md`), no código que copiar.

Plan por fases: [`docs/plan/ROADMAP.md`](../docs/plan/ROADMAP.md) y [`docs/plan/README.md`](../docs/plan/README.md).
Decisiones: `docs/adr/` (propuestas en [`docs/plan/ADRS_PROPUESTOS.md`](../docs/plan/ADRS_PROPUESTOS.md)).

---

## Arquitectura

```text
backend/app/
  core/                       # ajustes DOW_* + Docker secrets, logging JSON, errores RFC 9457, CSRF
  db/                         # engine SQLite (WAL), modelos SQLAlchemy 2, Alembic, backup
  api/                        # /api/health, /metrics; api/v1/ con los routers de negocio
  domain/                     # identity, locations, settings, projects, runs, cache, duplicates, context, ai
  integrations/doc_organize/  # ÚNICO punto que importa doc_organize (ADR-006)
  jobs/                       # worker, cola sobre runs (cpu/gpu), un subproceso por job (ADR-002)
  workspace/                  # carpetas por ejecución, run.json, ZIP en streaming, retención
frontend/src/
  app/ api/ features/ components/ i18n/ test/
openapi/openapi.json          # contrato; genera frontend/src/api/schema.d.ts
docs/ + zensical.toml         # documentación (GitHub y sitio Zensical)
docker/                       # Dockerfile multi-stage (runtime, runtime-gpu, backend-dev) + entrypoint
```

Tres zonas de datos (ADR-005): `config.db` y `projects/<id>/cache.db` en el volumen local `data`; artefactos por
ejecución en `workspace`; salidas del proyecto (Markdown, JSON, imágenes, duplicados, sitio) en la ubicación destino.

Detalle: [`.ai/architecture.md`](../.ai/architecture.md) y
[`docs/plan/ARQUITECTURA_PROPUESTA.md`](../docs/plan/ARQUITECTURA_PROPUESTA.md).

### Reglas no negociables

1. **No modificar doc_organize** desde este repositorio. Huecos de su API →
   [`docs/plan/DOC_ORGANIZE_GAPS.md`](../docs/plan/DOC_ORGANIZE_GAPS.md).
2. **No inventar APIs**: verifica firmas en el wheel instalado o en un clon local de doc_organize (solo lectura,
   p. ej. `../doc_organize/src/doc_organize`). Si no se puede, `PENDIENTE DE VERIFICAR`.
3. **Capa anticorrupción**: solo `backend/app/integrations/doc_organize/` importa `doc_organize` (test de arquitectura).
4. **Operaciones pesadas como jobs** (escaneo, OCR, deduplicación, contexto, IA, exportación) en el worker; la API solo
   encola y consulta.
5. **Ninguna ruta del sistema de ficheros sin pasar por el resolvedor de ubicaciones**; autorización antes que
   existencia; **nunca SQLite en una ubicación de red**.
6. **Secretos nunca en claro** (claves IA, PAT de GitHub, claves de la app): ni en SQLite, logs, `run.json`,
   respuestas ni mensajes de error.
7. **Operaciones que mueven o borran ficheros**: rol autorizado, ubicación `rw`, vista previa (modo seco) y
   confirmación explícita.
8. **Contrato primero**: cambio en la API → `scripts/export_openapi.py` + `npm run gen:api` en el mismo cambio.
9. Sin `git add -A`; sin commits ni push salvo petición.

**Repositorio público**: sin secretos, rutas internas, nombres de servidores reales ni documentos reales en código,
tests, fixtures, ejemplos o capturas (servidores ficticios como `//nas.example.internal/...`; documentos sintéticos).

---

## Principios de diseño

- **SOLID**: routers finos → servicios de dominio → repositorios/integraciones; dependencias inyectadas con `Depends`.
- **Backend**: tipado estricto (`mypy --strict`), Pydantic para todo lo que cruza HTTP, SQLAlchemy 2 (estilo 2.0,
  tipos portables), `pathlib.Path`, f-strings, `logging` con `extra` (nunca `print`), excepciones específicas.
- **Frontend**: componentes funcionales, datos solo vía TanStack Query y el cliente generado, textos en i18n (`es`),
  estados de carga/vacío/error/sin permiso en cada vista.
- **API**: `/api/v1`, recursos en plural, paginación `limit/offset` acotada, errores *problem details*, progreso SSE.
- **Escala**: todo listado de documentos, caché o duplicados paginado en servidor y virtualizado en cliente.

Reglas por tipo de archivo: [`.github/instructions/`](instructions/).

---

## Calidad y pruebas

### Comandos de desarrollo

Se activan a medida que la Fase 0 crea `backend/` y `frontend/`. Hasta entonces el CI solo valida los enlaces de la
documentación (`python scripts/check_doc_links.py`).

Backend (desde `backend/`, con [uv](https://docs.astral.sh/uv/) local):

```bash
uv sync --frozen
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen pytest
uv run --frozen python scripts/export_openapi.py --check   # contrato al día
```

Sin uv local, la misma imagen de herramientas que usa el CI (desde la raíz):

```bash
docker build -f docker/Dockerfile --target backend-dev -t doc_organize_web:backend-dev .
docker run --rm -v "$PWD/backend:/src/backend" -v "$PWD/openapi:/src/openapi" doc_organize_web:backend-dev uv run --frozen pytest
```

Frontend (desde `frontend/`):

```bash
npm ci
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm run gen:api        # tras exportar openapi/openapi.json
npm run e2e            # con la app levantada; primera vez: npx playwright install chromium
```

Documentación (desde la raíz; sitio con [Zensical](https://zensical.org), configuración en `zensical.toml`):

```bash
uv run --frozen --project backend --only-group docs zensical build --strict   # falla ante enlaces o anclas rotos
uv run --frozen --project backend --only-group docs zensical serve            # http://127.0.0.1:8000
```

Aplicación completa (desde la raíz):

```bash
python scripts/generate_secrets.py
docker compose up -d --build
curl http://127.0.0.1:8080/api/health
```

Las salidas largas de validación (`.txt`, informes) van a `build/logs/`.

### Estrategia de tests

- Backend: `tests/unit` (lógica pura), `tests/api` (TestClient con SQLite temporal y doc_organize sustituido en la
  capa anticorrupción), `tests/integration` (`@pytest.mark.integration`, conversión real con Docling, montajes de red;
  fuera del CI).
- Frontend: Vitest + Testing Library (consultas por rol/texto), `fetch` sustituido con `vi.stubGlobal`.
- E2E: Playwright contra `docker compose up` con carpetas locales de prueba como ubicaciones.
- Solo documentos **sintéticos** generados por los propios tests; ninguna prueba del CI depende de red, GPU ni
  modelos descargados.

### Dependencias

- Python: `uv.lock` con `exclude-newer` (solo versiones de ≥ 2 semanas; excepciones justificadas en `pyproject.toml`).
  doc_organize como wheel de su release en GitHub con hash (ADR-006).
- npm: `package-lock.json`, versiones exactas, instalación con `--before=<fecha>`.
- Imágenes base con versión exacta en `docker/Dockerfile`; Dependabot con *cooldown* de 14 días.

### Formato de commits

[Conventional Commits](https://www.conventionalcommits.org/) con scope opcional (`backend`, `frontend`, `docker`,
`docs`, `ia`): `feat`, `fix`, `hotfix`, `security`, `perf`, `refactor`, `test`, `docs`, `chore`, `release`.

---

## Flujo de trabajo

```text
PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
```

- Una fase del ROADMAP = un flujo `phase_implementation`. No adelantes historias de fases posteriores.
- Antes de planificar una fase, comprueba la columna «Requiere de doc_organize» del ROADMAP: si la versión necesaria
  no está publicada, el hueco va a `DOC_ORGANIZE_GAPS.md` con su rodeo temporal.
- Detente tras AUDIT_PLAN y espera aprobación antes de IMPLEMENT.
- En VERSION puebla `## Directrices para Futuras IAs` del `TRACEABILITY.md` de la sesión
  (plantilla en `.ai/sessions/TEMPLATE/`), formato `**[área]**: <hecho verificable>`, y marca la fila de
  `docs/plan/PARIDAD.md` que cubra la fase.

---

## Gobernanza de plataformas IA

| Archivo | Plataforma | Propósito |
|---|---|---|
| `.github/SHARED_INSTRUCTIONS.md` | Claude, Copilot | Fuente canónica |
| `CLAUDE.md` | Claude Code | Slash commands y hooks (importa SHARED con `@`) |
| `.github/copilot-instructions.md` | GitHub Copilot | Agentes y prompts en VS Code |
| `.github/AGENTS.md` | Ambas | Registro de agentes, prompts y slash commands |
| `.github/instructions/*.instructions.md` | Copilot (por `applyTo`); Claude por referencia | Reglas por tipo de archivo |
| `.ai/*.md`, `.ai/sessions/` | Ambas | Contexto persistente y sesiones |

**Checklist de sincronización** (único):

- [ ] Ninguna regla común copiada en un entry point
- [ ] Rutas relativas y existentes (o en `código` si llegan en una fase posterior)
- [ ] Sin términos ni rutas heredados de util_bbdd_web (`UBW_`, `util_bbdd`, motores, conexiones, `UTIL_BBDD_GAPS`)
      ni de la web integrada de doc_organize (Jinja, WebSocket, `mkdocs.yml`); la documentación se publica con
      Zensical (`zensical.toml`)
- [ ] Slash commands ↔ prompts ↔ `.github/AGENTS.md` coherentes
- [ ] Revisión con Config Reviewer (`/config-review`)

---

*Actualizado: 2026-10-31*
