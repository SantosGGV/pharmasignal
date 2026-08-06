#!/usr/bin/env bash
# Empaqueta las tablas que consume el frontend en un único archivo comprimido,
# pensado para publicarse como recurso descargable junto al código.
#
# La aplicación solo lee tablas de resultados, no las tablas curadas
# intermedias: el conjunto completo ocupa varios gigabytes mientras que lo
# estrictamente necesario para que la interfaz funcione son unas decenas de
# megabytes. Esa diferencia es la que permite distribuir una demostración
# funcional sin exigir la ejecución previa del pipeline.
set -euo pipefail

BASE="$HOME/pharmasignal"
SALIDA="$BASE/docker/pharmasignal-datos-demo.tar.gz"

TABLAS=(
  senales_prr_ror
  geo_perfil_paises
  geo_divergencia_farmacos
  geo_divergencia_reacciones
  geo_senales_espana
  geo_perfil_renta
  geo_glp1_paises
  geo_evolucion_espana
  serie_temporal_familias
  serie_temporal_glp1_farmacos
  trad_terminos
  # Tablas del explorador. Las dos primeras son los catálogos de entidades que
  # alimentan el buscador; el resto resuelve cada combinación del constructor.
  expl_catalogo_farmacos
  expl_catalogo_reacciones
  expl_farmaco_trimestre
  expl_farmaco_pais
  expl_farmaco_indicacion
  expl_farmaco_gravedad
  expl_reaccion_trimestre
  expl_reaccion_pais
  expl_farmaco_reaccion_trimestre
  expl_farmaco_reaccion_pais
  expl_reaccion_farmaco_trimestre
  expl_reaccion_farmaco_pais
  expl_farmaco_indicacion_trimestre
  expl_farmaco_gravedad_trimestre
)

cd "$BASE"

# Se comprueba que todas las tablas existen antes de empaquetar, para que un
# archivo incompleto no llegue a generarse.
for t in "${TABLAS[@]}"; do
  if [ ! -d "data/curated/$t" ]; then
    echo "ERROR: falta la tabla $t. Ejecute antes el pipeline de análisis."
    exit 1
  fi
done

RUTAS=()
for t in "${TABLAS[@]}"; do RUTAS+=("data/curated/$t"); done
RUTAS+=("data/diccionarios/paises.txt" "data/diccionarios/terminos_es.txt")

tar czf "$SALIDA" "${RUTAS[@]}"

echo "Archivo generado: $SALIDA"
du -h "$SALIDA"
