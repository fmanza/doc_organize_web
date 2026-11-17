# PLAN + AUDIT_PLAN — El manifiesto de taxonomía solo con su catálogo (2026-11-17)

Skill: `new-feature` (web). Solo PLAN y AUDIT_PLAN; sin implementar.

> Revisión 6 (2026-11-17). **Fusionado en doc_organize_web 2.0.0**, que se publica a la vez que doc_organize 2.0.0
> (plan único: `doc_organize/.ai/sessions/2026-11-17-ai-2.0/PLAN.md`, §I y §Hitos W1-W9). La **parte 1** no cambia de
> diseño y es el hito W1 (puede empezar ya; **D17 decidida: se publica antes, como doc_organize_web 1.8.0** (publicada: #70, #71, tag `v1.8.0`; ver `TRACEABILITY.md`), sobre doc_organize 1.6.x; la `feature/2.0` de la web se crea después y sus migraciones empiezan en `0016`). La **parte 2** queda adaptada a
> ejes: en la librería 2.0 las facetas son **ejes** genéricos (dominio y tipo de material también), y la IA de facetas
> ya no es una fase propia sino el alcance `ai_scope="missing_axes"`. Cambios sobre la parte 2:
>
> - tabla `context_document_facets` → **`context_document_axis_values`** con columna `axis` (genérica para todos los
>   ejes, mismos índices); `ProjectContext.taxonomy_facets` → `taxonomy_axes`;
> - filtro `facet=clave:slug` → `axis=clave:slug` (mismas reglas O/Y, patrón y máximo de 20);
> - casilla «Completar las facetas con IA» (`ai_facets`, etapa `context_facets`, familia
>   `litellm_taxonomy_classification`) → selector de alcance `ai_scope` y etapa `context_ai`, con la familia única
>   `litellm` y modelo por tarea;
> - `classified_by` admite `rules`, `semantic`, `ai`, `human`; insignias con la marca de cada origen;
> - `implicit_facets` → `implicit_axes`; `write_context_documents_xlsx` con una columna por eje y hoja «Ejes»;
> - la condición 1 de la parte 2 pasa a ser «`2.0.0a1` instalada y firmas verificadas»; P8 (orden de migraciones) la
>   resuelve U5 del plan único.
>
> El resto de la parte 2 (P1-P13, tests) sigue valiendo con esos nombres. Al restaurar una versión del manifiesto
> guardada en v1, se guarda migrada a v2 (U4 del plan único).
>
> Revisión 5 (2026-11-17). Añade la **parte 2: facetas** (ejes adicionales de la taxonomía), que adopta doc_organize
> 1.7.0 (`doc_organize/.ai/sessions/2026-11-17-taxonomy-facets/PLAN.md`): guardar las facetas, filtrar por ellas,
> casilla de IA, Excel de los documentos del contexto y aviso de claves ignoradas. Va al final, con su propio
> AUDIT_PLAN; depende de que se publique la librería. La parte 1 (manifiesto) no depende de ella.
>
> Revisión 4 (2026-11-17). Incorpora al cuerpo del plan las correcciones de las auditorías de las revisiones 2 (A1-A10)
> y 3 (B1-B9): textos de «Descubrir dominios», bloqueo de «Construir» solo con el manifiesto, selección sin efectos,
> confirmación común, foco, versión en «Vaciar histórico», concurrencia con `etag`, orden versión-escritura y borrado
> seguro. Las tablas de auditoría quedan al final como registro; las condiciones vigentes son las 17 del final.
>
> Revisión 3 (2026-11-17). Añade versiones del manifiesto en la base de datos, «Borrar manifiesto» y «Restaurar la
> versión anterior» (puntos 4 y 5), a petición del mantenedor: deshacer la copia de una plantilla, se haya guardado o no.
> Cambian las tablas de entrada y se añade la sección «Revisión 3» al AUDIT_PLAN.
>
> Revisión 2 (2026-11-17). El mantenedor confirma que el bloque «Manifiesto de taxonomía» solo debe verse con el catálogo
> «Manifiesto del proyecto». Sustituye a la revisión 1, que lo dejaba siempre visible con un aviso.

## Contexto

Comprobado en todo el código de la web y de la librería (doc_organize 1.6.0): el manifiesto del proyecto
(`taxonomy_manifest.md`) **solo se usa al construir con «Manifiesto del proyecto»**.

| Dónde | Qué hace con el manifiesto |
|---|---|
| Encolar `context_build` con `catalog=manifest` (`domain/context/service.py:351-357`) | Lo lee y lo pasa a la librería: el único uso |
| Encolar con `discover`, `domains` o `template` | No lo lee |
| `ContextBuilder` (librería) | No lo carga por su cuenta: solo usa `taxonomy_manifest` si se le pasa |
| `GET` y `PUT /projects/{id}/context/taxonomy-manifest` | Mostrarlo y guardarlo (el propio bloque) |
| Run `taxonomy_draft` («Pedir borrador») | No escribe en él: el borrador va al editor y solo se guarda con `PUT` |

Hoy el bloque se muestra siempre, separado del selector, y confunde: con «Plantilla» parece que influye. Además, la ayuda
y la guía describen mal «Descubrir dominios»: dicen «a partir del contenido», y la librería usa el **nombre de la
carpeta inmediata** de cada documento (`DomainClassifier._best_domain`, modo descubrimiento), sin leer el contenido.

## Inputs

| Campo | Valor |
|---|---|
| Objetivo | (1) El bloque del manifiesto solo se ve con el catálogo «Manifiesto del proyecto». (2) Con «Plantilla», un botón copia la plantilla elegida al manifiesto y cambia a ese catálogo. (3) Corregir la descripción de «Descubrir dominios» y explicar en qué se diferencia del manifiesto. (4) Deshacer: versiones del manifiesto en la base de datos y «Restaurar la versión anterior». (5) «Borrar manifiesto» |
| Rutas | Frontend: `features/context/ContextPage.tsx` (`ContextPage`, `BuildCard`, `ManifestCard`, `ManifestVersions` nuevo), `useContext.ts` (hooks de versiones, borrar y restaurar), `i18n/es/features.json`, `context.test.tsx`, `context/ai.test.tsx`, `e2e/ai.spec.ts`. Backend: `alembic/versions/0015_manifest_versions.py` (nuevo), `db/models.py` (`ProjectManifestVersion`), `domain/context/service.py` (`save_manifest`, `delete_manifest`, `list_manifest_versions`, `restore_manifest`, `manifest_etag`), `domain/context/manifest_versions.py` (nuevo: guardar y recortar versiones), `jobs/operations/history_clear.py` (versión antes de vaciar), `jobs/operations/_files.py` (borrado seguro, reutilizado), `domain/identity/audit.py`, `api/v1/context.py`, `api/v1/schemas.py`; tests `backend/tests/api/test_context*.py`. Docs: `docs/guides/contexto.md`, `CHANGELOG.md`; `openapi/` y `schema.d.ts` regenerados |
| Contrato HTTP | Se reutilizan `GET /taxonomy-templates/{name}`; `GET /projects/{id}/context/taxonomy-manifest` gana `etag`; `PUT` exige `If-Match` y guarda la versión anterior. Nuevos: `DELETE …/taxonomy-manifest`, `GET …/taxonomy-manifest/versions`, `GET …/versions/{version_id}` y `POST …/versions/{version_id}/restore`. Errores nuevos: 409 `manifest_changed`, 428 `etag_required`, 404 `manifest_not_found`, 422 `manifest_version_invalid` |
| Pantallas | Página del contexto: tarjeta de construcción y bloque del manifiesto |
| Permisos | Los de hoy: ver, cualquier miembro; construir, copiar y guardar, editor con destino de lectura y escritura |
| doc_organize | Sin cambios: plantillas y manifiesto se validan con el mismo `validate_markdown`/`parse_taxonomy_template` |
| Restricciones | Migración `0015` aditiva (tabla nueva); sin dependencias; sin cambios en doc_organize. Borrar el fichero lo hace la web con su utilidad segura de `jobs/operations/_files.py` (la librería no tiene función para borrar el manifiesto; si se quiere, se pide como hueco nuevo sin bloquear) |

## PLAN

### 1. El bloque del manifiesto, solo con su catálogo

- **La selección del catálogo pasa a `ContextPage`**, porque ahora la necesitan la tarjeta de construcción y el bloque
  del manifiesto, y el botón del punto 2 la cambia:
  - Estado `selection = { catalog, template }` en `ContextPage`.
  - Valor inicial con una función compartida, `initialSelection(context)`: `catalog_kind` y `taxonomy_template_name` del
    contexto construido, o «Descubrir dominios».
  - `BuildCard` pasa a ser **controlado** para catálogo y plantilla (`selection`, `onSelectionChange`). El resto de su
    estado (dominios, carpeta, umbral, sitio, IA) sigue dentro.
  - Tras construir, la selección vuelve a partir del contexto nuevo **sin `useEffect`** (la regla
    `react-hooks/set-state-in-effect` lo impide): el estado guarda `{ builtAt, catalog, template }` y, si `builtAt` no
    coincide con el `built_at` del contexto, se usa `initialSelection(context)`. Es el patrón del menú plegable de
    `Layout`. Así, al terminar una construcción, la selección pasa a la del contexto nuevo aunque se hubiera cambiado
    mientras se construía.
- **Editores con destino `rw`** (ven la tarjeta de construcción): el bloque aparece justo debajo de la tarjeta, como
  parte del catálogo, solo con `selection.catalog === 'manifest'`. Al elegir otro catálogo desaparece, y el borrador sin
  guardar se conserva (vive en `ContextPage`), así que no se pierde al volver.
- **Sin tarjeta de construcción** (lector, o destino de solo lectura): no hay selector.
  - Si el contexto actual se construyó con el manifiesto, se muestra el bloque, de solo lectura como hoy.
  - Si no, un enlace discreto «Ver el manifiesto del proyecto» lo despliega, de solo lectura. El manifiesto puede
    existir aunque no se use, y es información del proyecto.
- **«Pedir borrador» (IA)** se mueve con el bloque: solo con «Manifiesto del proyecto». Antes de construir con el
  manifiesto hay que tenerlo, así que es el sitio natural.
- **Texto de introducción del bloque**: pasa a «Manifiesto de este proyecto: dominios y tipos de material con los que se
  clasifica al construir con este catálogo. Puedes escribirlo, partir de una plantilla o pedir un borrador a la IA.»

### 2. «Usar la plantilla como manifiesto del proyecto»

- **Dónde está:** en la tarjeta de construcción, junto al selector de plantilla, con `catalog === 'template'`, una
  plantilla elegida y permiso de edición. Botón secundario «Personalizar para este proyecto».
- **Al pulsarlo:**
  1. Si hay un borrador sin guardar o un manifiesto guardado distinto, confirmación en un `Modal`: «El texto del
     manifiesto se sustituye por el de la plantilla «Calidad». El manifiesto guardado no cambia hasta que guardes.»
     Es la **misma confirmación** (`replaceDraft(text, source)`) que usan «Pedir borrador» y «Restaurar», para que
     ningún camino sustituya un borrador sin avisar.
  2. Lee el Markdown con `GET /taxonomy-templates/{name}` (`queryClient.fetchQuery`, que aprovecha la caché si ya
     estaba).
  3. Lo deja como **borrador sin guardar** del manifiesto (estado en `ContextPage`), igual que hoy el borrador de la IA.
  4. Cambia la selección a «Manifiesto del proyecto». El bloque aparece con el texto y el aviso «Copiado de la
     plantilla «Calidad». Revísalo y guárdalo; después, construye» (`role="status"`), con un botón «Deshacer».
  5. **Foco**: el botón pulsado desaparece al cambiar de catálogo, así que el foco pasa al editor del manifiesto (si no,
     volvería a `body`).
- **El botón «Construir» con el manifiesto sin guardar**: «Construir» usa el manifiesto **guardado**, como hoy. **Solo
  con el catálogo «Manifiesto del proyecto»** y un borrador distinto del guardado, la tarjeta lo dice («Hay cambios sin
  guardar en el manifiesto: guárdalos antes de construir») y desactiva «Construir». Con otro catálogo, un borrador
  pendiente no bloquea nada.
- **Procedencia**: al construir con un manifiesto copiado de una plantilla, el contexto ya no guarda
  `taxonomy_template_name`; el resumen dice «Manifiesto del proyecto». La guía lo explica.
- **Nada se guarda sin «Guardar»**, que valida con la librería y audita como siempre.

### 3. Descripción correcta de los catálogos

- **Ayuda del selector** (`context.build.help.discover`), que hoy dice «doc_organize descubre los dominios a partir del
  contenido.». Pasa a: «Un dominio por cada carpeta: cada documento va al de la carpeta que lo contiene (los de la
  raíz, al de la carpeta escaneada). No lee el contenido.» Solo quedan sin clasificar los que no están bien convertidos
  o cuya carpeta no tiene letras ni números.
- **Guía** (`docs/guides/contexto.md`): se corrige la tabla de catálogos y se añade el apartado «¿Descubrir dominios o
  manifiesto?»:

  | | Descubrir dominios | Manifiesto del proyecto |
  |---|---|---|
  | Dominios | Uno por carpeta (nombre de la carpeta inmediata) | Lista cerrada del manifiesto |
  | Ejes | Dominio | Dominio y tipo de material |
  | Asignación | Por carpeta, sin puntuación (los de la raíz, al dominio de la carpeta escaneada) | Palabras del dominio y sus palabras clave (`keywords`) en el título y el contenido, más la carpeta, con umbral; el tipo de material, igual por separado |
  | Dominios nuevos | Sí, uno por carpeta | No |
  | Estado | Borrador | Confirmado |
  | Cuándo | Carpetas ya temáticas; primer contexto rápido | Vocabulario propio, independiente de las carpetas |

- **Umbral**: la guía dice que no afecta a «Descubrir dominios», porque todo documento con carpeta puntúa 1,0.
- **Manifiesto**: la guía dice que solo se usa con su catálogo y cómo partir de una plantilla.
- **Sin cambio de comportamiento**: solo textos. Si se quiere que «Descubrir dominios» lea el contenido, es una petición
  para doc_organize (hueco nuevo), fuera de este plan.

### 4. Versiones del manifiesto y «Restaurar la versión anterior»

**Modelo** (`ProjectManifestVersion`, migración `0015`, en `config.db`):

| Columna | Tipo | Notas |
|---|---|---|
| `id` | entero, PK | |
| `project_id` | FK a `projects`, `ON DELETE CASCADE` | Las versiones se van con el proyecto |
| `created_at` | fecha con zona | Cuándo se sustituyó esa versión |
| `created_by` | FK a `users`, `ON DELETE SET NULL` | Quién hizo el cambio que la sustituyó |
| `action` | `save` · `delete` · `restore` · `history_clear` | Qué cambio la sustituyó |
| `markdown` | texto, **nulo** = no había manifiesto | Contenido **anterior** al cambio, tal como estaba en el disco |
| `domains`, `material_types` | entero, nulos si no era válido | Para la lista, sin volver a validar |

Índice `(project_id, created_at)`. Se conservan las **5 últimas** por proyecto: al añadir la sexta se borra la más
antigua, en la misma transacción.

**Cuándo se guarda una versión** (siempre lo que había **antes**):
- `PUT` (guardar): se lee el fichero actual (si no hay, `markdown` nulo) y se guarda como versión antes de escribir.
  Si el texto nuevo es igual al actual, no se escribe ni se guarda versión.
- `DELETE` (borrar): lo que había.
- `restore`: lo que había antes de restaurar, para que restaurar también se pueda deshacer.
- `history_clear` («Vaciar histórico», B1): el job guarda la versión del manifiesto antes de vaciar la carpeta del
  proyecto, y su vista previa lo nombra («el manifiesto de taxonomía; se podrá restaurar desde Versiones»).
- Un manifiesto **cambiado fuera de la app** (editado en la carpeta compartida) se recoge igual: se guarda lo que haya
  en el disco en ese momento.

**Orden y fallos** (B3): la versión se guarda y se **confirma antes de escribir** el fichero. Si la escritura falla de
forma definitiva (error de la ubicación, `ManifestReplacedError`), se borra esa versión. Si se agota el tiempo
(`run_with_timeout`, la escritura puede seguir en segundo plano), la versión se conserva: es lo que había antes y
restaurarla es inocuo. Así el fichero nunca cambia sin versión.

**Concurrencia** (B2): `_check_writable` solo mira los runs en marcha, no dos peticiones a la vez. Por eso:
- `GET …/taxonomy-manifest` devuelve `etag` (SHA-256 del contenido en el disco, o `"none"` si no hay manifiesto).
- `PUT`, `DELETE` y `restore` lo exigen en la cabecera `If-Match`: sin ella, 428 `etag_required`; si el fichero cambió
  desde entonces (otro editor, un job, una edición fuera de la app), 409 `manifest_changed` («Otro usuario lo cambió:
  recarga para ver su versión»).
- Un cerrojo por proyecto en el proceso protege la sección crítica (leer → versión → escribir).
- La página guarda el `etag` con el manifiesto que muestra y lo envía; ante el 409, recarga el manifiesto y conserva
  el borrador del usuario para que no lo pierda.

**API**:
- `GET /projects/{id}/context/taxonomy-manifest/versions` (cualquier miembro, como ver el manifiesto): lista de la más
  reciente a la más antigua con `id`, `created_at`, `created_by` (nombre visible), `action`, `empty` (no había
  manifiesto), `valid`, `domains`, `material_types`. Sin el Markdown, para no cargar 5 × 256 KB.
- `GET …/versions/{version_id}` (cualquier miembro): el Markdown de esa versión, para verla antes de restaurar.
- Las versiones se buscan siempre por `(project_id, version_id)` tras comprobar el acceso al proyecto (S4): un
  `version_id` de otro proyecto da 404.
- `POST …/versions/{version_id}/restore` (editor, destino `rw`, mismo bloqueo de escritura y `If-Match` que guardar):
  - versión con texto válido: se escribe (validando con la librería, como al guardar);
  - versión «sin manifiesto»: se borra el fichero;
  - versión con texto no válido (fichero roto o cambiado fuera): 422 `manifest_version_invalid`; en la página, en vez
    de «Restaurar», «Cargar en el editor» para arreglarla.
  - Audita `project.taxonomy_manifest_restore` (sin el texto).

**Página** (bloque del manifiesto, con permiso de edición):
- Botón **«Restaurar la versión anterior»** (la más reciente) con confirmación: «Se restaura la versión del 17/11 13:05
  (antes de «Guardar» de Ana). El texto actual se conserva como versión y se puede volver a él.»
- Desplegable **«Versiones (5)»**: fecha, autor, qué cambio la sustituyó y nº de dominios; «Ver» abre el texto en
  solo lectura y «Restaurar» la recupera. Los lectores ven la lista y el texto, sin restaurar.

**Deshacer la copia de una plantilla** (lo que pidió el mantenedor):
- **Sin guardar**: botón «Deshacer» junto al aviso «Copiado de la plantilla…». Repone el borrador y el catálogo que
  había antes de copiar, sin llamar al servidor.
- **Guardada**: «Restaurar la versión anterior» (la versión creada al guardar la copia). Funciona también tras recargar
  la página.
- **Restaurar con un borrador sin guardar** en el editor pide la confirmación común (`replaceDraft`).
- **Si el contexto se construyó con el manifiesto antes del último cambio** (`ProjectContext.catalog_kind == "manifest"`
  y `built_at` anterior a la versión más reciente), la página avisa: «El contexto se construyó con el manifiesto anterior
  a este cambio: reconstruye para aplicarlo.» Si se construyó después, no avisa (B5).

### 5. «Borrar manifiesto»

- `DELETE /projects/{id}/context/taxonomy-manifest` (editor, destino `rw`, bloqueo de escritura): guarda la versión
  (acción `delete`), borra el fichero y audita `project.taxonomy_manifest_delete`. Sin manifiesto: 404
  `manifest_not_found`.
- Borra con la utilidad segura de la web (`jobs/operations/_files.py`): solo un fichero normal dentro de la carpeta del
  proyecto, sin seguir enlaces; si en su lugar hay un enlace o una carpeta, 409 `manifest_replaced` y no se borra nada.
  Exige `If-Match` como guardar.
- Guardar vacío **se sigue rechazando** (página, `min_length=1` y librería). Borrar es siempre la acción explícita.
- Página: botón «Borrar manifiesto» (rojo, secundario) con confirmación: «Se borra el manifiesto del proyecto. Se puede
  restaurar desde «Versiones».» Tras borrar, el editor queda vacío y construir con «Manifiesto del proyecto» da el error
  que ya existe («El proyecto no tiene manifiesto de taxonomía: guárdalo primero»).

### Textos (`features.json`, `context.manifest.*` y `context.build.*`)

- `context.manifest.intro`: el nuevo del punto 1.
- `context.manifest.show`: «Ver el manifiesto del proyecto»
- `context.build.useTemplateAsManifest`: «Personalizar para este proyecto»
- `context.build.useTemplateAsManifestHint`: «Copia la plantilla al manifiesto del proyecto para retocarla. La plantilla
  no cambia.»
- `context.manifest.replaceTitle` y `replaceBody`: «¿Sustituir el texto del manifiesto?» y «El texto del manifiesto se
  sustituye por el de la plantilla «{{name}}». El manifiesto guardado no cambia hasta que guardes.»
- `context.manifest.copied`: «Copiado de la plantilla «{{name}}». Revísalo y guárdalo; después, construye.»
- `context.build.unsavedManifest`: «Hay cambios sin guardar en el manifiesto: guárdalos antes de construir.»
- `context.build.help.discover`: el nuevo del punto 3.
- `context.manifest.undoCopy`: «Deshacer»
- `context.manifest.restorePrevious`, `restoreConfirm`: «Restaurar la versión anterior» y «Se restaura la versión del
  {{date}} (antes de «{{action}}» de {{user}}). El texto actual se conserva como versión.»
- `context.manifest.versions`, `versionsEmpty`, `versionAction.{save,delete,restore}`, `versionEmpty`, `versionInvalid`,
  `loadIntoEditor`, `view`, `restore`.
- `context.manifest.delete`, `deleteConfirm`: «Borrar manifiesto» y «Se borra el manifiesto del proyecto. Se puede
  restaurar desde «Versiones».»
- `context.manifest.contextStale`: «El contexto se construyó con el manifiesto anterior a este cambio: reconstruye para
  aplicarlo.»

### Tests

- **Frontend** (`context.test.tsx`):
  - el bloque solo se ve con «Manifiesto del proyecto»; al cambiar a otro catálogo desaparece, y al volver conserva el
    borrador;
  - un lector ve el bloque si el contexto se construyó con el manifiesto y, si no, el enlace «Ver el manifiesto del
    proyecto»;
  - «Personalizar para este proyecto» solo aparece con una plantilla elegida y permiso de edición;
  - al pulsarlo, cambia a «Manifiesto del proyecto», carga el Markdown sin llamar a `PUT` y muestra el aviso;
  - con un manifiesto distinto, pide confirmación, y al cancelar no cambia nada;
  - con un borrador sin guardar, «Construir» está desactivado y lo explica; tras «Guardar», se puede construir;
  - la ayuda de «Descubrir dominios» es la nueva.
- **Backend**:
  - el Markdown de cada plantilla incluida (`builtin_templates()`) se acepta como manifiesto del proyecto
    (`PUT …/taxonomy-manifest` → 200), con la librería real;
  - guardar crea una versión con el texto anterior (nulo si no había); guardar el mismo texto no crea ninguna;
  - se conservan 5: la sexta borra la más antigua;
  - `DELETE` guarda la versión y borra el fichero; sin manifiesto, 404; con un enlace en su lugar, 409;
  - restaurar una versión con texto la escribe, una «sin manifiesto» borra el fichero, una no válida da 422, y la
    restauración crea a su vez una versión (se puede deshacer);
  - permisos: lector lista y ve; editor guarda, borra y restaura; destino de solo lectura, 422; proyecto de otro
    tenant, 404 (IDOR también con un `version_id` de otro proyecto);
  - bloqueo de escritura: con un run de escritura en marcha, guardar, borrar y restaurar dan 409;
  - auditoría sin el texto del manifiesto;
  - migración `0015` con `downgrade`, y borrar el proyecto borra sus versiones;
  - `If-Match`: sin él, 428; con un `etag` viejo, 409 `manifest_changed` y no se escribe ni se guarda versión;
  - orden versión-escritura: con la escritura fallando, no queda versión; con timeout, queda;
  - «Vaciar histórico» guarda la versión del manifiesto antes de vaciar;
  - borrar con un enlace simbólico en lugar del manifiesto: 409 y el destino del enlace intacto.
- **Frontend (además)**: «Deshacer» de una copia sin guardar repone borrador y catálogo; «Restaurar la versión
  anterior» con confirmación; lista de versiones (lector sin «Restaurar»); «Borrar manifiesto» con confirmación;
  aviso de contexto construido con otro manifiesto solo si es anterior al cambio; foco en el editor tras copiar;
  «Construir» bloqueado por un borrador solo con «Manifiesto del proyecto»; selección reiniciada tras construir;
  ante 409 `manifest_changed`, recarga sin perder el borrador.
- **Tests existentes que cambian** (A5): `e2e/ai.spec.ts` y `context/ai.test.tsx` eligen «Manifiesto del proyecto»
  antes de «Pedir borrador»; los casos de `context.test.tsx` dejan de simular el `GET` del manifiesto donde ya no se
  pide.

## AUDIT_PLAN

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| F1 | Quien ya tenía un manifiesto y construye con otro catálogo no sabe que existe | Se ve al elegir «Manifiesto del proyecto», y sin tarjeta de construcción hay un enlace para verlo. El manifiesto guardado no se toca |
| F2 | Copiar la plantilla sustituye un manifiesto que el usuario estaba editando | Confirmación si hay texto distinto; nada se guarda sin «Guardar» |
| F3 | Construir con el manifiesto mientras hay cambios sin guardar usa la versión guardada, no la que se ve | «Construir» desactivado con un borrador pendiente, con el motivo a la vista |
| F4 | Una plantilla incluida no sirve como manifiesto (formato o metadatos distintos) | Test de backend con todas las incluidas, bloqueante antes de exponer el botón |
| F5 | Las plantillas personalizadas cambian después de copiarlas | Es una copia: el aviso «Copiado de la plantilla…» lo deja claro; lo mismo pasa hoy con el borrador de la IA |
| F6 | La descripción de «Descubrir dominios» vuelve a quedar mal si la librería cambia el modo descubrimiento | Comentario junto a la clave citando `DomainClassifier._best_domain`; revisar su CHANGELOG al subir el pin (ADR-006) |
| F7 | Ocultar el bloque esconde «Pedir borrador», que algunos usaban para explorar | Sigue disponible eligiendo «Manifiesto del proyecto», donde el resultado tiene efecto |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| T1 | Hacer `BuildCard` controlado (catálogo y plantilla) rompe el reinicio tras construir, que hoy hace `key={built_at}` | `ContextPage` vuelve a fijar la selección al cambiar `built_at`; `BuildCard` conserva `key` para el resto de su estado. Test de reconstrucción |
| T2 | El borrador del manifiesto sube a `ContextPage` y sobrevive a cambios de catálogo, pero no a recargar la página | Es lo esperado (borrador sin guardar); el aviso de sin guardar lo hace visible |
| T3 | `useTemplate` lanzado al renderizar pediría la plantilla sin necesidad | Se pide al pulsar (`fetchQuery`) |
| T4 | Tamaño: una plantilla grande en el editor | Mismo límite `MAX_TEMPLATE_BYTES` que el manifiesto; el editor muestra `tooLarge` como hoy |
| T5 | LSP/ISP | Sin cambios en la API pública; `BuildCard` y `ManifestCard` son internos de la página |

### Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| S1 | Un lector usa la copia para escribir el manifiesto | El botón solo aparece con permiso de edición; guardar sigue pasando por `PUT`, que exige editor y destino `rw` |
| S2 | Plantillas personalizadas de otro tenant | `GET /taxonomy-templates/{name}` ya filtra por tenant; sin cambio |
| S3 | Markdown de la plantilla con contenido malicioso en el editor | Va a un `Textarea` (texto plano) y se valida al guardar con la librería |

### Simplificaciones posibles

- **Copiar en el servidor** (`POST …/taxonomy-manifest/from-template`): guarda directamente, sin revisar antes y con
  un endpoint nuevo. No recomendada.
- **Permitir construir con el borrador sin guardar** (enviarlo en el run): ahorra un clic, pero el manifiesto usado no
  quedaría en el proyecto y cambia el contrato del run. No recomendada.
- **Sin el enlace para lectores**: más simple, pero el manifiesto dejaría de verse para quien no construye.

### Veredicto: **GO_CONDICIONAL**

Condiciones:

1. F4: el test de compatibilidad (todas las plantillas incluidas se aceptan como manifiesto) pasa antes de exponer el
   botón.
2. T1: la selección inicial sale de `initialSelection(context)` y se reinicia al reconstruir, con test.
3. F2 y F3: copiar nunca guarda; con texto distinto pide confirmación; con un borrador sin guardar no se construye.
4. Punto 3: la ayuda y la guía describen «Descubrir dominios» como hace la librería (por carpeta, sin leer el
   contenido), comprobado contra `domain_classifier.py` de la versión fijada (1.6.0).

---

## AUDIT_PLAN independiente de la revisión 2 (2026-11-17)

Contrastado con el código de la web (`develop`, `85c51b7`) y de doc_organize 1.6.0. La premisa se confirma: el
manifiesto solo se usa con `catalog=manifest` y plantilla y manifiesto comparten formato (front matter YAML →
`TaxonomyManifest`, `parse_taxonomy_template` y `save_taxonomy_manifest`). Hallazgos:

| # | Gravedad | Hallazgo | Corrección |
|---|---|---|---|
| A1 | **Alta** | El texto propuesto para «Descubrir dominios» dice que «los de la raíz del origen quedan sin clasificar». Es falso: para un documento en la raíz de la carpeta escaneada, su carpeta inmediata es esa misma carpeta (`/mnt/…/Calidad` → dominio `calidad`), así que se clasifica igual. Solo quedan sin clasificar los que no están bien convertidos (`incomplete_artifacts`) o cuya carpeta no tiene letras ni números (`_slugify` vacío) | Texto: «Un dominio por cada carpeta: cada documento va al de la carpeta que lo contiene (los de la raíz, al de la carpeta escaneada). No lee el contenido.» Igual en la guía |
| A2 | Media | La tabla de la guía simplifica la asignación con manifiesto: cada dominio y tipo de material puede llevar **palabras clave** (`keywords`, sumadas a las del slug), y el tipo de material se puntúa aparte | Fila «Asignación»: «Palabras del dominio y sus palabras clave en el título y el contenido (más la carpeta), con umbral; el tipo de material, igual por separado» |
| A3 | **Alta** | «Construir desactivado con un borrador sin guardar» no dice que solo aplica con «Manifiesto del proyecto». Como está, pedir un borrador y cambiar a «Plantilla» bloquearía construir con la plantilla | Desactivar solo si `selection.catalog === 'manifest'` y hay borrador distinto del guardado; test con los dos casos |
| A4 | Media | Reiniciar la selección «al cambiar `built_at`» con un `useEffect` choca con la regla `react-hooks/set-state-in-effect` del proyecto, y no dice qué pasa si el usuario cambia el catálogo mientras una construcción está en marcha | Estado derivado sin efecto: guardar `{ builtAt, catalog, template }` y, si `builtAt` no coincide con el del contexto, usar `initialSelection(context)` (el patrón del menú plegable en `Layout`). Así, al terminar una construcción, la selección pasa a la del contexto nuevo |
| A5 | **Alta** | Tests que dan por hecho que el bloque se ve siempre: el e2e `ai.spec.ts` construye con «Descubrir dominios» y después pulsa «Pedir borrador» sin cambiar de catálogo; `context/ai.test.tsx` también; y los 8 casos de `context.test.tsx` simulan el `GET` del manifiesto | Actualizarlos en el mismo PR: elegir «Manifiesto del proyecto» antes de pedir el borrador; quitar el `GET` del manifiesto donde ya no se pida |
| A6 | Media | La copia de la plantilla y el borrador de la IA comparten el mismo borrador, pero la confirmación (F2) solo cubre la copia: «Pedir borrador» con una copia sin guardar la sustituye sin avisar (hoy pasa con dos borradores de la IA) | Misma confirmación para los dos caminos, en una sola función `replaceDraft(text, source)` |
| A7 | Media | Accesibilidad: al pulsar «Personalizar para este proyecto» el catálogo pasa a «Manifiesto del proyecto», así que el selector de plantilla y el propio botón desaparecen y el foco se pierde (vuelve a `body`) | Llevar el foco al editor del manifiesto (o a su título) tras copiar; el aviso «Copiado de…» con `role="status"`. Test que comprueba el foco |
| A8 | Baja | Procedencia: al construir con un manifiesto copiado de una plantilla, el contexto ya no guarda `taxonomy_template_name`; el resumen dirá «Manifiesto del proyecto» sin decir de qué plantilla salió | Aceptable (es una copia que se edita). Mencionarlo en la guía |
| A9 | Baja | Con «Descubrir dominios», «Clasificar con IA» solo recibe los sin clasificar, que en este modo son casi siempre documentos sin convertir: la IA tendría poco o ningún efecto. No está verificado con una construcción real | Fuera de alcance: anotarlo para comprobarlo y, si se confirma, explicarlo en la ayuda o desactivar la casilla en ese catálogo (otro cambio) |
| A10 | Baja | El enlace «Ver el manifiesto del proyecto» para lectores lee de la ubicación de destino: si no responde, error | `ErrorAlert` como hoy en el bloque; sin cambio de backend |

### Veredicto: **GO_CONDICIONAL**

Condiciones nuevas, que se suman a las 4 del plan:

5. A1 y A2: textos de la ayuda y de la guía corregidos como en la tabla.
6. A3: el bloqueo de «Construir» solo con «Manifiesto del proyecto», con test.
7. A4: la selección reiniciada sin `useEffect` (estado derivado de `built_at`).
8. A5: e2e y tests unitarios afectados actualizados en el mismo PR.
9. A6 y A7: confirmación común para copia y borrador; foco al editor tras copiar.

---

## AUDIT_PLAN de la revisión 3 (2026-11-17)

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | Restaurar o borrar el manifiesto no cambia el contexto ya construido, y el usuario puede creer que sí | Aviso «reconstruye para aplicarlo» al restaurar o borrar si existe un contexto construido con catálogo `manifest` |
| R2 | Solo 5 versiones: tras 5 cambios se pierde la anterior a ellos | Documentado en la guía y en el texto del desplegable («las 5 últimas»); el número es una constante de configuración |
| R3 | Un manifiesto editado fuera de la app entre dos guardados no tiene versión propia | Se captura al siguiente guardado, borrado o restauración (siempre se guarda lo que hay en el disco) |
| R4 | Restaurar una versión que ya no es válida (cambió la librería, o venía rota) | 422 `manifest_version_invalid` y «Cargar en el editor» para arreglarla |
| R5 | Borrar sin querer | Confirmación y versión guardada: se recupera con «Restaurar» |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| T6 | Versión y fichero desincronizados si falla la escritura después de guardar la versión | Orden: validar → escribir el fichero → guardar la versión y el recorte a 5 en la transacción; si falla la escritura, no se confirma la transacción. Si falla el `commit` tras escribir, queda el fichero nuevo sin versión (se informa en el log); se documenta |
| T7 | Dos editores a la vez | Mismo bloqueo de escritura del proyecto que hoy; las versiones quedan en orden por `created_at` |
| T8 | Tamaño en `config.db` | Como mucho 5 × 256 KB por proyecto; la lista no devuelve el texto |
| T9 | Borrar el fichero desde la web, cuando hoy lo escribe la librería | Misma resolución segura que el resto de salidas (`resolve_within`, sin seguir enlaces, solo ficheros normales); si se prefiere, pedir `delete_taxonomy_manifest` a doc_organize (hueco nuevo) sin bloquear |
| T10 | Copias de seguridad | La tabla está en `config.db`, que ya copia `app.cli backup`; `restore` la recupera con el resto |

### Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| S4 | IDOR: restaurar o ver una versión de otro proyecto con su `version_id` | La versión se busca siempre por `(project_id, version_id)` tras comprobar el acceso al proyecto; test |
| S5 | La auditoría filtra el contenido del manifiesto | Solo `action`, `version_id` y recuentos de dominios; nunca el texto |
| S6 | El texto de una versión se muestra en la página | En un `Textarea`/`Code` de solo lectura, como el manifiesto; nunca como HTML |

### Simplificaciones posibles

- **Una sola versión** (solo «Restaurar la versión anterior», sin lista): menos interfaz, pero tras dos guardados no se
  puede volver a la de antes de copiar. El mantenedor eligió 5.
- **Sin «Ver»**: restaurar sin ver el texto; menos seguro. No recomendada.

### Veredicto: **GO_CONDICIONAL**

Condiciones nuevas, que se suman a las 9 anteriores:

10. Guardar, borrar y restaurar guardan siempre lo que había antes, y se conservan 5 versiones por proyecto, con tests.
11. S4: versiones buscadas por proyecto y versión, con test de IDOR.
12. T6: el fichero y la versión no quedan desincronizados ante un fallo de escritura (test con la escritura fallando).
13. Guardar vacío sigue rechazado; borrar es solo con «Borrar manifiesto» y confirmación.

---

## AUDIT_PLAN independiente de la revisión 3 (2026-11-17)

Contrastado con `domain/context/service.py` (`save_manifest`, `_check_writable`), `jobs/operations/history_clear.py`,
`db/models.py` y doc_organize 1.6.0 (`ProjectHistoryCleaner`). Hallazgos:

| # | Gravedad | Hallazgo | Corrección |
|---|---|---|---|
| B1 | **Alta** | El plan dice que siempre queda versión de lo que había, pero **«Vaciar histórico»** (`history_clear` → `ProjectHistoryCleaner.clear`) borra todo el contenido de la carpeta del proyecto, `taxonomy_manifest.md` incluido, sin pasar por la API del manifiesto. El manifiesto se perdería sin versión | El job `history_clear` guarda una versión (acción `history_clear`) con el manifiesto que haya antes de vaciar, y su vista previa lo nombra («el manifiesto de taxonomía; se podrá restaurar desde Versiones»). Test |
| B2 | **Alta** | Dos peticiones a la vez (dos editores, o doble clic) sobre el manifiesto no se excluyen: `_check_writable` solo mira runs en marcha. «Leer lo actual → escribir → guardar la versión» puede registrar como «anterior» un texto equivocado o perder el cambio de otro. El problema ya existe hoy con `PUT`, pero las versiones lo hacen visible | Concurrencia optimista: `GET` del manifiesto devuelve un `etag` (hash del contenido, o «sin manifiesto»); `PUT`, `DELETE` y `restore` lo exigen en `If-Match`, y si el fichero cambió, 409 `manifest_changed` («Otro usuario lo cambió: recarga»). Además, un cerrojo por proyecto en el proceso alrededor de la sección crítica. Tests de los dos casos |
| B3 | **Alta** | El orden de la T6 («escribir el fichero y luego confirmar la versión; si falla la escritura, no se confirma») no aguanta un **timeout**: `run_with_timeout` deja el hilo escribiendo en una ubicación lenta, la transacción se deshace y el fichero cambia después **sin versión** | Orden inverso: guardar y confirmar la versión **antes** de escribir. Si la escritura falla con un error definitivo, se borra esa versión; si es un timeout, se conserva (es lo que había antes y restaurarla es inocuo). Test con escritura fallida y con timeout |
| B4 | Media | El plan dice que la web borrará el fichero «como ya hace con los ficheros del contexto». No es así: borrar el contexto lo hace la librería (`ContextRegistry.delete_context`); la web solo borra exportaciones y usa `jobs/operations/_files.py` en sus jobs | Corregir el texto. Borrar con la utilidad segura que ya existe (sin seguir enlaces, solo un fichero normal dentro de la carpeta del proyecto) y su test con un enlace simbólico en lugar del manifiesto |
| B5 | Media | El aviso «reconstruye para aplicarlo» (R1) se mostraría con cualquier contexto construido con el manifiesto, también si se construyó **después** del cambio | Avisar solo si `ProjectContext.catalog_kind == "manifest"` y `built_at` es anterior a la última versión |
| B6 | Media | Restaurar con un borrador sin guardar en el editor lo sustituye sin avisar | La misma confirmación común de A6 (`replaceDraft`) para copiar, pedir borrador y restaurar |
| B7 | Baja | Los proyectos se borran de forma lógica (`deleted_at`), así que `ON DELETE CASCADE` solo actúa si alguna vez se purgan: las versiones de un proyecto borrado se quedan en `config.db` | Aceptable (como el resto de tablas del proyecto); documentarlo. Si hay purga de proyectos, que incluya la tabla |
| B8 | Baja | Restaurar `config.db` desde una copia de seguridad trae versiones que pueden no corresponder al manifiesto actual del destino | Aceptable: cada versión guarda su texto completo y no depende del fichero actual. Mencionarlo en la guía de copias |
| B9 | Baja | Las restauraciones también cuentan entre las 5: ir y volver entre dos versiones llena la lista enseguida | Aceptable; la lista indica la acción de cada versión |

### Veredicto: **GO_CONDICIONAL**

Condiciones nuevas, que se suman a las 13 anteriores:

14. B1: «Vaciar histórico» guarda versión del manifiesto antes de vaciar y su vista previa lo dice.
15. B2: concurrencia optimista con `etag`/`If-Match` (409 `manifest_changed`) en guardar, borrar y restaurar, con tests.
16. B3: la versión se confirma antes de escribir; se retira solo si la escritura falla de forma definitiva, con tests de
    fallo y de timeout.
17. B4: borrar con la utilidad segura de la web, sin seguir enlaces, con test.

---

# Parte 2 — Facetas de la taxonomía (doc_organize 1.7.0)

> **Adaptada a doc_organize 2.0.0 (revisión 6)**: lee esta parte con los cambios de nombres y alcance de la cabecera
> (facetas → ejes, `ai_facets` → `ai_scope`, tabla genérica `context_document_axis_values`). Manda el plan único.

## Origen

La plantilla `taxonomia-multi-dimensional-normas-gobernanza-2` (proyecto CALIDAD_VD) declara los ejes
`normative_frameworks`, `management_system` y `evidence`, que doc_organize 1.6.0 ignora sin avisar. doc_organize 1.7.0
(plan de la librería) los convierte en **facetas**: etiquetas de cada documento, de uno o varios valores, además de
dominio y tipo de material. Decisiones de la librería que condicionan la web:
- formato implícito aceptado: la plantilla actual funciona sin tocarla;
- IA para facetas en dos sitios: en la Sub-fase B (documentos sin dominio) y en una fase propia para los ya
  clasificados (`ai_facets_enabled`, con su presupuesto);
- Excel de documentos del contexto: `write_context_documents_xlsx`;
- `inspect_taxonomy_front_matter(text)` → facetas que se leerán, `implicit_facets` e `ignored_keys`;
- el historial no registra cambios de faceta en 1.7.0.

## Inputs

| Campo | Valor |
|---|---|
| Objetivo | (6) Guardar las facetas de cada documento del contexto. (7) Filtrar los documentos por faceta y ver los recuentos. (8) Casilla «Completar las facetas con IA» al construir. (9) Exportar a Excel los documentos del contexto. (10) Avisar, al guardar una plantilla o el manifiesto, de las claves que no se usarán y de las facetas implícitas |
| Rutas | Backend: `pyproject.toml`/`uv.lock` (pin 1.7.0); `alembic/versions/0016_context_facets.py` (nuevo); `db/models.py` (`ContextDocumentFacet`, `ProjectContext.taxonomy_facets`, estadísticas `ai_facets_*`); `integrations/doc_organize/context.py` (`ContextDoc.facets`, `ContextRequest.ai_facets`, `inspect_front_matter`), `integrations/doc_organize/export.py` (`context_documents`); `domain/runs/operations.py` (`ContextBuildParams.ai_facets`, `ExportParams.kind`); `jobs/operations/context.py` (filas de facetas, estadísticas); `jobs/operations/export.py`; `domain/context/service.py` (filtro `facet`, recuentos); `domain/context/templates.py` (informe de claves); `api/v1/{context,templates,runs,schemas}.py`. Frontend: `features/context/{ContextPage,useContext}.tsx`, `features/admin/TaxonomyTemplatesPage.tsx`, `features/documents/ExportPanel.tsx`, `features/runs/*` (etapa `context_facets`), `i18n/es/features.json`, tests y e2e. Docs: `docs/guides/{contexto,ia,documentos}.md`, `CHANGELOG.md` |
| Contrato HTTP | Ver «Contrato» abajo: campos nuevos en contexto, documentos, plantillas, manifiesto, runs y exportación; parámetro `facet` repetible |
| Pantallas | Página del contexto (filtros por faceta, facetas en cada documento, casilla de IA, recuentos del run), editor de plantillas y bloque del manifiesto (avisos), panel de exportación |
| Permisos | Los de hoy: ver y filtrar, cualquier miembro; construir con IA, editor con destino `rw` y la familia `litellm_taxonomy_classification` configurada; exportar, cualquier miembro; plantillas, `templates.manage` |
| doc_organize | 1.7.0: `DomainDocument.facets`, `UnclassifiedDocument.facets`, `Context.taxonomy_facets`, `Context.ai_facets_*`, `ContextBuilder.build(ai_facets_enabled=, ai_facets_client=)`, `write_context_documents_xlsx`, `inspect_taxonomy_front_matter`. Firmas a verificar en el tag antes de implementar |
| Restricciones | Migración `0016` aditiva; sin dependencias nuevas; la web no se publica con facetas hasta que exista el wheel 1.7.0 |

## PLAN

### 6. Guardar las facetas

- **Tabla nueva `context_document_facets`** (migración `0016`), en vez de una columna JSON: el filtro y los recuentos
  necesitan índice con 100 000 documentos.

  | Columna | Tipo | Notas |
  |---|---|---|
  | `project_id`, `seq` | FK compuesta a `context_documents` (`ON DELETE CASCADE`) | El documento |
  | `facet` | texto (≤ 41) | Clave de la faceta (`normative_frameworks`) |
  | `slug`, `name` | texto | Valor |
  | `confidence` | real | 0-1 |
  | `classified_by` | `rules` · `ai` | |

  Índices `(project_id, facet, slug)` y `(project_id, seq)`.
- **`ProjectContext.taxonomy_facets`** (JSON): las facetas del contexto (clave, nombre, si admite varios valores y sus
  valores con nombre), para pintar los filtros sin leer `context.json`.
- **El job `context_build`** sustituye las facetas a la vez que la proyección de documentos (misma transacción y mismos
  lotes de `executemany`); también las de los sin clasificar por umbral.
- **Contextos anteriores** (sin facetas): tabla vacía para ellos; la página no muestra filtros de faceta.

### 7. Filtrar por faceta

- `GET /projects/{id}/context/documents?facet=normative_frameworks:iso-27001&facet=…`:
  - valores de la **misma faceta** se combinan con O (ISO 27001 o ENS);
  - **facetas distintas**, con Y (ISO 27001 y «Sistema de gestión: SGSI»);
  - se combina con `domain`, `language`, `keyword`, `only` y `q` como hoy.
  - Implementación: `EXISTS` sobre `context_document_facets` con el índice; como mucho 20 valores; clave o valor que no
    existen, lista vacía (no error).
- `ContextDocumentOut.facets: dict[str, list[FacetValueOut]]`.
- `ContextOut.taxonomy_facets`: cada faceta con sus valores y **cuántos documentos** tiene cada uno (una consulta
  agrupada).
- **Página**: debajo de los filtros actuales, un `MultiSelect` por faceta («Marcos normativos», con el recuento de cada
  valor); en cada documento, sus valores como `Badge` (los de la IA con la marca «IA», como el resto de campos). Los
  filtros viven en la URL, como el resto del listado.

### 8. Casilla «Completar las facetas con IA»

- `ContextBuildParams.ai_facets: bool = False`. Solo con catálogo `template` o `manifest` y si la plantilla o el
  manifiesto tienen facetas; si no, 422 al encolar («este catálogo no tiene facetas»).
- Exige la familia `litellm_taxonomy_classification` configurada (`require_configured`), como `ai_classification`.
- El job pasa `ai_facets_enabled=True` y el cliente de taxonomía; mismo `ai_max_documents` y `ai_max_failures` que el
  resto de fases, con recuento propio.
- **Resultado del run**: `ai_facets` (`calls`, `applied`, `failed`, `stopped`), como `ai_enrichment`; etapa de progreso
  `context_facets` en la página del run.
- **Página**: casilla en la tarjeta de construcción, junto a «Clasificar con IA», visible con plantilla o manifiesto con
  facetas, con el mismo aviso «El contenido sale de la aplicación» y el presupuesto.
- Auditoría: `run.enqueue` ya guarda los parámetros (incluido `ai_facets`).

### 9. Excel de los documentos del contexto

- `ExportParams.kind` gana `context_documents`. El job carga el contexto del proyecto (`ContextRegistry`) y llama a
  `write_context_documents_xlsx` (hojas «Documentos» y «Facetas»), con progreso y cancelación como las demás
  exportaciones.
- Sin contexto construido: 409 al encolar («construye antes el contexto»).
- Rutas de la hoja: relativas a las carpetas de origen (nunca las del contenedor), como en el Excel de la caché.
- **Panel de exportación**: botón «Excel del contexto» (cualquier miembro).

### 10. Aviso de claves ignoradas

- `inspect_front_matter(markdown)` en la integración; `validate_markdown` devuelve además `facets`, `implicit_facets` e
  `ignored_keys`.
- `TaxonomyTemplateDetail` y `TaxonomyManifestOut` ganan `facets` (clave, nombre, nº de valores), `implicit_facets` e
  `ignored_keys`; el `PUT` de plantillas y del manifiesto los devuelve.
- **Página** (editor de plantillas y bloque del manifiesto):
  - `ignored_keys` no vacío: `Alert` naranja «Estas claves no se usan al clasificar: `references`, `notes`…».
  - `implicit_facets`: aviso gris «Se leen como facetas: `normative_frameworks`, `management_system`, `evidence`.
    Puedes darles nombre en `facets:`».
  - El resumen del catálogo dice también las facetas («8 dominios, 10 tipos de material, 3 facetas»).
- Una plantilla guardada antes sigue siendo válida: el aviso es informativo, no bloquea.

## Contrato (resumen)

| Endpoint | Cambio |
|---|---|
| `GET /projects/{id}/context` | `taxonomy_facets[]` con valores y recuentos; `ai_facets` (estadísticas) |
| `GET /projects/{id}/context/documents` | `facet` repetible (`clave:slug`); `facets` en cada documento |
| `POST /projects/{id}/runs` (`context_build`) | `ai_facets: bool` |
| `POST /projects/{id}/runs` (`export_xlsx`) | `kind: "context_documents"` |
| `GET`/`PUT /taxonomy-templates/{name}`, `GET`/`PUT …/context/taxonomy-manifest` | `facets`, `implicit_facets`, `ignored_keys` |

Todo aditivo para los clientes; OpenAPI y `schema.d.ts` regenerados.

## Tests

- **Backend**:
  - migración `0016` con `downgrade`;
  - el job guarda las facetas de clasificados y sin clasificar y las sustituye al reconstruir;
  - filtro `facet`: O en la misma faceta, Y entre facetas, combinado con `domain` y `q`; clave inexistente da lista
    vacía; más de 20 valores, 422;
  - recuentos por valor; contexto anterior sin facetas;
  - `ai_facets`: 422 sin facetas o con un catálogo de un eje, 422 sin la familia configurada, estadísticas en el
    resultado;
  - exportación `context_documents`: hojas y columnas por faceta, rutas relativas, 409 sin contexto;
  - plantilla real de CALIDAD_VD: `implicit_facets` con las tres claves, `ignored_keys` vacío; una plantilla con
    `notes: …` lo da en `ignored_keys`;
  - IDOR y permisos como en el resto del contexto.
- **Frontend**:
  - filtros por faceta con recuentos y en la URL;
  - insignias de faceta por documento, con la marca «IA»;
  - casilla de IA visible solo con facetas y con su aviso;
  - botón «Excel del contexto»;
  - avisos de claves ignoradas y facetas implícitas en el editor de plantillas y en el bloque del manifiesto.
- **e2e**: construir con la plantilla de CALIDAD_VD (o una de prueba con facetas), filtrar por un marco normativo y
  exportar el Excel.

## AUDIT_PLAN de la parte 2

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| P1 | Facetas con palabras clave genéricas etiquetan de más, y los filtros devuelven casi todo | Recuentos visibles en cada filtro y hoja «Facetas» del Excel para detectarlo; la guía explica cómo escribir palabras clave de faceta |
| P2 | El usuario espera que las facetas reorganicen las carpetas o aparezcan en el historial | Documentado: solo etiquetan; el historial no las registra en 1.7.0 |
| P3 | Contextos construidos con 1.6.0 no tienen facetas | Sin filtros de faceta y aviso «reconstruye para ver las facetas» si el catálogo actual las tiene |
| P4 | La casilla de IA con un catálogo sin facetas confunde | Solo visible con plantilla o manifiesto que tenga facetas; 422 en el servidor si llega igual |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| P5 | Volumen: 100 000 documentos × 3 facetas × hasta 5 valores = hasta 1,5 M filas por proyecto | Tabla con índices; inserción por lotes en la misma transacción que la proyección; medir con 100 000 documentos (objetivo: la escritura de la proyección no pasa del doble de hoy) |
| P6 | Filtro con `EXISTS` y varias facetas, lento | Índice `(project_id, facet, slug)`; como mucho 20 valores; medir junto al listado de documentos (objetivo: ≤ 150 ms por página, como G43) |
| P7 | La web adopta firmas de 1.7.0 que aún no existen | Verificar las firmas en el tag antes de implementar (como en cada subida de la librería); la parte 2 no empieza hasta el wheel |
| P8 | Migraciones `0015` (parte 1) y `0016` (parte 2) en ramas distintas | Orden fijo: parte 1 primero; si la parte 2 se adelanta, renumerar antes de fusionar |
| P9 | El Excel se genera en el worker con todo el contexto en memoria | El `Context` ya se carga entero en la construcción; `openpyxl` en modo de escritura en flujo; medir con 2600 documentos |

### Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| P10 | Inyección en el filtro (`facet=…`) | Formato `clave:slug` validado con patrón (`^[a-z][a-z0-9_]{0,40}:[a-z0-9-]{1,128}$`); consultas parametrizadas |
| P11 | Nombres de faceta o valor con HTML en la página | React escapa el texto; nunca `dangerouslySetInnerHTML` |
| P12 | Privacidad de la fase de IA (más contenido sale) | Opt-in con aviso, presupuesto, `run.enqueue` auditado; desactivada por defecto |
| P13 | Fórmulas en el Excel | La librería aplica `_excel_safe`; test en la web con un título que empieza por `=` |

### Simplificaciones posibles

- **Columna JSON en vez de tabla**: menos migración, pero el filtro y los recuentos serían lentos con 100 000 documentos.
  No recomendada.
- **Sin recuentos en los filtros**: menos consultas, pero no se ve si una faceta etiqueta de más (P1).
- **Avisos solo en el editor de plantillas**: menos cambios, pero el manifiesto también puede tener claves ignoradas.

### Veredicto: **GO_CONDICIONAL**

Condiciones de la parte 2:

1. doc_organize 1.7.0 publicada y firmas verificadas en el tag antes de empezar (P7).
2. P5 y P6: medidas con 100 000 documentos dentro de los objetivos; si no, índices o recuentos en caché antes de cerrar.
3. P8: la migración de la parte 2 va después de la `0015` de la parte 1.
4. P10: filtro validado con patrón y tests de valores no válidos.
5. La plantilla real de CALIDAD_VD produce `implicit_facets` con sus tres claves y facetas en los documentos (test de
   aceptación con un corpus pequeño).
