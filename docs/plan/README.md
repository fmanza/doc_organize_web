# Plan — separar doc_organize (librería) y doc_organize_web (React + FastAPI)

> **Estado: propuesta (2026-10-31).** Todavía no hay código: esta carpeta es el plan de partida para abrir
> `/phase 0` en doc_organize_web. Lo que dependa de verificar una API o una herramienta está marcado
> `PENDIENTE DE VERIFICAR`.

## Contexto

| Repositorio | Qué es | Papel en este plan |
|---|---|---|
| [doc_organize](https://github.com/fmanza/doc_organize) | Librería Python + CLI que escanea carpetas de documentos (PDF, Office, imágenes), los convierte a Markdown/JSON con [Docling](https://github.com/docling-project/docling) (con OCR), deduplica, cachea en SQLite y genera un «contexto» navegable por dominios. Hoy incluye además una web FastAPI + Jinja (`src/doc_organize/web/`) con usuarios multi-tenant (`src/doc_organize/auth/`) | **Parte API**: se convierte en librería pura; su web se sustituye por este proyecto ([TAREAS_DOC_ORGANIZE.md](TAREAS_DOC_ORGANIZE.md)) |
| [doc_organize_web](https://github.com/fmanza/doc_organize_web) | Este repositorio | **Parte web**: backend FastAPI + frontend React que consume doc_organize ([ROADMAP.md](ROADMAP.md)) |
| [util_bbdd_web](https://github.com/fmanza/util_bbdd_web) (1.10.1) | Aplicación web sobre la librería [util_bbdd](https://github.com/fmanza/util_bbdd), con el mismo modelo | **Referencia**: estructura, stack, ADRs, CI, Docker e instrucciones IA se copian de ahí. Abreviado «UBW» en este plan |

Identificadores usados en todo el plan:

- `L-*`: tareas en doc_organize. `WB-*` / `WF-*` / `WD-*`: tareas de backend, frontend e infraestructura de
  doc_organize_web. `F0…F10`: fases del ROADMAP.
- `G*`: huecos de la API de doc_organize ([DOC_ORGANIZE_GAPS.md](DOC_ORGANIZE_GAPS.md)). `ADR-*`: decisiones
  ([ADRS_PROPUESTOS.md](ADRS_PROPUESTOS.md)). `P*` / `R*`: decisiones y riesgos ([DECISIONES_Y_RIESGOS.md](DECISIONES_Y_RIESGOS.md)).
- Prefijo de variables de entorno: `DOW_` (doc_organize_web).

Para empezar: leer este README, después [ARQUITECTURA_PROPUESTA.md](ARQUITECTURA_PROPUESTA.md) y
[ROADMAP.md](ROADMAP.md). Las fases web dependen de versiones concretas de doc_organize (columna «Requiere» del
ROADMAP): ambos repos avanzan en paralelo.

## Decisiones tomadas por el mantenedor

| # | Tema | Decisión |
|---|---|---|
| D1 | Modelo | **doc_organize = librería pura + CLI** (como util_bbdd). `doc_organize_web` = monorepo **backend FastAPI + frontend React** que consume doc_organize como wheel fijado, a través de una capa anticorrupción. |
| D2 | Identidad | **Por fases**: primero el modelo de util_bbdd_web (usuarios `admin`/`user` + miembros por proyecto `owner`/`editor`/`viewer`); multi-tenant en una fase posterior. |
| D3 | Red | **Montajes + allowlist**: SMB/NFS montados como volúmenes; la app solo ve «ubicaciones» registradas por un admin. Sin credenciales de red en la app. |
| D4 | Datos existentes | **Empezar limpio**: los proyectos se registran de nuevo apuntando a sus carpetas. |
| D5 | Instrucciones IA | Set completo en `doc_organize_web` **y** adaptar las de `doc_organize` a «librería pura». |
| D6 | Imágenes Docker | **CPU** por defecto + variantes **GPU**, **LibreOffice** (`.xls` legado) y **AV** (audio/vídeo). |
| D7 | Alcance | **Paridad completa** con la web actual, incluida IA y contexto, por fases. |
| D8 | Persistencia | Configuración y parámetros en **SQLite** (SQLAlchemy 2 + Alembic) con ruta de escape a otra BD. |
| D9 | Despliegue | **Servidor Linux** en producción; Docker Desktop solo para desarrollo. |
| D10 | Volumen | Diseño para **~100 000 documentos / ~1 TB por proyecto**. |
| D11 | Documentación | **Zensical en todo y mkdocs retirado**: documentación de ambos repos (L-13b) y sitio de contexto de los proyectos (L-8). |
| D12 | Repositorio | `doc_organize_web` **ya creado y público**: seguridad del repo desde F0. |
| D13 | Resto | Sin subida desde navegador; solo español con i18n; retirada 0.12.0/1.0.0; sitio en `iframe sandbox`. Detalle en `DECISIONES_Y_RIESGOS.md`. |

## Contenido

| Fichero | Qué contiene |
|---|---|
| [ARQUITECTURA_PROPUESTA.md](ARQUITECTURA_PROPUESTA.md) | Vista general, capas, modelo de datos, ubicaciones locales/red, jobs, Docker, configuración |
| [TAREAS_DOC_ORGANIZE.md](TAREAS_DOC_ORGANIZE.md) | **Parte back (API = librería)**: tareas `L-*` en doc_organize, incluida la retirada de `web/` y `auth/` |
| [ROADMAP.md](ROADMAP.md) | **Parte WEB**: fases 0–10 de doc_organize_web con tareas backend `WB-*` y frontend `WF-*` |
| [DOC_ORGANIZE_GAPS.md](DOC_ORGANIZE_GAPS.md) | Huecos de la API de doc_organize detectados (equivalente a `UTIL_BBDD_GAPS.md`) |
| [ADRS_PROPUESTOS.md](ADRS_PROPUESTOS.md) | ADR-001…ADR-013 propuestos para doc_organize_web |
| [DEPENDENCIAS.md](DEPENDENCIAS.md) | Librerías Python, npm y paquetes de sistema por imagen |
| [INSTRUCCIONES_IA.md](INSTRUCCIONES_IA.md) | Inventario de ficheros IA a crear (web) y a adaptar (librería) |
| [MEJORAS.md](MEJORAS.md) | Mejoras propuestas por buenas prácticas, priorizadas |
| [DECISIONES_Y_RIESGOS.md](DECISIONES_Y_RIESGOS.md) | Decisiones de las preguntas abiertas y riesgos |

## Secuencia global (dos repos en paralelo)

```text
doc_organize (librería)              doc_organize_web
───────────────────────              ────────────────────────────────────────
L-0  inventario de paridad    ──►    F0  fundaciones (consume doc_organize 0.9.x)
L-1…L-6  API pública 0.10.0   ──►    F1  identidad
         (progreso, cancel,          F2  ubicaciones locales/red + ajustes
          desacople ai/auth,         F3  proyectos + motor de ejecuciones
          layout, dedup seco)        F4  escaneo y conversión
L-7…L-9  0.11.0 (export,      ──►    F5  caché, resultados y descargas
          sitio, red)                F6  duplicados
                                     F7  contexto y taxonomías
                                     F8  IA (clasificación, manifiestos, uso)
L-10 deprecar `web` (0.12.0)  ◄──    paridad alcanzada (F8 cerrada)
                                     F9  multi-tenant
L-11 retirar web/ y auth/     ◄──    F10 endurecimiento y release 1.0.0
     → doc_organize 1.0.0
```

Regla: **la web actual de doc_organize no se elimina hasta que doc_organize_web tenga paridad** (checklist de L-0), para
no dejar a nadie sin interfaz.
