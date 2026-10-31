## Qué cambia

<!-- Fase del ROADMAP o motivo; resumen en 2-3 líneas -->

## Tipo

- [ ] feat · [ ] fix · [ ] hotfix · [ ] security · [ ] refactor · [ ] docs · [ ] chore

## Checklist

- [ ] Comandos de «Comandos de desarrollo» en verde (backend y frontend)
- [ ] OpenAPI exportado y cliente regenerado si cambia la API
- [ ] Migración Alembic con `downgrade` si cambia el esquema
- [ ] Sin secretos en respuestas, logs ni `run.json`
- [ ] Rutas del sistema de ficheros solo a través del resolvedor de ubicaciones
- [ ] Autorización por recurso cubierta con tests (401/403/404)
- [ ] Operaciones que mueven o borran ficheros con vista previa y confirmación
- [ ] Estados de carga, vacío, error y sin permiso en la UI
- [ ] Sin datos, rutas ni servidores reales (repositorio público)
- [ ] CHANGELOG, docs y `docs/plan/PARIDAD.md` actualizados
