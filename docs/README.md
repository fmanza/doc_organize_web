# doc_organize_web

Aplicación web multiusuario (FastAPI + React) sobre la librería
[doc_organize](https://github.com/fmanza/doc_organize): escanea carpetas de documentos locales o de red, los convierte
a Markdown y JSON con Docling y OCR, detecta duplicados y genera un contexto navegable por dominios, con proyectos,
miembros y ejecuciones en segundo plano.

Con doc_organize 2.2, el contexto se organiza por **ejes** de taxonomía (dominio, tipo de material y los que solo
etiquetan), desde una plantilla o el manifiesto del proyecto, en pasos de trabajo (Taxonomía → Construir → Resultado →
Revisar → Calidad → Entregar), con reglas, clasificación semántica, IA con cita y decisiones de personas; se revisa y
se mide su calidad, y se entrega como Excel, sitio sin conexión o paquete para IA. Los duplicados se buscan también por
contenido (mismo texto o, con IA, contenido parecido), y la IA se configura y se mide por funcionalidad.

## Uso

- [Usuarios y sesiones](guides/usuarios_y_sesiones.md): primer administrador, inicio de sesión, contraseñas, tema
  claro u oscuro, administración de usuarios, sesiones y auditoría.
- [Tenants y roles](guides/tenants_y_roles.md): organizaciones aisladas, administrador de la instancia, selector de
  tenant y roles con permisos.
- [Ubicaciones](guides/ubicaciones.md): carpetas de origen y destino, estados, uso por proyectos, explorador, ajustes
  y capacidades.
- [Proyectos](guides/proyectos.md), [Ejecuciones](guides/ejecuciones.md) y
  [Escaneo y conversión](guides/escaneo.md): carpetas, opciones, incremental, errores y forzar reconversión.
- [Documentos, búsqueda y exportaciones](guides/documentos.md): caché, visor, búsqueda de texto completo, ZIP y Excel.
- [Duplicados](guides/duplicados.md): exactos, versiones, nombres parecidos y por contenido; revisar, ver diferencias
  y aplicar (copiar, mover o solo informe) en dos pasos.
- [Contexto y taxonomías](guides/contexto.md): ejes, carpeta reorganizada, sitio, manifiesto y plantillas, perfil,
  versiones, semántica, revisar clasificación y decisiones, Calidad, agentes y entregas.
- [Inteligencia artificial](guides/ia.md): configuración por funcionalidad, pruebas de modelos, clasificar y describir
  con IA, semántica, duplicados por contenido, borrador, agentes, modelos locales y consumo.

## Operación

- [Despliegue](guides/despliegue.md): Docker Compose, secretos, volúmenes, diagnóstico, IA, modelos de Docling,
  worker con GPU, copias de seguridad y proxy TLS.
- [Montar carpetas de red](guides/carpetas_de_red.md): SMB/NFS en el servidor Linux y su paso al contenedor.
- [Seguridad (ASVS nivel 2)](security/ASVS_L2.md): controles verificados.
- [Preproducción de la 2.0](guides/preproduccion_2_0.md): probar migraciones, diagnóstico y entregas con datos reales
  sin tocarlos.
- [Publicar una versión](guides/publicar_version.md).

## Desarrollo

- [Entorno de desarrollo](guides/desarrollo.md): backend, frontend, documentación e imagen.
- Decisiones: [ADR-001](adr/ADR-001-stack-y-proyecto-aparte.md) a
  [ADR-006](adr/ADR-006-integracion-doc-organize.md), [ADR-007](adr/ADR-007-ubicaciones.md),
  [ADR-008](adr/ADR-008-progreso-sse.md), [ADR-010](adr/ADR-010-sitio-de-contexto-aislado.md),
  [ADR-011](adr/ADR-011-modelos-sin-internet.md), [ADR-012](adr/ADR-012-ajustes-administrables.md),
  [ADR-013](adr/ADR-013-multi-tenant.md), [ADR-014](adr/ADR-014-uso-de-servicios-de-ia.md) y
  [ADR-015](adr/ADR-015-endurecimiento.md); propuestas para fases siguientes en
  [ADRS_PROPUESTOS](plan/ADRS_PROPUESTOS.md).
- Plan: [README del plan](plan/README.md), [arquitectura propuesta](plan/ARQUITECTURA_PROPUESTA.md),
  [ROADMAP](plan/ROADMAP.md), [huecos de doc_organize](plan/DOC_ORGANIZE_GAPS.md) y [paridad](plan/PARIDAD.md).
