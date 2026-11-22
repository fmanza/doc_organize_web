# PLAN + AUDIT_PLAN — Contexto en orden de trabajo (2026-11-22)

Skill: `new-feature` (web). Solo PLAN y AUDIT_PLAN; sin implementar. Parte de la fase F3 del plan general de IA
(F0 agente · F1 limpieza · F2 uso con tokens · **F3 reorganizar Contexto** · F4 memoria IA · F5 cierre).

## Contexto: cómo está hoy

La página `/projects/:id/context` es una sola columna de tarjetas, en este orden (`ContextPage.tsx:183-266`):

| # | Bloque | Problema de orden |
|---|---|---|
| 1 | Resumen del contexto (o «No hay contexto») | Correcto arriba |
| 2 | Aviso de contexto desactualizado | Correcto |
| 3 | **Construir / Reconstruir** (selector de catálogo, plantilla, carpeta, umbral, sitio, IA, botón) | Pide construir **antes** de ver la taxonomía con la que se construye |
| 4 | Manifiesto (solo con catálogo «Manifiesto»): borrador con IA, **agente**, editor, comprobar, guardar, versiones | Va **debajo** del botón Construir, aunque hay que definirlo antes; dentro, las dos formas de crearlo (borrador y agente) van antes del editor y las versiones al final |
| 5 | Perfil del proyecto | Siempre visible, separado del catálogo al que acompaña |
| 6 | Versiones de documentos | Es resultado de la construcción, pero va antes de los dominios |
| 7 | Dominios y documentos | El resultado principal, casi al final |
| 8 | Entregar | Correcto al final |
| 9 | Historial | Correcto al final |

Revisión, Calidad y Sitio son páginas aparte con «Volver al contexto»: no hay forma de ver dónde se está dentro del
proceso ni de saltar entre ellas.

**Hechos que condicionan el diseño (comprobados):**

- «Reconstruir» ya depende de que exista un contexto: título y botón (`ContextPage.tsx:496`, `:609`) y el aviso de
  desactualización. No hay que cambiar esa regla.
- `profile.md` se usa con **cualquier** catálogo, no solo con plantilla: `ContextBuilder` hace
  `compose_profile(manifest.profile if manifest else None, root)` (`doc_organize/context/context_builder.py:479-481`) y
  lo manda a clasificar **y a describir** con IA (`:531`, `:543`, `:550`). Ocultarlo fuera de «Plantilla» dejaría un
  texto activo e invisible (ver AUDIT_PLAN, D1).
- Con catálogo «Manifiesto», el perfil del cuerpo del manifiesto y `profile.md` se concatenan: hay dos sitios para lo
  mismo.
- `selection` (catálogo y plantilla) y el borrador del manifiesto ya viven en `ContextPage` (sesión
  2026-11-17-manifest-from-template), así que se pueden repartir entre pasos sin mover estado al servidor.
- El router es de datos (`createBrowserRouter`): `useBlocker` está disponible para avisar de un borrador sin guardar.

## Inputs

| Campo | Valor |
|---|---|
| Objetivo | Ordenar Contexto en pasos: **1 Taxonomía → 2 Construir → 3 Resultado → 4 Revisar → 5 Calidad → 6 Entregar**, con una navegación común en las cuatro rutas de contexto; perfil ligado al catálogo |
| Rutas | Frontend: `features/context/ContextPage.tsx` (reparto en pasos), `ContextNav.tsx` **(nuevo)**, `TaxonomyStep.tsx` **(nuevo**: selector de catálogo + plantilla + manifiesto + perfil), `BuildCard` (sin selector de catálogo), `ManifestCard.tsx` (orden interno), `ProfileCard.tsx` (regla de visibilidad), `ReviewPage.tsx`, `QualityPage.tsx`, `SiteViewerPage.tsx` (usan `ContextNav`), `useContext.ts` (`contextStep`, `defaultStep`), `useUnsavedDraft.ts` **(nuevo)**, `i18n/es/features.json`; tests `context.test.tsx`, `manifest.test.tsx`, `profile.test.tsx`, `ai.test.tsx`, `agent.test.tsx`, `freshness.test.tsx`, `contextnav.test.tsx` **(nuevo)**; e2e `context.spec.ts`, `w9-contexto.spec.ts`, `ai.spec.ts`. Docs: `docs/guides/contexto.md`, `CHANGELOG.md` |
| Contrato HTTP | **Sin cambios** |
| Pantallas | Contexto y sus subpáginas (detalle abajo) |
| Permisos | Los de hoy: ver, cualquier miembro; construir y editar, editor con destino rw; borrar, owner |
| doc_organize | Ninguno nuevo |
| Restricciones | Sin dependencias nuevas (Mantine `Tabs`/`Stepper` ya están en `@mantine/core`); sin migraciones; sin cambios de backend |

## PLAN

### 1. Navegación común: `ContextNav`

Cabecera compartida por `/context`, `/context/review`, `/context/quality` y `/context/site`:

```
← Proyecto X
Contexto · [estado: construido el 21/11 · 1.234 documentos · desactualizado]
[1 Taxonomía] [2 Construir] [3 Resultado] [4 Revisar] [5 Calidad] [6 Entregar]   Historial
```

- Los pasos 1, 2, 3 y 6 son pestañas de `/context` con `?paso=taxonomia|construir|resultado|entregar`; 4 y 5 son las
  rutas existentes. Se mantienen las URLs actuales: un enlace viejo a `/context` sigue funcionando.
- Paso por defecto: **Taxonomía** si no hay contexto; **Resultado** si lo hay.
- Pasos sin contexto (Resultado, Revisar, Calidad, Entregar): visibles pero deshabilitados con un `title` que explica
  «Construye primero el contexto».
- Sin permiso de construir: «Construir» no aparece; «Taxonomía» se ve en solo lectura.
- Accesible: `nav` con `aria-label`, el paso actual con `aria-current="page"`; en móvil, las pestañas se desplazan en
  horizontal (`Tabs` con `ScrollArea`) en vez de partirse.
- «Historial» pasa a ser una pestaña más del final (`?paso=historial`), no un bloque al pie de la página.

### 2. Paso 1 · Taxonomía (definir antes de construir)

Orden interno:

1. **«¿Cómo se clasifican los documentos?»**: el selector de catálogo **sale de `BuildCard`** y viene aquí, agrupado
   en dos bloques con su ayuda:
   - *Sin taxonomía*: «Por carpetas» (hoy «Descubrir dominios») · «Lista de dominios» (hoy «Catálogo propio»).
   - *Con taxonomía*: «Plantilla» · «Manifiesto del proyecto».
   Los valores que se mandan a la API (`discover`, `domains`, `template`, `manifest`) no cambian; solo los textos.
2. Según el catálogo:
   - *Por carpetas*: solo la explicación (no lee el contenido).
   - *Lista de dominios*: el `TagsInput` (sale de `BuildCard`).
   - *Plantilla*: selector + «Personalizar para este proyecto» (copia al manifiesto, como hoy).
   - *Manifiesto*: `ManifestCard`, con el orden interno del punto 4.
3. **Perfil del proyecto**, según la regla D1 (punto 3).
4. Pie: «Siguiente: Construir →», deshabilitado si la taxonomía no está lista (lista vacía, sin plantilla o borrador del
   manifiesto sin guardar; es la misma condición `ready` de hoy, que pasa a `useContext.ts` como `selectionReady`).

### 3. Perfil del proyecto (D1, recomendado)

| Catálogo | Perfil |
|---|---|
| Plantilla | **Visible y editable**: es la forma de añadir lo propio del proyecto a una plantilla que no se puede tocar |
| Por carpetas / Lista de dominios | Visible **solo si** está activa la IA (clasificar o describir) en Construir, o si ya existe un `profile.md`; con el texto «Solo lo usa la IA» |
| Manifiesto | **Plegado**. Si existe `profile.md`, aviso: «Este proyecto tiene además un perfil aparte, que se añade al del manifiesto» con «Ver» y «Copiar al cuerpo del manifiesto» (copia al borrador; nunca guarda ni borra solo). Si no existe, no se muestra: el perfil va en el cuerpo del manifiesto |

Así se cumple la intención de la petición (el perfil acompaña a la plantilla) sin esconder un texto que la librería
sigue usando.

### 4. Manifiesto: orden interno de `ManifestCard`

De «crear → editar → comprobar → guardar → historial»:

1. Estado: válido / no válido, recuento de dominios y tipos, avisos del front matter, «el contexto se construyó con otra
   versión».
2. **Crear o mejorar** (plegable, cerrado si ya hay manifiesto): pestañas «Borrador con IA» (`DraftPanel`) · «Diseñar con
   el agente» (`AgentPanel`) · «Desde una plantilla» (enlace al selector del punto 2).
3. Editor.
4. «Comprobar manifiesto» (`RulesCheck`) y «Guardar», juntos bajo el editor.
5. Versiones del manifiesto y «Borrar manifiesto» al final, en una zona plegable «Historial y borrado».

Sin cambios de comportamiento: mismas mutaciones, `If-Match`, confirmaciones y foco.

### 5. Paso 2 · Construir

- Cabecera con **lo que se va a usar**: «Taxonomía: Plantilla «x» · Perfil: sí» y el enlace «Cambiar» (vuelve al paso 1).
- Parámetros: carpeta (fija si ya hay contexto), umbral, sitio.
- IA: clasificar y describir, con sus avisos de envío de datos.
- Botón «Construir» o «Reconstruir» (regla actual, sin cambios).
- El aviso de desactualización «Reconstruir» lleva a `?paso=construir` en vez de hacer scroll.

### 6. Paso 3 · Resultado

Resumen (los recuentos y avisos de hoy) → **Dominios y documentos** → Versiones de documentos. Los botones
«Revisar», «Calidad» y «Ver sitio» del resumen desaparecen: ahora están en `ContextNav`. «Borrar contexto» (owner) se
queda en el resumen, separado y en rojo.

### 7. Pasos 4 y 5 · Revisar y Calidad

Sin cambios internos: se sustituyen `BackLink` + título por `ContextNav`. Orden: Revisar (decisiones de personas) va
antes que Calidad (medir contra la referencia), que puede usar esas decisiones.

### 8. Paso 6 · Entregar

`DeliveryCard` + «Ver sitio» (ruta `/context/site`, que también usa `ContextNav`).

### 9. Borrador sin guardar

`useUnsavedDraft(dirty)`: `useBlocker` al salir de `/context` con un borrador del manifiesto o del perfil sin guardar,
y `beforeunload` al cerrar la pestaña. Al cambiar de paso dentro de `/context` no se pierde nada (`Tabs keepMounted`).

### 10. Textos y documentación

- `i18n`: `context.steps.*`, `context.catalog.*` (nuevos nombres y grupos), ayudas del perfil según catálogo.
- `docs/guides/contexto.md`: la guía sigue los seis pasos; capturas si las hay.
- `CHANGELOG.md`: web **2.1.0** (cambio visible de la interfaz, sin cambios de API).

### 11. Tests

- Unitarios: paso por defecto con y sin contexto; pasos deshabilitados; `?paso=` respetado; selector en Taxonomía;
  `BuildCard` sin selector y con el resumen de lo que usa; las tres reglas del perfil (D1); «Copiar al cuerpo del
  manifiesto»; aviso de borrador sin guardar al ir a Revisar; solo lectura sin permiso.
- e2e: actualizar los selectores de `context.spec.ts`, `w9-contexto.spec.ts` y `ai.spec.ts` al nuevo recorrido.
- `npm run lint`, `npm run typecheck`, `npm test` (desde PowerShell con `C:\`) y e2e.

### Riesgos (detalle en AUDIT_PLAN)

Borrador perdido al navegar, perfil invisible pero activo, tests e2e frágiles, pestañas en móvil, alcance que crece
hacia F3b/F4.

---

## AUDIT_PLAN

### Riesgos funcionales

| Id | Riesgo | Severidad | Corrección en el plan |
|---|---|---|---|
| A1 | **La petición («perfil solo con Plantilla») choca con la librería**: `profile.md` entra en clasificar y describir con cualquier catálogo. Ocultarlo fuera de Plantilla deja un texto activo e invisible que cambia los resultados sin que nadie lo vea | Alta | Regla D1 (punto 3): visible con Plantilla; con carpetas/lista solo si hay IA o ya existe; con Manifiesto, aviso + «Copiar al cuerpo». **Requiere confirmación del mantenedor** |
| A2 | Al sacar el selector de catálogo de `BuildCard`, quien entra directamente en «Construir» no ve qué taxonomía usa | Media | Cabecera «Taxonomía: … · Cambiar» en el paso 2 (punto 5) |
| A3 | Borrador del manifiesto o del perfil perdido al ir a Revisar/Calidad (otra ruta) | Alta | `useUnsavedDraft` con `useBlocker` + `beforeunload`; `Tabs keepMounted` dentro de `/context` |
| A4 | `BuildCard` está montado con `key={builtAt}` para reiniciar opciones tras construir; con pestañas siempre montadas, el reinicio sigue igual. Comprobar que el selector, ya fuera de `BuildCard`, no se reinicia mal | Baja | Ya se deriva de `built_at` sin efectos (`ContextPage.tsx:91-118`); test que lo cubra |
| A5 | Paso por defecto «Resultado» oculta el aviso de desactualización si está en otro paso | Media | El aviso va en `ContextNav` (cabecera común), no en un paso |
| A6 | Un enlace o marcador viejo a `/context` ya no cae en el sitio de antes | Baja | Misma URL; paso por defecto razonable; `?paso=` inválido → por defecto |
| A7 | Usuarios sin permiso de construir: pasos vacíos | Media | «Construir» oculto; «Taxonomía» en solo lectura (manifiesto y perfil `readOnly`, como hoy) |

### Riesgos técnicos

| Id | Riesgo | Corrección |
|---|---|---|
| T1 | `ContextPage.tsx` tiene 1.129 líneas; repartirla puede tentar a refactorizar más de lo necesario (la skill lo prohíbe) | Solo se **mueven** componentes existentes a `TaxonomyStep.tsx`/`ContextNav.tsx`; nada de cambiar hooks ni mutaciones. Diff revisable por bloques |
| T2 | Los e2e dependen de que todo esté en una página | Actualizarlos en el mismo PR; usar `getByRole('tab', …)` para cambiar de paso |
| T3 | Pestañas en móvil (seis pasos + historial) | `Tabs` desplazable; probar a 360 px |
| T4 | `useBlocker` con mutaciones que navegan tras éxito (`navigate('/runs/…')` al construir) dispararía el aviso | El bloqueo se omite cuando no hay borrador; construir ya está bloqueado con borrador sucio (`blockedByDraft`) |
| T5 | Dos listas de textos para los catálogos (contexto construido muestra `catalog_kind` con `context.catalog.*`) | Cambiar las etiquetas en un solo sitio; los contextos antiguos `domains` se ven como «Lista de dominios» |

### Seguridad

Sin cambios de API, permisos ni datos. El aviso «Copiar al cuerpo del manifiesto» copia texto al borrador del cliente;
se guarda por el `PUT` existente con `If-Match`. Sin superficie nueva.

### Simplificaciones

- S1: **no crear rutas nuevas**; pasos con `?paso=` y las tres rutas existentes.
- S2: mantener los cuatro valores de catálogo en la API; convertir «Lista de dominios» en asistente del manifiesto queda
  para F3b.
- S3: «Instrucciones del proyecto» únicas para todas las tareas (incluido el agente) quedan para F3b; aquí el perfil solo
  cambia de sitio y de regla de visibilidad.
- S4: `Stepper` de Mantine descartado: obliga a un orden lineal y aquí hay que poder saltar (p. ej., a Entregar).

### Decisiones pendientes

- **D1** (bloqueante): regla de visibilidad del perfil, punto 3. Alternativa literal a la petición: solo con
  Plantilla, aceptando A1.
- **D2** (no bloqueante): paso por defecto con contexto: «Resultado» (recomendado) o «Construir».
- **D3** (no bloqueante): versión 2.1.0 propia o agrupada con F1/F2.

### Decisiones del mantenedor (2026-11-22)

- D1: **regla recomendada** (punto 3).
- D2: con contexto, se abre en **Resultado**.
- D3: **una sola versión** con F1 (retirar Copilot) y F2 (uso con tokens): rama `feature/2.1`, web 2.1.0.

### Veredicto

**GO** (era GO_CONDICIONAL; la condición 1 queda cumplida).

Condiciones para IMPLEMENT:

1. ~~D1 decidida por el mantenedor.~~ Cumplida.
2. Sin cambios de backend ni de contrato: si aparece la necesidad, se para y se replantea.
3. A3 (borrador sin guardar) y A5 (aviso en la cabecera) con test propio.
4. e2e actualizados en el mismo PR; `lint`, `typecheck`, `npm test` y e2e en verde.
5. `docs/guides/contexto.md` y `CHANGELOG.md` en el mismo PR.

---

## IMPLEMENT (2026-11-22)

Solo frontend, en `feature/2.1` (sin backend, contrato ni migraciones).

| Fichero | Cambio |
|---|---|
| `features/context/useContext.ts` | `selectionNotReady`, `CONTEXT_STEPS`, `resolveStep`, `stepHref`, `profileMode` (D1), `appendProfile` |
| `features/context/ContextNav.tsx` (nuevo) | Cabecera común: volver, título, estado, pasos y aviso de desactualizado (sale de `ContextPage`) |
| `features/context/TaxonomyStep.tsx` (nuevo) | Paso 1: catálogo agrupado (`Radio.Group`), lista de dominios, plantilla y «Personalizar», manifiesto, perfil y «Siguiente: Construir» |
| `features/context/UnsavedDraft.tsx` (nuevo) | `useBlocker` al cambiar de ruta con borrador y `beforeunload` |
| `features/context/ContextPage.tsx` | Pasos con `?paso=` y paneles `hidden` (siempre montados); `BuildCard` sin selector, con «Taxonomía: … · Cambiar» y el motivo si no está lista; `Summary` sin botones de navegación; `SiteCard` en Entregar; dominios en `TaxonomyStep` (estado subido a la página) |
| `features/context/ManifestCard.tsx` | Orden: estado → «Crear o mejorar con IA» (plegable, montado) → editor → comprobar/guardar → versiones → borrar |
| `features/context/ProfileCard.tsx` | Modos `full`/`manifestNotice`/`hidden`; `onDirtyChange`; «Ver el perfil» y «Copiar al cuerpo del manifiesto» |
| `ReviewPage.tsx`, `QualityPage.tsx`, `SiteViewerPage.tsx` | `ContextNav` en lugar de `BackLink` + `h2` |
| `i18n/es/features.json` | Nombres «Por carpetas» y «Lista de dominios»; `context.steps`, `context.taxonomy`, `context.unsaved`, `context.build.notReady`, avisos del perfil; fuera `review.back`, `context.site.back`, `context.build.unsavedManifest` |
| Tests | Adaptados `context`, `ai`, `agent`, `manifest`, `freshness`; `profile` reescrito (4 casos D1); `steps.test.tsx` nuevo (pasos, motivo, D1, aviso al salir) |
| e2e | `context.spec.ts`, `w9-contexto.spec.ts`, `ai.spec.ts` al recorrido por pasos (**no ejecutados**) |
| Docs | `docs/guides/contexto.md` («Los pasos (2.1)», nombres nuevos, perfil por catálogo); `CHANGELOG.md` en `[Unreleased]` |

**Desviación del plan (D1, punto 3):** con «Por carpetas» o «Lista de dominios», el perfil se muestra si hay IA
**configurada** (clasificar o describir), no si está activada en Construir: evita atar el paso 1 al estado del paso 2.

## AUDIT_CODE (2026-11-22)

Comprobado: `prettier --check`, `tsc -b` (incluye e2e), `eslint .`, `vitest run` (27 ficheros, 169 tests) y
`zensical build --strict` en verde.

| Id | Hallazgo | Estado |
|---|---|---|
| C1 | «Copiar al cuerpo del manifiesto» no aparecía: la página leía el manifiesto con `getQueryData`, que no repinta al llegar los datos | Corregido: se lee al pulsar (lo detectó el test nuevo) |
| C2 | La línea de estado decía «1 documentos clasificados» | Corregido con plural (`status_one`/`status_other`) |
| C3 | Pulsar «Copiar al cuerpo» dos veces añade el perfil dos veces | Aceptado (nit): se ve en el editor y no se guarda solo |
| C4 | Con el perfil sin guardar, «Construir» o «Borrar contexto» (navegan a la ejecución) muestran el aviso de salir | Aceptado: es lo esperado |
| C5 | `manifestDirty` en `ContextPage` sigue leyendo con `getQueryData` (no reactivo) | Preexistente; sin efecto visible (repinta al teclear). No se toca (sin refactor) |
| C6 | Los títulos de Revisar, Calidad y Sitio bajan a `h3` bajo el `h2` «Contexto» de la cabecera | Intencionado (jerarquía) |

**Pendiente antes de publicar:** ejecutar los e2e con la imagen construida desde esta rama, y revisar en el navegador
el móvil (pestañas con desplazamiento horizontal, 360 px).

Veredicto AUDIT_CODE: **GO_CONDICIONAL** (e2e pendientes).
