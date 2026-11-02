# 00_REQUEST

- fecha: 2026-11-02
- skill: phase (`phase-implementation`)

```text
/phase

Fase: 5
Alcance: completa (WB-5.1, WB-5.2, WB-5.3, WF-5.1)
Mejoras opcionales: búsqueda de texto completo (FTS5) sobre el Markdown convertido; backup de cache.db
Restricciones: doc_organize 0.11.0 (wheel de la release v0.11.0 con hash, L-7 publicado); dependencias nuevas
permitidas si hacen falta (p. ej. DOMPurify y un renderizador Markdown en el frontend); sin GPU ni red en las pruebas
```

Notas del mantenedor sobre doc_organize 0.11.0 (al integrarlo):

- Las funciones de escritura de `doc_organize.export` son síncronas: desde código async, `asyncio.to_thread`;
  `on_progress` corre en ese hilo.
- Diferencias con la web anterior (CHANGELOG de doc_organize): `cache_export.json` ordenado por ruta; exportar un
  proyecto sin escanear no crea un `cache.db` vacío; los enlaces simbólicos de `Conversión/` no entran en el ZIP; los
  caracteres de control de los mensajes de error se quitan del Excel.
