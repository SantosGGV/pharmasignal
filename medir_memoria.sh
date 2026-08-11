#!/usr/bin/env bash
# Mide el consumo maximo de memoria de un script del pipeline.
#
# La utilidad time del sistema informa unicamente de la memoria del proceso que
# la invoca. En este pipeline el procesamiento no ocurre en el proceso de
# Python sino en la maquina virtual de Java que Spark levanta como proceso
# independiente, de modo que aquella medicion deja fuera precisamente lo que
# interesa medir. Aqui se muestrea el conjunto de procesos del arbol una vez por
# segundo y se conserva el maximo alcanzado.
#
# Uso:  ./medir_memoria.sh src/analisis/prr_ror.py
set -uo pipefail

if [ $# -ne 1 ]; then
  echo "Uso: $0 <ruta_del_script>"
  exit 1
fi

SCRIPT="$1"
if [ ! -f "$SCRIPT" ]; then
  echo "ERROR: no existe $SCRIPT"
  exit 1
fi

ETIQUETA="$(basename "$SCRIPT" .py)"
DIR_SALIDA="$HOME/pharmasignal/outputs"
SALIDA="$DIR_SALIDA/memoria_${ETIQUETA}.txt"
LOG="$DIR_SALIDA/log_${ETIQUETA}_medicion.txt"
mkdir -p "$DIR_SALIDA"

echo "Midiendo $SCRIPT ..."
INICIO=$(date +%s)

python -u "$SCRIPT" > "$LOG" 2>&1 &
PID=$!

MAX=0
while kill -0 "$PID" 2>/dev/null; do
  # Suma el conjunto residente de todos los procesos implicados en la
  # ejecucion, incluida la maquina virtual de Java que levanta Spark.
  ACTUAL=$(ps -eo rss,comm --no-headers \
           | grep -E "python|java" \
           | awk '{s+=$1} END {print s+0}')
  if [ "$ACTUAL" -gt "$MAX" ]; then MAX=$ACTUAL; fi
  sleep 1
done

wait "$PID"
CODIGO=$?
FIN_T=$(date +%s)
SEGUNDOS=$((FIN_T - INICIO))

{
  echo "Script: $SCRIPT"
  printf 'Pico de memoria: %.2f GB (%d kB)\n' "$(echo "$MAX / 1048576" | bc -l)" "$MAX"
  printf 'Tiempo de pared: %d:%02d\n' "$((SEGUNDOS / 60))" "$((SEGUNDOS % 60))"
  echo "Codigo de salida: $CODIGO"
} | tee "$SALIDA"
