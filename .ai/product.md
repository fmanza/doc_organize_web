# Producto — doc_organize_web

- **Qué es**: aplicación web multiusuario (FastAPI + React) que expone la funcionalidad de la librería doc_organize y
  sustituye a su web integrada.
- **Versión actual**: 2.4.0 con doc_organize 2.4.1 (todo desde la API pública de la librería), sobre la 2.3.2 (textos
  de IA al día y documentación revisada), la 2.3.1
  (los proyectos borrados sueltan sus ubicaciones), la 2.3.0 (tema claro u oscuro por usuario), la 2.2.0 (IA por
  funcionalidad con avisos flotantes y duplicados por contenido) y la 2.1.0 (contexto en pasos de trabajo, consumo de
  IA por ejecución y sin GitHub Copilot). Historial completo en `CHANGELOG.md`; siguiente: lo que quede en `docs/plan/MEJORAS.md`. Plan: `docs/plan/ROADMAP.md`.
- **Usuarios**: equipos que organizan grandes fondos documentales en una red interna, en tenants aislados; admin de
  instancia, roles del tenant con permisos y miembros de proyecto `owner`/`editor`/`viewer` (ADR-013).
- **Despliegue**: servidor Linux (producción, con montajes SMB/NFS y GPU opcional); Docker Desktop solo para desarrollo.
- **Escala de diseño**: ~100 000 documentos / ~1 TB por proyecto.

## Capacidades objetivo (paridad completa con la web integrada, por fases)

1. Identidad: usuarios, sesiones, auditoría (F1); tenants y roles (F9).
2. Ubicaciones locales y de red con sondeo, explorador de carpetas y ajustes administrables (F2).
3. Proyectos con miembros y motor de ejecuciones con progreso en vivo y cancelación (F3).
4. Escaneo y conversión con OCR, GPU, audio/vídeo, imágenes y descripción de imágenes; carpetas guardadas (F4).
5. Caché, resultados, visor y exportaciones (F5); duplicados en dos pasos (F6), también por contenido (2.2).
6. Contexto por ejes, en pasos de trabajo, y sitio aislado (F7, 2.x); IA por funcionalidad: clasificación,
   manifiestos, agentes, embeddings y consumo por ejecución (F8, 2.x).

## Fuera de alcance (por ahora)

- Subida de documentos desde el navegador (mejora opcional, P3).
- Credenciales o montaje de carpetas de red desde la app.
- Modificar doc_organize desde este repositorio.
- Exposición directa a Internet sin proxy TLS.
- Idiomas distintos del español (i18n preparado).
