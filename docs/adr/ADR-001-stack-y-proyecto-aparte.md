# ADR-001 — Stack y proyecto aparte

- **Estado**: Aceptado (implementado en la Fase 0, 0.1.0)
- **Fecha**: 2026-10-31

## Contexto

doc_organize incluye hoy una web FastAPI + Jinja (`src/doc_organize/web/`) con usuarios multi-tenant
(`src/doc_organize/auth/`). Mezclar la librería con la aplicación obliga a publicarlas juntas, arrastra dependencias
web a quien solo quiere la librería y dificulta una interfaz rica (progreso en vivo, tablas de 100 000 filas). El mismo
problema se resolvió en util_bbdd con util_bbdd_web (D1).

## Decisión

1. **Proyecto aparte** con su propio ciclo de versiones: `doc_organize_web` consume doc_organize como librería
   fijada (ADR-006). doc_organize pasa a ser librería pura + CLI (tareas `L-*`).
2. **Monorepo** backend + frontend + contrato:

    ```text
    backend/   FastAPI + Pydantic 2, Python 3.12, SQLAlchemy 2 + Alembic sobre SQLite, uv
    frontend/  React 19 + TypeScript 5.9 estricto + Vite, Mantine, React Router, TanStack Query, i18next, npm
    openapi/   openapi.json exportado del backend → frontend/src/api/schema.d.ts (openapi-typescript + openapi-fetch)
    ```

3. **Un origen**: la API sirve la SPA en `/` y la API en `/api`, sin CORS, detrás de un proxy TLS.
4. **SQLite** (`config.db`, WAL) con tipos portables y Alembic: cambiar de motor es cambiar la URL y el driver (D8).
5. **Versiones como util_bbdd_web 1.10.1** para no divergir: Python 3.12.14, Node 24.21.0, uv 0.13.1, React 19.3,
   Mantine 9.6, TypeScript 5.9 (openapi-typescript 7 exige `^5` y typescript-eslint 8 `<6.1`).
6. **Cadena de suministro**: solo versiones publicadas hace ≥ 2 semanas (`exclude-newer` en uv, `--before` en npm,
   *cooldown* de 14 días en Dependabot), lockfiles con hash e imágenes base con versión exacta. **Suspendida hasta la
   1.0** (decisión del mantenedor, 2026-11-01): se mantienen lockfiles con hash y versiones exactas, y la Fase 10 la
   reactiva.

## Consecuencias

- Dos repositorios avanzan en paralelo: cada fase de la web declara la versión de doc_organize que necesita
  (columna «Requiere» del ROADMAP) y la web integrada queda congelada (solo hotfix) hasta su retirada (`PARIDAD.md`).
- La imagen incluye Docling y torch (CPU): mucho mayor que la de util_bbdd_web (ver ADR-006 y el CHANGELOG).

## Alternativas descartadas

- Seguir con la web Jinja dentro de doc_organize: no resuelve el acoplamiento ni la interfaz.
- Next.js o SSR: añade un runtime Node en producción sin necesidad; la SPA estática basta.
