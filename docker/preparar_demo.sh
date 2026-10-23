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

# Uso: bash docker/preparar_demo.sh [archivo de salida]
# Las rutas de las capas salen de config.toml (vía src/config.py), y la base
# respeta PHARMASIGNAL_BASE. El paquete lleva la estructura por capas (0.11):
# data/oro/<tabla>, data/plata/trad_terminos y data/diccionarios. Se publica en
# la release datos-demo-v2; datos-demo se queda con la estructura vieja para la
# imagen de v1.0-tfb.

# El repositorio es un nivel por encima de este script.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SALIDA="$(realpath -m "${1:-$REPO/docker/pharmasignal-datos-demo.tar.gz}")"

# Base y rutas de las capas, relativas a la base, desde la configuración común.
mapfile -t RUTAS_CFG < <(cd "$REPO" && python3 -c '
import os
from src import config
print(config.BASE)
for r in (config.RUTAS_ORO, config.RUTAS_PLATA, config.RUTAS_DICCIONARIOS):
    print(os.path.relpath(r, config.BASE))
')
BASE="${RUTAS_CFG[0]}"
ORO="${RUTAS_CFG[1]}"
PLATA="${RUTAS_CFG[2]}"
DICCIONARIOS="${RUTAS_CFG[3]}"

TABLAS=(
  senales_prr_ror
  geo_perfil_paises
  geo_divergencia_farmacos
  geo_divergencia_reacciones
  geo_perfil_renta
  geo_glp1_paises
  geo_evolucion_espana
  serie_temporal_familias
  serie_temporal_glp1_farmacos
  trad_terminos   # la única de plata; las demás son de oro
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
RUTAS=()
for t in "${TABLAS[@]}"; do
  if [ "$t" = trad_terminos ]; then RUTAS+=("$PLATA/$t"); else RUTAS+=("$ORO/$t"); fi
done
for r in "${RUTAS[@]}"; do
  if [ ! -d "$r" ]; then
    echo "ERROR: falta la tabla $r en $BASE. Ejecute antes el pipeline de análisis."
    exit 1
  fi
done
for d in paises.txt terminos_es.txt; do
  if [ ! -f "$DICCIONARIOS/$d" ]; then
    echo "ERROR: falta el diccionario $DICCIONARIOS/$d en $BASE."
    exit 1
  fi
done

if ! python3 -c "import deltalake" 2>/dev/null; then
  echo "ERROR: falta deltalake. Activa antes el entorno virtual (source .venv/bin/activate)."
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Solo la versión vigente de cada tabla: su _delta_log y los parquet que esa
# versión usa. Los de versiones antiguas (sin VACUUM) se quedan en la base.
python3 - "$BASE" "${RUTAS[@]}" > "$TMP/lista" <<'PY'
import os
import sys
from pathlib import Path

from deltalake import DeltaTable

base, *tablas = sys.argv[1:]
for tabla in tablas:
    raiz = Path(base, tabla)
    ficheros = [f for f in (raiz / "_delta_log").rglob("*") if f.is_file()]
    ficheros += [Path(u.removeprefix("file://")) for u in DeltaTable(str(raiz)).file_uris()]
    for f in sorted(ficheros):
        rel = os.path.relpath(f, base)
        if not Path(rel).is_relative_to(tabla):
            sys.exit(f"ERROR: {rel} queda fuera de la tabla {tabla}")
        sys.stdout.write(rel + "\0")
PY
for d in paises.txt terminos_es.txt; do printf '%s\0' "$DICCIONARIOS/$d" >> "$TMP/lista"; done

# Sin dueño local en el paquete público: uid y gid 0, sin nombres de usuario.
tar czf "$SALIDA" --owner=0 --group=0 --numeric-owner --null --verbatim-files-from -T "$TMP/lista"

# Comprobación del propio paquete: se descomprime aparte y cada tabla tiene que
# dar las mismas filas que en la base, sin tablas de más. Si no, se borra.
mkdir "$TMP/paquete"
tar xzf "$SALIDA" -C "$TMP/paquete" --no-same-owner
if ! python3 - "$BASE" "$TMP/paquete" "${RUTAS[@]}" <<'PY'
import sys
from pathlib import Path

from deltalake import DeltaTable

base, paquete, *tablas = sys.argv[1:]


def filas(raiz):
    return DeltaTable(str(raiz)).to_pyarrow_dataset().count_rows()


mal = 0
for tabla in tablas:
    esperadas = filas(Path(base, tabla))
    try:
        obtenidas = filas(Path(paquete, tabla))
    except Exception as e:
        obtenidas = f"ilegible ({type(e).__name__})"
    ok = obtenidas == esperadas
    mal += not ok
    print(f"  {'ok ' if ok else 'MAL'} {tabla}: {obtenidas} filas (base: {esperadas})")
dentro = {str(p.parent.relative_to(paquete)) for p in Path(paquete).rglob("_delta_log")}
for extra in sorted(dentro - set(tablas)):
    mal += 1
    print(f"  MAL {extra}: está en el paquete y no en la lista")
print(f"Tablas comprobadas: {len(tablas)}; con problemas: {mal}")
sys.exit(1 if mal else 0)
PY
then
  rm -f "$SALIDA"
  echo "ERROR: el paquete no cuadra con la base; se ha borrado. No lo publiques."
  exit 1
fi

echo "Archivo generado: $SALIDA"
du -h "$SALIDA"
