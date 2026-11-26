# Plan de la 3.0.0

Versión **mayor**: rompe el contrato HTTP a propósito para retirar la compatibilidad heredada, tipar los resultados de
las ejecuciones y partir de una línea base de migraciones. Sale del informe `/tech-debt` de la 2.7.0 (veredicto
`DEUDA_MENOR`), después de la 2.8.0 de mantenimiento. Veredicto del AUDIT_PLAN: **`GO_CONDICIONAL`** (condiciones al
final).

Solo se podrá actualizar a la 3.0 desde la **2.7.x o la 2.8.x**: las dos están en la revisión Alembic `0033`.

## Lo heredado que se retira

| Elemento | Origen | Datos afectados |
|---|---|---|
| `deleted_projects` y `LocationProjects.deleted` | Proyectos borrados que retenían ubicaciones (antes de la migración `0029`) | Ninguno: desde `0029` siempre vale 0 |
| `collision` y `collisions_count` | Rodeo de G30 (colisiones de nombre en doc_organize 0.13) | Contextos construidos con 0.13: pierden el aviso |
| Reescritura del `source_path` absoluto | Rodeo de G23 (JSON de doc_organize < 0.12.0) | Esos JSON muestran solo el nombre del fichero y piden reconvertir |
| `legacy_variables` | Variables de entorno de la IA 1.x y de Copilot | Ninguno en la BD; solo el entorno |
| `legacy_format` | Aviso de front matter 1.x de las plantillas | Ninguno |
| `taxonomy_templates.markdown_v1` | Solo servía para bajar la migración `0017` | Se borra |

Se **mantienen** `implicit_axes` y `migrate_markdown_v1`: la librería sigue leyendo el formato 1.x y las versiones
antiguas del manifiesto se pueden restaurar.

## PRs, en orden

| PR | Tipo | Contenido | Depende de |
|---|---|---|---|
| 0 | `refactor` / `test` | Partir `update_user`; `httpx2` para el `TestClient` de Starlette (si cumple los 14 días); volcar el esquema que deja la cadena `0001→0033` en un fixture | — |
| 1 | `refactor(db)` | Squash de Alembic: una línea base **con id `0033`**, DDL copiado del fixture y datos semilla literales; puerta de versión en `alembic/env.py`; test contra el snapshot; ADR-018 | 0 |
| 2 | `feat!` | Retirar lo heredado: migración `3001` (borra las tres columnas y deja en el log los proyectos con colisiones), código, claves de i18n, OpenAPI y cliente; G23 sin exponer rutas del contenedor | 1 |
| 3a | `refactor(backend)` | Un modelo `*Result` por operación (campos opcionales, `extra="allow"`), las operaciones devuelven modelos y las columnas JSON usan un `TypeDecorator` de Pydantic | 2 |
| 3b | `feat!` | `RunOut` como unión discriminada por `operation` con `params` y `result` tipados; `QualityRunOut.result` tipado; el frontend quita los casts y `useFollowedRun` pasa a ser genérico | 3a |
| 4 | `test(frontend)` | jsdom 31: la prueba del menú móvil pasa a Playwright con un viewport estrecho; en Vitest queda el cableado ARIA | — |

## Impacto en el contrato

- `GET /locations/{id}/usage`: sin `deleted_projects`.
- `GET /admin/ai-settings`: sin `legacy_variables`.
- `front_matter` de plantillas y manifiesto: sin `legacy_format`.
- Contexto: sin `collisions_count`; documentos sin `collision`; el filtro `only=collision` desaparece.
- `RunOut` (`/runs`, `/runs/{id}`, `POST /projects/{id}/runs`): `params` y `result` tipados por operación.
- `QualityRunOut.result` tipado.

## Guía de actualización (para `docs/guides/despliegue.md`)

1. Si la instancia está por debajo de la 2.7: instalar la 2.8.x y arrancarla una vez.
2. Copia de seguridad de `config.db`.
3. Quitar del entorno `DOC_ORGANIZE_LITELLM_<CLIENTE>_*`, `DOC_ORGANIZE_GITHUB_USERNAME` y `DOC_ORGANIZE_GITHUB_PAT`.
4. Reconstruir los contextos que la migración `3001` liste con colisiones.
5. «Forzar reconversión» en los proyectos convertidos con doc_organize < 0.12.0.
6. Clientes propios de la API: regenerar contra el nuevo `openapi.json`.
7. Volver atrás: `alembic downgrade 0033` con la imagen 3.0 y después la imagen 2.8.

## AUDIT_PLAN

**Riesgos funcionales.** Ejecuciones antiguas con resultados de otra forma podrían dar 500 al validar la respuesta:
campos opcionales, `extra="allow"`, fixtures con resultados históricos y, si la validación falla, `result=None` con
log. La vista genérica de resultados tiene que seguir funcionando.

**Riesgos técnicos.** La línea base puede no coincidir con el esquema que deja la cadena (test contra el snapshot).
Los modelos de agentes y evaluación replican los de doc_organize y pueden desfasarse al subir la librería (test de
contrato en la capa anticorrupción). Con el `TypeDecorator`, comprobar que SQLAlchemy detecta los cambios.

**Riesgos de datos.** Al bajar `3001` se pierden los valores de `collision` (dato muerto). Una BD anterior a `0033`
queda bloqueada por diseño, con un mensaje claro.

**Seguridad.** G23 no puede mostrar la ruta del contenedor. La puerta de versión no muestra la ruta de la BD.
`httpx2` debe cumplir los 14 días.

**Pendiente de verificar.** Python 3.13 (el `uv.lock` solo trae ruedas cp312 de torch y docling); TypeScript 7 con
typescript-eslint y Vite; si los permisos de los roles base cambiaron después de `0009`; la fecha de `httpx2`.

**Fuera de la 3.0.** Reutilizar la app entre tests (contaminaría el estado del limitador entre tests); Python 3.13 y
TypeScript 7 (estudio aparte para la 3.1); G47 (depende de doc_organize).

## Condiciones del veredicto

1. La 2.8.x publicada como puente y el snapshot de `0033` guardado antes del PR 1.
2. La línea base con id `0033`, la puerta de versión y el test del snapshot en verde.
3. G23 sin exponer rutas del contenedor.
4. Fixtures de resultados históricos antes del PR 3b.
5. Python 3.13 y TypeScript 7 fuera de la 3.0.
