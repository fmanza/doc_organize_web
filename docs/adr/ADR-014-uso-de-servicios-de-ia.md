# ADR-014 — Uso de servicios de IA

- **Estado**: Aceptado (implementado en la Fase 8, 0.9.0)
- **Fecha**: 2026-11-02

## Contexto

doc_organize trae clientes para un LiteLLM Proxy (clasificación de dominio, clasificación de taxonomía, borrador de
manifiesto, uso) y para la API de facturación de GitHub (uso de Copilot). En la web integrada la clasificación con IA
era un interruptor de la construcción del contexto y el borrador era una petición síncrona.

En la web multiusuario hay tres riesgos:

- el contenido de los documentos sale de la instancia;
- con 100 000 documentos el coste puede descontrolarse;
- una URL configurable recibe una clave.

## Decisión

1. **Opt-in por ejecución**. La IA nunca se usa por defecto. `context_build` lleva `ai_classification` y el borrador es
   una operación propia, `taxonomy_draft`. La pantalla avisa de que el título y un extracto de cada documento salen de
   la aplicación. Ninguna ruta del servidor va al prompt: la muestra del borrador usa rutas relativas (G36). Ambas
   operaciones exigen el rol `editor`, y el borrador se audita.
2. **Presupuesto y cortes**:
   - un tope de documentos con IA por ejecución (`ai_max_documents_per_run`, 500 por defecto);
   - reintentos solo de conexión (`ai_retries`) y un timeout por petición (`ai_timeout_seconds`);
   - se deja de llamar tras un error de autenticación o tras 3 errores de conexión seguidos (G33, G34);
   - el run guarda el recuento (G35).
3. **El borrador no se aplica solo**. Va en el resultado del run. El usuario lo revisa en el editor y lo guarda con el
   `PUT` del manifiesto.
4. **Configuración solo del admin de instancia**:
   - la URL se valida: `http`/`https`, sin credenciales, sin *query* ni fragmento;
   - la clave solo viaja a la URL configurada, y una URL interna es una decisión del admin (riesgo aceptado);
   - los secretos siguen el ADR-004: cifrados, nunca devueltos y descifrados solo en el proceso que los usa;
   - en los jobs se descifran en el subproceso, no al encolar.
5. **Panel de uso en la API, no como job**. Son dos lecturas HTTP cortas, con timeout de 10 s y caché de 5 minutos por
   fuente en el proceso. El refresco forzado se limita a una vez cada 30 s. No es una «operación pesada» (regla 4). La
   caché se invalida si cambia la configuración, porque su clave incluye una huella de los valores.
6. **De instancia**. Como en la web integrada, `ai_settings` no es por tenant. Los tenants llegan en la Fase 9.

## Consecuencias

- Una clave mala cuesta una sola petición por ejecución. Para clasificar más de 500 documentos con IA hay que subir el
  ajuste.
- Con varios procesos `web`, cada uno tiene su propia caché del panel de uso. Como mucho se hace una consulta por
  proceso cada 5 minutos.
- Desde doc_organize 0.14.0 (L-3a…L-3e) los cortes, el presupuesto, los reintentos y el recuento los hace la
  librería: la web solo le pasa `ai_max_failures`, `ai_max_documents` y `*Config.retries`. El silencio de los loggers
  `httpx`/`httpcore` se mantiene como defensa.

## Nota (2026-11-22, web 2.1)

GitHub Copilot se quitó: ya no hay familia `github_copilot_usage` ni llamadas a la API de facturación de GitHub. La
migración `0025` borra su configuración guardada (el PAT cifrado incluido) y bajar de versión no la recupera. Si
`DOC_ORGANIZE_GITHUB_USERNAME`/`DOC_ORGANIZE_GITHUB_PAT` siguen definidas, la configuración avisa de que ya no se leen.
El panel de uso muestra el gasto y el presupuesto de la clave de LiteLLM y, además, el consumo por ejecución que
registra la web (`ai_usage`, migración `0026`). En doc_organize 2.1.0, Copilot queda obsoleto y se retira en 3.0. El
texto de arriba se conserva tal como se decidió.
