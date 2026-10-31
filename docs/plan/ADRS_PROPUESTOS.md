# ADRs propuestos para doc_organize_web

Se redactan en la Fase 0 (001–006) o en la fase indicada. Los marcados «≈ UBW» copian la decisión de util_bbdd_web
adaptando nombres.

| ADR | Título | Fase | Decisión resumida |
|---|---|---|---|
| 001 | Stack y proyecto aparte | 0 | ≈ UBW: proyecto aparte con su ciclo de releases; monorepo backend + frontend; React 19 + TS 5.9 + Vite + Mantine; FastAPI + Pydantic 2 en Python 3.12; SQLite + SQLAlchemy 2 + Alembic; uv y npm |
| 002 | Ejecución de jobs | 0/3 | ≈ UBW (cola propia sobre `runs`, subproceso por job) **+ colas `cpu`/`gpu`** y concurrencia 1 por defecto por el consumo de memoria de Docling; una escritura por proyecto a la vez |
| 003 | Autenticación y sesiones | 0/1 | ≈ UBW: Argon2id, cookie `__Host-` opaca en BD, CSRF firmado, bloqueo por intentos; `tenant_id` desde el primer día con tenant `default` |
| 004 | Cifrado de secretos | 0/8 | ≈ UBW: Fernet con lista de claves (rotación con `app.cli rotate-secrets`) para credenciales IA; nunca en logs, respuestas ni `run.json` |
| 005 | Workspace, estado y salidas | 0/3 | **Nuevo**: tres zonas — `config.db` y `projects/<id>/cache.db` en el volumen local `data` (SQLite nunca en red); artefactos por ejecución en `workspace`; salidas del proyecto (Markdown, JSON, imágenes, duplicados, sitio) en la ubicación destino |
| 006 | Integración con doc_organize | 0 | ≈ UBW: wheel de la release en GitHub con hash en `uv.lock`; solo `integrations/doc_organize/` importa la librería; huecos en `DOC_ORGANIZE_GAPS.md` |
| 007 | Ubicaciones locales y de red | 2 | **Nuevo**: montajes fuera de la app + allowlist bajo `DOW_LOCATIONS_ROOT`; resolución segura; sondeo; `ro`/`rw`; sin credenciales SMB en la app |
| 008 | Progreso por SSE en lugar de WebSocket | 3 | **Nuevo**: sustituye a ADR-001 de doc_organize (SSE vs WebSocket); el run sobrevive al cierre de la pestaña; reanudación con `Last-Event-ID` |
| 009 | Deduplicación en dos pasos | 6 | **Nuevo**: vista previa obligatoria, aplicar solo grupos confirmados, modos `move/copy/report_only`, auditoría por fichero |
| 010 | Sitio de contexto aislado | 7 | ≈ ADR-007 UBW: el sitio Zensical generado se sirve en un origen o `iframe sandbox` aislado con CSP propia |
| 011 | Modelos de IA/OCR sin Internet | 0/4 | **Nuevo**: modelos de Docling, RapidOCR, EasyOCR y Whisper precargados en la imagen (o volumen `models` de solo lectura); `HF_HUB_OFFLINE=1` en runtime |
| 012 | Ajustes administrables | 2 | ≈ ADR-012 UBW: BD > entorno > defecto; sin reinicio |
| 013 | Multi-tenant | 9 | **Nuevo**: aislamiento por `tenant_id` en repositorios (no en routers), admin de instancia, roles con permisos; migración de `admin`/`user` |
