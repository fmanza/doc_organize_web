#!/usr/bin/env sh
# Para la instancia aislada de preproducción y BORRA sus volúmenes (dow-preprod_*): nada de producción.
set -eu
export COMPOSE_PROJECT_NAME=dow-preprod
export COMPOSE_FILE="docker-compose.yml${COMPOSE_PATH_SEPARATOR:-:}docker-compose.preprod.yml"
export DOW_PREPROD_SOURCE="${DOW_PREPROD_SOURCE:-.}" DOW_PREPROD_OUT="${DOW_PREPROD_OUT:-.}"
docker compose down --volumes --remove-orphans
echo "Instancia de preproducción parada y sus volúmenes borrados. Borra a mano DOW_PREPROD_OUT y las copias."
