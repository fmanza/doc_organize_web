# ADR-004 — Cifrado de secretos

- **Estado**: Aceptado (claves desde la Fase 0; credenciales IA cifradas en la Fase 8)
- **Fecha**: 2026-10-31

## Contexto

La aplicación guarda credenciales de servicios de IA por familia (LiteLLM de uso, clasificación de dominio y de
taxonomía, borrador de manifiesto, PAT de GitHub Copilot). La web integrada de doc_organize ya las cifra con Fernet
(`auth/secrets_cipher.py`). No hay credenciales de red: los montajes SMB/NFS se hacen fuera de la app (D3, ADR-007).

## Decisión

1. Secretos de la instancia solo por **Docker secrets** (`/run/secrets/dow_app_secret_key`,
   `/run/secrets/dow_fernet_keys`, `/run/secrets/dow_metrics_token`), generados con `scripts/generate_secrets.py`;
   `secrets/` está git-ignored. En producción `dow_app_secret_key` y `dow_fernet_keys` son obligatorios.
2. Credenciales IA en `ai_settings` cifradas con **MultiFernet**: `dow_fernet_keys` es una lista separada por comas;
   la primera cifra y todas descifran. Rotación con `python -m app.cli rotate-secrets` (vuelve a cifrar con la
   primera).
3. **Nunca en claro**: ni en respuestas (solo «configurado» + últimos 4 caracteres), logs, `run.json`, mensajes de
   error ni excepciones re-lanzadas. Se registra solo `type(exc).__name__`.
4. Precedencia: valor cifrado en `ai_settings` > variable `DOC_ORGANIZE_*` del entorno (compatible con la librería).
5. El subproceso de un job descifra solo lo que su operación necesita y lo pasa a doc_organize como `*Config`
   explícito (G3, L-3), nunca por variables de entorno visibles en `ps`.

## Consecuencias

- Perder `dow_fernet_keys` obliga a reintroducir las credenciales IA; el backup de `config.db` no basta sin la clave.
