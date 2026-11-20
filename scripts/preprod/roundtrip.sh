#!/usr/bin/env sh
# Prueba de ida y vuelta de las migraciones 2.0 sobre una COPIA de la base de datos de producción (W9).
# La copia la hace la propia aplicación de producción (`app.cli backup`, copia coherente de SQLite) en el /tmp de su
# contenedor; se saca al host (tar por la salida estándar), se borra del contenedor y se prueba con backend/scripts/migration_roundtrip.py, que
# trabaja sobre otra copia temporal. Al terminar, todo se borra. El original no se abre para escribir.
# Uso:  sh scripts/preprod/roundtrip.sh [contenedor-web-de-producción]   (por defecto doc_organize_web-web-1)
set -eu
container="${1:-doc_organize_web-web-1}"
work="$(mktemp -d "${TMPDIR:-/tmp}/dow-roundtrip-XXXXXX")"
inside="/tmp/dow-roundtrip-$$"
# Git Bash (Windows): sin convertir las rutas del contenedor.
export MSYS_NO_PATHCONV=1
cleanup() {
  docker exec "$container" rm -rf "$inside" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT INT TERM
docker exec "$container" python -m app.cli backup --dest "$inside" >/dev/null
# `docker cp` no ve el tmpfs de /tmp: se saca con tar por la salida estándar.
docker exec "$container" tar -C "$inside" -cf - . | tar -C "$work" -xf -
db="$(find "$work" -name config.db | head -n 1)"
if [ -z "$db" ]; then
  echo "La copia no tiene config.db" >&2
  exit 1
fi
db="$(cygpath -w "$db" 2>/dev/null || echo "$db")"   # Git Bash: ruta del host para Python de Windows
(cd backend && uv run --frozen python scripts/migration_roundtrip.py "$db")
