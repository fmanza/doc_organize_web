#!/bin/sh
# Aplica las migraciones de config.db y ejecuta el comando del contenedor (API o worker).
set -eu
cd /app
alembic upgrade head
exec "$@"
