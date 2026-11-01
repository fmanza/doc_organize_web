#!/bin/sh
# Aplica las migraciones de config.db y ejecuta el comando del contenedor (API o worker).
set -eu
# torch no crea la carpeta de PYTORCH_KERNEL_CACHE_PATH (solo la de por defecto): se prepara en el tmpfs.
if [ -n "${PYTORCH_KERNEL_CACHE_PATH:-}" ]; then mkdir -p "$PYTORCH_KERNEL_CACHE_PATH"; fi
cd /app
alembic upgrade head
exec "$@"
