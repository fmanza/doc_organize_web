# Producto — doc_organize_web

- **Qué es**: aplicación web multiusuario (FastAPI + React) que expone la funcionalidad de la librería doc_organize y
  sustituye a su web integrada.
- **Versión actual**: 0.5.0 (Fase 4, escaneo y conversión), con doc_organize 0.10.0 y Pillow 13. Siguiente: Fase 5
  (caché, resultados y descargas; requiere doc_organize 0.11.0, L-7).
  Plan: `docs/plan/ROADMAP.md`.
- **Usuarios**: equipos que organizan grandes fondos documentales en una red interna; rol `admin` y rol `user`;
  miembros de proyecto `owner`/`editor`/`viewer`. Multi-tenant en la Fase 9.
- **Despliegue**: servidor Linux (producción, con montajes SMB/NFS y GPU opcional); Docker Desktop solo para desarrollo.
- **Escala de diseño**: ~100 000 documentos / ~1 TB por proyecto.

## Capacidades objetivo (paridad completa con la web integrada, por fases)

1. Identidad: usuarios, sesiones, auditoría (F1); tenants y roles (F9).
2. Ubicaciones locales y de red con sondeo, explorador de carpetas y ajustes administrables (F2).
3. Proyectos con miembros y motor de ejecuciones con progreso en vivo y cancelación (F3).
4. Escaneo y conversión con OCR, GPU, audio/vídeo, imágenes y descripción de imágenes; carpetas guardadas (F4).
5. Caché, resultados, visor y exportaciones (F5); duplicados en dos pasos (F6).
6. Contexto, taxonomías y sitio aislado (F7); IA: clasificación, manifiestos y uso (F8).

## Fuera de alcance (por ahora)

- Subida de documentos desde el navegador (mejora opcional, P3).
- Credenciales o montaje de carpetas de red desde la app.
- Modificar doc_organize desde este repositorio.
- Exposición directa a Internet sin proxy TLS.
- Idiomas distintos del español (i18n preparado).
