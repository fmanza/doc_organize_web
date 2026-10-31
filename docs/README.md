# doc_organize_web

Aplicación web multiusuario (FastAPI + React) sobre la librería
[doc_organize](https://github.com/fmanza/doc_organize): escanea carpetas de documentos locales o de red, los convierte
a Markdown y JSON con Docling y OCR, detecta duplicados y genera un contexto navegable por dominios, con proyectos,
miembros y ejecuciones en segundo plano.

> **Estado: Fase 0 (fundaciones, 0.1.0).** La aplicación arranca, sirve la SPA y comprueba su salud. Las
> funcionalidades llegan fase a fase según el [ROADMAP](plan/ROADMAP.md); la web integrada de doc_organize sigue siendo
> la interfaz hasta alcanzar la [paridad](plan/PARIDAD.md).

## Operación

- [Despliegue](guides/despliegue.md): Docker Compose, secretos, volúmenes y proxy TLS.
- [Publicar una versión](guides/publicar_version.md).

## Desarrollo

- [Entorno de desarrollo](guides/desarrollo.md): backend, frontend, documentación e imagen.
- Decisiones: [ADR-001](adr/ADR-001-stack-y-proyecto-aparte.md) a
  [ADR-006](adr/ADR-006-integracion-doc-organize.md); propuestas para fases siguientes en
  [ADRS_PROPUESTOS](plan/ADRS_PROPUESTOS.md).
- Plan: [README del plan](plan/README.md), [arquitectura propuesta](plan/ARQUITECTURA_PROPUESTA.md),
  [ROADMAP](plan/ROADMAP.md), [huecos de doc_organize](plan/DOC_ORGANIZE_GAPS.md) y [paridad](plan/PARIDAD.md).
