# doc_organize_web

Aplicación web multiusuario (FastAPI + React) sobre la librería
[doc_organize](https://github.com/fmanza/doc_organize): escanea carpetas de documentos locales o de red, los convierte
a Markdown y JSON con Docling y OCR, detecta duplicados y genera un contexto navegable por dominios, con proyectos,
miembros y ejecuciones en segundo plano.

> **Estado: Fase 2 (ubicaciones y ajustes, 0.3.0).** Inicio de sesión, usuarios, ubicaciones locales y de red con
> explorador de carpetas, ajustes administrables y ficha de capacidades. Las
> funcionalidades llegan fase a fase según el [ROADMAP](plan/ROADMAP.md); la web integrada de doc_organize sigue siendo
> la interfaz hasta alcanzar la [paridad](plan/PARIDAD.md).

## Uso

- [Usuarios y sesiones](guides/usuarios_y_sesiones.md): primer administrador, inicio de sesión, contraseñas,
  administración de usuarios, sesiones y auditoría.
- [Ubicaciones](guides/ubicaciones.md): carpetas de origen y destino, estados, explorador, ajustes y capacidades.

## Operación

- [Despliegue](guides/despliegue.md): Docker Compose, secretos, volúmenes y proxy TLS.
- [Montar carpetas de red](guides/carpetas_de_red.md): SMB/NFS en el servidor Linux y su paso al contenedor.
- [Publicar una versión](guides/publicar_version.md).

## Desarrollo

- [Entorno de desarrollo](guides/desarrollo.md): backend, frontend, documentación e imagen.
- Decisiones: [ADR-001](adr/ADR-001-stack-y-proyecto-aparte.md) a
  [ADR-006](adr/ADR-006-integracion-doc-organize.md), [ADR-007](adr/ADR-007-ubicaciones.md) y
  [ADR-012](adr/ADR-012-ajustes-administrables.md); propuestas para fases siguientes en
  [ADRS_PROPUESTOS](plan/ADRS_PROPUESTOS.md).
- Plan: [README del plan](plan/README.md), [arquitectura propuesta](plan/ARQUITECTURA_PROPUESTA.md),
  [ROADMAP](plan/ROADMAP.md), [huecos de doc_organize](plan/DOC_ORGANIZE_GAPS.md) y [paridad](plan/PARIDAD.md).
