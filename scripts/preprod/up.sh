#!/usr/bin/env sh
# Levanta la instancia AISLADA de preproducción (W9). No toca la de producción: otro proyecto de Compose
# (dow-preprod), otros volúmenes y otro puerto, y solo docker-compose.yml + docker-compose.preprod.yml (nunca el
# override local). Uso:
#   DOW_PREPROD_SOURCE=/ruta/copia/CALIDAD_VD DOW_PREPROD_OUT=/ruta/vacia sh scripts/preprod/up.sh
# Variables opcionales: DOW_TAG (imagen, por defecto la del árbol: se construye), DOW_PORT (18090).
set -eu
: "${DOW_PREPROD_SOURCE:?Define DOW_PREPROD_SOURCE (copia o carpeta que se monta de solo lectura)}"
: "${DOW_PREPROD_OUT:?Define DOW_PREPROD_OUT (carpeta vacía para las salidas)}"
if [ -n "$(ls -A "$DOW_PREPROD_OUT" 2>/dev/null)" ]; then
  echo "DOW_PREPROD_OUT no está vacía: usa una carpeta nueva." >&2
  exit 1
fi
export COMPOSE_PROJECT_NAME=dow-preprod
export COMPOSE_FILE="docker-compose.yml${COMPOSE_PATH_SEPARATOR:-:}docker-compose.preprod.yml"
export DOW_PORT="${DOW_PORT:-18090}"
export DOW_TAG="${DOW_TAG:-preprod}"
docker compose config --services >/dev/null
if [ "${DOW_BUILD:-1}" = 1 ]; then
  docker build -f docker/Dockerfile --target runtime -t "doc_organize_web:$DOW_TAG" .
fi
docker compose up -d --no-build web worker
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$DOW_PORT/api/health" | grep -q '"worker":"ok"'; then break; fi
  if [ "$i" = 60 ]; then docker compose logs --tail 50; exit 1; fi
  sleep 3
done
echo "Instancia aislada en http://127.0.0.1:$DOW_PORT (proyecto de Compose dow-preprod)."
echo "Crea su admin: printf '%s\n' \"\$PASSWORD\" | COMPOSE_PROJECT_NAME=dow-preprod COMPOSE_FILE=\"$COMPOSE_FILE\" docker compose exec -T web python -m app.cli create-admin --username preprod-admin --password-stdin"
