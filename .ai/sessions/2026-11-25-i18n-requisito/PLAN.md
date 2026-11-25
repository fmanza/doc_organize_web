# PLAN — refactor: i18n como requisito en todo el frontend

- Skill: `refactor` · Fases: PLAN + AUDIT_PLAN (IMPLEMENT pendiente de aprobación)
- Base: `develop` en `37a7e34` (web 2.5.0; el PLAN se redactó sobre `c9f9ee1`, 2.3.2, sin diferencias en el alcance)

## Objective

Que todo texto visible del frontend salga de `frontend/src/i18n/es/*.json` y que el CI lo vigile, sin cambios
funcionales:

1. El ejemplo del perfil del proyecto (`PLACEHOLDER` de `ProfileCard.tsx`) pasa a i18n.
2. El locale de `Intl` (`'es-ES'` fijo en 3 ficheros, 6 formateadores) sale de un único sitio ligado al idioma de i18n.
3. Se quitan 13 claves sin uso.
4. El título de reserva `'Error'` (respuesta sin *problem details*) deja de estar en el código: lo pone i18n al mostrarlo.
5. Un test de Vitest falla si aparece texto visible fuera de `t()`, una clave usada que no existe o una clave sin uso.

## Scope and affected paths

| Fichero | Cambio |
|---|---|
| `frontend/src/i18n/index.ts` | Exporta `LANGUAGE = 'es'` (lo usa `init`) e `INTL_LOCALE` (`{ es: 'es-ES' }[LANGUAGE]`) |
| `frontend/src/components/format.ts` | `Intl.DateTimeFormat` / `NumberFormat` con `INTL_LOCALE` |
| `frontend/src/features/admin/AiUsagePage.tsx` | `money` y `number` con `INTL_LOCALE` |
| `frontend/src/features/admin/AiUsageCharts.tsx` | `compact` y `full` con `INTL_LOCALE` |
| `frontend/src/features/context/ProfileCard.tsx` | `placeholder={t('context.profile.placeholder')}`; fuera la constante |
| `frontend/src/i18n/es/features.json` | + `context.profile.placeholder` (texto idéntico, `\n`); − 13 claves (abajo) |
| `frontend/src/api/client.ts` | Reserva `title: result.response.statusText` (sin `'Error'`) |
| `frontend/src/features/health/useHealth.ts` | Ídem |
| `frontend/src/components/ErrorAlert.tsx` | `error.problem.title \|\| t('common.error')` y `detail ?? t('common.errorBody')` solo si falta |
| `frontend/src/features/admin/AiSettingsPage.tsx` (l. 317) | `detail \|\| title \|\| t('common.errorBody')` |
| `frontend/src/i18n/i18n.test.ts` (nuevo) | Test de vigilancia (abajo) |

Claves que se quitan: `roles.admin`, `roles.user`, `roles.saveLabel`, `listing.search`, `duplicates.keepLabel`,
`review.open`, `quality.open`, `ai.settings.testOk`, `ai.settings.testOkKey`, `ai.settings.testOkModel`,
`ai.settings.testFailed`, `ai.settings.testedTask`, `ai.settings.testModelLabel`. Ninguna aparece en el código ni en
los tests (`grep` exacto y por prefijo dinámico).

Fuera de alcance: los textos que manda el backend (*problem details* en español) se siguen mostrando tal cual; traducir
por `code` sería una decisión nueva (ADR), no un refactor. Placeholders técnicos `"es"` (código de idioma) y
`"doc-organize-classify"` (alias de modelo) se quedan, en la lista de permitidos del test con su motivo.

### Test de vigilancia (`i18n.test.ts`, `// @vitest-environment node`)

- Fuentes: `import.meta.glob('../**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true })`, sin tests,
  `test/` ni `schema.d.ts` (no hace falta `@types/node` en `tsconfig.app.json`). Análisis con la API de `typescript`
  (devDependency ya instalada, 5.9.3).
- **Texto visible fuera de `t()`**: `JsxText` con letras; atributos `aria-label`, `title`, `placeholder`, `label`,
  `description`, `alt`, `error`, `message` con literal de texto; propiedades `title`, `message`, `label`,
  `description`, `placeholder` con literal fuera de `t()`. Lista de permitidos explícita (`fichero → literal → motivo`).
- **Claves inexistentes**: cada `t('literal')` (también ramas de un ternario) existe en `core.json` + `features.json`
  (o con `_one`/`_other`, o es un grupo).
- **Claves dinámicas**: cada `` t(`prefijo${…}`) `` tiene alguna clave con ese prefijo.
- **Claves sin uso**: una clave cuenta como usada si aparece como literal en el código (cubre `t('x')` y las claves
  guardadas como valor, p. ej. `'auth.required'` de los esquemas zod), si empieza por un prefijo dinámico, o por sus
  formas plurales.

## HTTP contract

No cambia: solo frontend. Sin `export_openapi.py` ni `gen:api`.

## doc_organize usage (verified signatures)

No aplica. Los títulos de sección del ejemplo de perfil (`## Contexto del proyecto`, `## Reglas de desempate`,
`## Glosario`, `## Ejemplos`) son el formato de `profile.md` que describe `backend/app/domain/context/profile.py`: se
copian sin tocar.

## Risks

- **Texto de reserva visible**: hoy, una respuesta sin *problem details* y sin `statusText` (habitual con HTTP/2, p. ej.
  un 502 en HTML del proxy) titula el aviso «Error»; pasará a «Se ha producido un error» (`common.error`). Es el único
  cambio visible y es justo el objetivo; con *problem details* (lo normal) no cambia nada.
- **Formato**: `'es-ES'` sigue siendo el mismo locale, así que fechas y números salen idénticos.
- **Falsos positivos del test**: la heurística puede marcar literales técnicos; se resuelve con la lista de permitidos,
  no relajando la regla. Las claves guardadas como valor obligan a la regla «literal en el código = usada».
- **Rendimiento del test**: ~100 ficheros con `createSourceFile`: segundos, en entorno `node` (sin jsdom).
- **Windows**: ejecutar vitest desde `C:\…` (directriz de la sesión `2026-11-24-revision-docs`).

## Test strategy

- Nuevo `src/i18n/i18n.test.ts` (verde tras el cambio; se comprueba que falla con un texto fijo de prueba antes de
  quitarlo).
- Regresión: `npm test` completo — `context` (perfil), `admin/ai*` (uso e IA › Configuración), `colorScheme` y
  `scan` (errores 500 con `title: 'Error'`, que siguen mostrándose igual porque traen título), `documents`.
- `npm run format:check`, `lint`, `typecheck`, `build`.
- E2E: sin cambios esperados; los cubre el job `image` del CI.

## AUDIT_PLAN

- **Funcional**: sin cambios salvo el título de reserva (asumido). El placeholder del perfil es idéntico. Las 13 claves
  no se renderizan hoy.
- **Técnico**: `LANGUAGE`/`INTL_LOCALE` como constantes evita depender de `i18n.language` en tiempo de importación
  (los formateadores son de módulo). Importar `typescript` solo en un test no entra en el bundle (`vite build` no
  incluye `*.test.ts`). `import.meta.glob` con `?raw` es de Vite y funciona en Vitest.
- **Seguridad**: sin impacto; `ErrorAlert` sigue sin mostrar trazas.
- **Simplificaciones**: no se añade un plugin de ESLint (dependencia nueva, regla de 2 semanas y más configuración); el
  test cubre lo mismo y además las claves. No se traduce el `Error` de `main.tsx` (no llega al usuario).
- **Alcance**: acotado al frontend; sin backend, contrato, Docker ni migraciones. Entrada en `[Unreleased]` del
  CHANGELOG (`Changed`).
- **Documentación**: la regla va en `.github/instructions/frontend.instructions.md` (junto a «Textos con
  `useTranslation()`»): el test `src/i18n/i18n.test.ts` la hace cumplir y su lista de permitidos exige motivo.

## Verdict

**GO**
