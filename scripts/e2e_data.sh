#!/usr/bin/env sh
# Datos sintéticos de los E2E (CI y local): carpetas bajo dev-data/ que docker-compose.e2e.yml monta en /mnt.
# Solo texto inventado: nada de documentos reales. Se puede repetir (sobrescribe).
set -eu
root="${1:-dev-data}"
e2e="$root/e2e"
mkdir -p "$e2e/expedientes/2024" "$e2e/expedientes/2025" "$e2e/proyectos/2024" "$e2e/proyectos/duplicados" \
  "$e2e/w9" "$root/e2e-out"
echo "documento sintético" > "$e2e/proyectos/2024/factura.txt"
echo "<html><body><h1>Nota sintética</h1><p>Escaneo E2E.</p></body></html>" > "$e2e/proyectos/2024/nota.html"
echo "acta sintética de la reunión" > "$e2e/proyectos/duplicados/acta.txt"
echo "acta sintética de la reunión" > "$e2e/proyectos/duplicados/acta copia.txt"
touch -d "2024-01-01" "$e2e/proyectos/duplicados/acta.txt"   # el original es el más antiguo

# W9 (doc_organize 2.0): ejes con IVA, versiones de un documento, uno para la IA y una credencial que se redacta.
w9="$e2e/w9"   # aparte de proyectos/: los E2E anteriores cuentan lo que hay allí
printf 'Factura sintética número 1.\nImporte con IVA del 21 por ciento.\n' > "$w9/factura_luz.txt"
printf 'Informe sintético de calidad del proceso.\n' > "$w9/informe_calidad.txt"
printf 'Manual sintético del proceso, primera edición.\n' > "$w9/Manual_proceso_v1.txt"
printf 'Manual sintético del proceso, segunda edición revisada.\n' > "$w9/Manual_proceso_v2.txt"
printf 'Receta sintética de cocina con harina y huevos.\n' > "$w9/receta.txt"
printf 'Nota sintética de acceso.\nContraseña: Sintetica-E2E-2024!\n' > "$w9/nota_acceso.txt"
chmod 777 "$root/e2e-out"
