# PLAN + AUDIT_PLAN — Menú de Administración, medición en red y doc_organize 1.6.0 (2026-11-16)

Tres bloques: medir la construcción del contexto en un recurso de red real (pendiente de la adopción de 1.5.0),
reorganizar el menú de Administración y adoptar doc_organize 1.6.0 (G42, G43, historial girado). Solo PLAN y
AUDIT_PLAN. El plan de la librería está en `doc_organize/.ai/sessions/2026-11-16-doc-organize-1.6.0/PLAN.md`.

## Inputs

| Campo | Valor |
|---|---|
| Objetivo | Saber cuánto cuesta construir el contexto sobre SMB/NFS; menú de Administración agrupado (IA y Información aparte); usar las APIs de 1.6.0 |
| Módulos | `frontend/src/app/Layout.tsx`, `app/router.tsx`, `features/admin/*`, `i18n/es/*.json`; `backend/app/domain/settings/service.py`, `api/v1/admin.py`, `api/v1/schemas.py`, `integrations/doc_organize/{cache,context}.py`, `domain/context/service.py`; `backend/scripts/` |
| API pública | `SettingOut` gana `group`; `GET /documents` gana `mime_type` y nuevos `order_by`; `ContextDocumentOut` rellena metadatos de los sin clasificar; endpoint nuevo `GET /documents/mime-types` |
| Contrato de entrada | doc_organize 1.5.0 (W0, W1) y 1.6.0 (W2) |
| Contrato de salida | Mismas guardas de acceso que hoy; URLs antiguas siguen funcionando (redirección) |
| Reglas de negocio | `owner_name` solo para quien ya lo puede ver; los ajustes de IA siguen auditándose igual |
| Restricciones técnicas | Sin dependencias nuevas en frontend ni backend; Mantine `NavLink` anidado (el patrón ya usado en Proyectos) |
| Formatos | OpenAPI (`openapi/`, `frontend/src/api/schema.d.ts`) |
| Archivos existentes | Sí |

---

## PLAN

### Fase W0 — Medir la construcción del contexto en red

**Por qué primero**: su resultado decide si la librería necesita lectura concurrente de propiedades antes de extender
esa lectura a los sin clasificar (G42, fase L5 de la librería).

**Cambio**: `backend/scripts/bench_context_network.py` (hecho el 2026-11-16; no se empaqueta ni se ejecuta en CI).

- Mide solo lo que añadió la 1.5.0: `read_document_properties` sobre los originales. Lo demás (leer `.json`, idioma)
  ya existía antes de 1.5.0 y no depende de dónde estén los originales. **Solo lee del origen**: no escanea ni convierte.
- Pasadas sobre muestras aleatorias disjuntas (primera lectura desde el equipo): secuencial (como la librería hoy), con
  K hilos (¿compensa G44?), repetida tras una pausa (caché SMB caliente) y sobre una copia local (referencia).
- Salida: Markdown + JSON (`--report`) con p50/p95/máx por pasada y extensión, estimación para toda la carpeta y la
  decisión según el umbral. Sale con 2 si se supera el umbral.
- Resultado en `docs/plan/MEDICION_CONTEXTO_RED.md`.

**Recurso disponible** (2026-11-16): solo `\\NAS_CASA\tmp\VD\_documentación\Calidad\Calidad - General` (SMB, cliente
Windows 11; 3096 ficheros, 2613 PDF/Office, 4,2 GB). No hay NFS ni un worker Linux en Docker contra ese recurso: la
medición vale para SMB desde Windows; NFS y el cliente CIFS de Linux quedan **sin medir** y se documenta así.

Prueba de humo (5 ficheros por pasada, solo para validar el script, sin valor estadístico): p50 secuencial en red
74 ms/doc contra 8 ms en local; con 4 hilos, 43 ms/doc efectivos. Apunta a superar el umbral, pero hay que confirmarlo
con la ejecución completa.

**Preparación del entorno de W0** (entorno ideal; lo disponible está arriba en «Recurso disponible»)

| Pieza | Requisito |
|---|---|
| Servidor de ficheros | Una máquina distinta del host del worker que exporte un recurso SMB (Windows Server o Samba, SMB 3.x) y otro NFS (v4.1; v3 si es lo que se usa en producción). Pueden ser el mismo servidor |
| Host cliente | Linux con Docker y la imagen del worker de la web 1.5.0 (doc_organize 1.5.0), en la misma red que tendría producción (no en el propio servidor de ficheros). `sudo` para vaciar la caché de páginas (`drop_caches`) y remontar |
| Montajes | Los dos recursos montados en el host con **las mismas opciones que en producción** (`cifs`: `vers`, `cache`, `actimeo`; `nfs`: `vers`, `rsize/wsize`, `actimeo`) y visibles en el contenedor como en el despliegue |
| Corpus | 500–2000 documentos mezclados (PDF, DOCX, XLSX, PPTX), con tamaños reales y propiedades rellenas en parte. Sin datos sensibles. La misma copia en cada recurso y en disco local para la referencia |
| Artefactos | El corpus ya escaneado y convertido (`.md`/`.json`) por la web en cada ubicación: el escaneo se lanza desde la web y la medición empieza después |
| Escritura | Una carpeta de destino de usar y tirar en cada recurso, con escritura para el usuario del worker (contexto e historial se escriben allí) |
| Datos de red | RTT (`ping` al servidor) y ancho de banda (`iperf3` si está disponible) |
| Opcional | `tc netem` en el host para simular más latencia (oficina remota) |

Datos que hay que pasar para lanzar el script: las rutas de montaje dentro del contenedor, las líneas de `/proc/mounts`
de los dos montajes, el número de documentos del corpus y la forma de ejecutar comandos en el host (acceso directo o
que el mantenedor ejecute el script y entregue el JSON).

**Umbral de decisión** (propuesto): si (a) pasa de 20 ms/doc en p95 o el build en red es > 3× el local, se pide a la
librería lectura concurrente acotada de propiedades (nuevo hueco G44) antes de cerrar L5.

### Fase W1 — Reorganizar el menú de Administración

**Hoy**: lista plana de nueve entradas bajo «Administración»
([Layout.tsx:17-27](../../../frontend/src/app/Layout.tsx)); «Ajustes» mezcla en una página la tabla de ajustes (sesión,
inicio de sesión, ubicaciones, retención, cuota **y los cinco `ai_*`**), la ficha de capacidades de la instancia y los
workers ([SettingsPage.tsx:385-434](../../../frontend/src/features/admin/SettingsPage.tsx)).

**Propuesta de menú** (grupos con `NavLink` anidado; un grupo sin hijos visibles no se muestra):

```
Administración
├─ Acceso
│  ├─ Usuarios            /admin/users              users.manage
│  ├─ Roles               /admin/roles              roles.manage
│  ├─ Sesiones            /admin/sessions           users.manage
│  └─ Tenants             /admin/tenants            instancia
├─ Plantillas de taxonomía  /admin/taxonomy-templates  templates.manage
├─ IA                                                 instancia
│  ├─ Configuración       /admin/ai/settings   (proveedores, modelos, claves: la página actual)
│  ├─ Parámetros          /admin/ai/parameters (ai_timeout_seconds, ai_retries, ai_max_documents_per_run,
│  │                                            ai_draft_timeout_seconds, ai_draft_retries)
│  └─ Uso                 /admin/ai/usage      (la página actual)
├─ Ajustes               /admin/settings            instancia  (sin los ai_*, agrupados por sección)
├─ Información           /admin/info                instancia  (Capacidades de la instancia + Workers)
└─ Auditoría             /admin/audit               audit.read
```

**Mejoras propuestas para el resto** (incluidas en W1 salvo las marcadas como opcionales):

1. **Ajustes por secciones**: la tabla se parte en «Sesión e inicio de sesión», «Ubicaciones» y «Retención y cuotas»,
   cada una con su título. Para no codificar prefijos en el frontend, `SettingOut` gana
   `group: Literal["security", "locations", "storage", "ai"]` desde el backend (un mapa junto a `ADMIN_KEYS`).
2. **Parámetros de IA con la misma tabla** (`SettingRow` reutilizado, filtrado por `group == "ai"`), usando el mismo
   `PATCH /admin/settings`: misma validación, misma auditoría, sin endpoint nuevo.
3. **Información de solo lectura**: Capacidades + Workers + versión de la web y de la librería (ya llegan en cada worker
   y en `/health`). Aviso visible si no hay ningún worker vivo o ninguno GPU cuando se espera.
4. **Enlaces entre páginas**: «Uso» enlaza a «Configuración» (ya lo hace, cambia la URL) y a «Parámetros» cuando se paró
   por `ai_max_documents_per_run`.
5. **Grupo abierto según la ruta**: el grupo que contiene la página actual se abre solo (como «Proyectos»).
6. **Redirecciones**: `/admin/ai-settings` → `/admin/ai/settings`, `/admin/ai-usage` → `/admin/ai/usage`
   (`<Navigate replace>`), para marcadores y enlaces de la documentación.
7. *(Opcional)* Migas de pan en las páginas de grupo («Administración › IA › Uso»).
8. *(Opcional)* Mover «Sesiones» a la ficha de cada usuario además del listado global.

**Cambios**

- Backend: `domain/settings/service.py` (mapa `SETTING_GROUPS`, `SettingView.group`), `api/v1/schemas.py`
  (`SettingOut.group`), `api/v1/admin.py`; regenerar `openapi/` y `schema.d.ts`.
- Frontend: `Layout.tsx` (estructura de grupos con guardas por hijo), `router.tsx` (rutas nuevas bajo `admin/ai`,
  `admin/info`, redirecciones), `SettingsPage.tsx` (secciones, sin capacidades ni workers), `InfoPage.tsx` nuevo
  (mueve `CapabilitiesCard` y `WorkersCard`), `AiParametersPage.tsx` nuevo, `AiUsagePage.tsx` (enlaces),
  `i18n/es/*.json` (claves `nav.*` nuevas).
- Tests: `admin.test.tsx`, `ai.test.tsx`, `locations.test.tsx:282,364` (hoy buscan capacidades en `/admin/settings`),
  test de navegación por permisos (grupo oculto sin hijos), redirecciones, e2e del menú; backend: `group` presente y
  estable para cada clave de `ADMIN_KEYS` (test que falle si se añade una clave sin grupo).
- Docs: guía de administración (capturas y rutas), `CHANGELOG.md`.

**Entrega**: independiente de la librería; puede salir como web 1.5.x/1.6.0 antes que W2.

> **Estado (2026-11-16)**: implementada sin commit. Menú por grupos (`app/adminMenu.ts`, botón accesible con
> `aria-expanded`), `SettingsTable` reutilizada en «Ajustes» (por secciones) e «IA › Parámetros», `InfoPage`
> (versiones, capacidades, workers y aviso si ningún worker late), redirecciones de las URLs antiguas y
> `SettingOut.group` (`SETTING_GROUPS`, test que falla con una clave sin sección). Condición 3 cumplida: redirecciones
> y grupos ocultos por permisos con test. La mejora 4 queda como enlace fijo de «Uso» a «Parámetros» (la página de uso
> no sabe si una ejecución paró por el tope). Opcionales 7 y 8 sin hacer. e2e actualizados, sin ejecutar.

### Fase W2 — Adoptar doc_organize 1.6.0

Tras publicar la librería.

- **Pin** 1.6.0 (`pyproject.toml`, `[tool.uv.sources]`, `uv.lock`), tests que fijan la versión.
- **`created_at` conservado** (L1): la fecha «creado» del contexto deja de moverse en cada reconstrucción; nota en el
  CHANGELOG.
- **Historial girado** (L3): `context_paths` (vista previa del borrado) lista también `CONTEXT_HISTORY.N.jsonl` vía
  `ProjectLayout.context_history_files()`; la página del historial y el Excel no cambian (la librería lee todo).
- **G42**: `integrations/doc_organize/context.py:505-517` construye los `ContextDoc` sin clasificar desde
  `context.unclassified_details` (autor, descripción, palabras clave, idioma, motivo) con respaldo a
  `unclassified_documents` para contextos anteriores; columna «Motivo» en la página del Contexto; quitar la nota de
  `contexto.md`. **Tamaño de la respuesta** (auditoría de la librería, 2026-11-16): `Context` serializado incluye ahora
  `unclassified_details`, con miles de entradas en proyectos grandes. Ningún endpoint debe devolver el `Context` entero
  tal cual: excluir `unclassified_details` donde no se use y servir los sin clasificar paginados (como los documentos de
  un dominio). Para leer un dominio, `ContextRegistry.get_domain` ya no carga `unclassified.json`.
- **Propiedades en paralelo** (G44): `ContextBuilder()` lee 4 originales a la vez por defecto; no hace falta tocar nada.
  Si el NAS de producción se satura, exponer `properties_concurrency` como ajuste de instancia.
- **G43**: `integrations/doc_organize/cache.py` (`CacheOrder` + `mime_type`), `GET /documents?mime_type=&order_by=`,
  `GET /documents/mime-types` (desplegable del filtro, mezclando las cachés de cada carpeta como ya se hace con las
  páginas); `DocumentsPage.tsx` con columnas ordenables y filtro por tipo. `order_by=owner_name` solo con el mismo
  permiso que ve `owner_name`; sin él → 403. Quitar la nota de `usuarios_y_sesiones.md`.
- **Huecos**: G42 y G43 pasan a «Resueltos» en `docs/plan/DOC_ORGANIZE_GAPS.md`; G44 si W0 lo abrió.

> **Estado (2026-11-16)**: implementada sin commit. Correcciones al plan:
> - **Historial girado**: la librería no borra el historial al borrar el contexto (ni la copia actual ni las giradas),
>   así que `context_paths` no debe listarlo; lo que sí borra y faltaba es `unclassified.json`, que ya se lista.
> - **Tamaño de la respuesta**: la web nunca devuelve el `Context` de la librería; guarda los documentos (también los
>   sin clasificar) en `context_documents` y los sirve paginados. No hacía falta cambio.
> - G42 añade `unclassified_reason` (migración `0014`); autor, descripción, palabras clave, idioma y la propuesta de
>   las reglas van en las columnas de `0013`. Si `unclassified_details` no cuadra con las rutas, se usan solo las rutas.
> - G43: el desplegable de tipos usa los mismos filtros que la lista salvo el tipo; la mezcla de varias cachés pliega
>   las mayúsculas solo en ASCII, como `COLLATE NOCASE`. Condición 4 cumplida (403 `owner_order_forbidden`).

### Orden

```
W0 (ya, con 1.5.0) ──> decide L5 de la librería
W1 (independiente) ──> release web
librería 1.6.0 ──> W2 ──> release web
```

---

## AUDIT_PLAN

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| F1 | Marcadores y enlaces de la documentación a `/admin/ai-settings` y `/admin/ai-usage` se rompen | Redirecciones permanentes en el router + buscar las rutas en `docs/` |
| F2 | Un administrador de tenant (sin instancia) vería un grupo «IA» vacío | El grupo solo se pinta si tiene algún hijo visible; test por cada combinación de permisos |
| F3 | Al quitar los `ai_*` de «Ajustes», quien los busque allí no los encuentra | Una línea en la sección de Ajustes enlazando a «IA › Parámetros» durante una versión |
| F4 | W0 sin acceso a un SMB/NFS real da cifras de un montaje simulado | La condición exige el recurso de red de pruebas; sin él no se cierra W0 |
| F5 | W2: contextos construidos con 1.5.0 no tienen `unclassified_details` | Respaldo a `unclassified_documents` (como hoy) y el aviso «reconstruye para ver los metadatos» |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| T1 | `SettingOut.group` cambia el contrato OpenAPI | Campo nuevo obligatorio en la respuesta, aditivo para clientes; regenerar `schema.d.ts` en el mismo PR |
| T2 | Dos fuentes de verdad para el grupo (backend y frontend) | Solo el backend decide; el frontend agrupa por el valor recibido |
| T3 | `GET /documents/mime-types` sobre varias cachés (varias carpetas) en red | Una consulta agregada por caché; mismo límite de carpetas que la lista (20); medir junto a W0 |
| T4 | LSP/ISP: páginas nuevas reutilizan `SettingRow`, `CapabilitiesCard`, `WorkersCard` | Se mueven a componentes propios en `features/admin/` sin cambiar sus props; ninguna interfaz crece |
| T5 | El script de W0 importa la librería y escribe en la carpeta medida (historial, contexto) | Trabaja sobre una copia del proyecto o con `output_root` temporal; nunca sobre un proyecto real |

### Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| S1 | Mover rutas puede dejar una página nueva fuera de `RequireAccess instance` | Las rutas nuevas cuelgan del mismo bloque `RequireAccess instance`; test que entra sin permiso y espera 403/redirección |
| S2 | «Parámetros de IA» vía `PATCH /admin/settings` permitiría a la página tocar claves que no son de IA | Es la misma protección que hoy (solo administrador de instancia); no amplía permisos |
| S3 | `order_by=owner_name` deja inferir propietarios a quien no ve la columna | 403 sin el permiso (condición W2) |
| S4 | «Información» muestra hosts e ids de workers | Ya visibles hoy en Ajustes con el mismo permiso; sin cambio |

### Simplificaciones posibles

- Sin `group` en el backend: el frontend agrupa por prefijo (`ai_`, `location_`, …). Menos cambios, pero frágil ante una
  clave nueva. No recomendada.
- «Parámetros de IA» como sección al final de «IA › Configuración» en vez de página propia: un enlace menos en el menú.
  Válido si el mantenedor prefiere el submenú de dos entradas.
- W0 con un único `ContextBuilder.build()` cronometrado en vez de desglosar (a)/(b)/(c): más rápido de hacer, pero no
  dice dónde se va el tiempo. No recomendada.

### Veredicto: **GO_CONDICIONAL**

Condiciones:

1. ~~W0 antes de cerrar L5 en la librería~~ — **Cumplida (2026-11-16)**: medido sobre el único recurso SMB disponible
   (NFS sin medir). Supera el umbral: red 7× local, p95 141 ms; ≈ 3,5 min por construcción en 2613 documentos, 1,5 min
   con 4 hilos. Abre G44. Detalle en `docs/plan/MEDICION_CONTEXTO_RED.md`.
2. ~~Estructura de menú confirmada por el mantenedor~~ — **Resuelta (2026-11-16)**: «Parámetros» es página propia en el
   submenú IA (`/admin/ai/parameters`). Se descarta la simplificación de llevarla a «Configuración».
3. Redirecciones de las URLs antiguas y test de grupos ocultos por permisos en el mismo PR que W1.
4. `order_by=owner_name` con 403 sin permiso en W2.
