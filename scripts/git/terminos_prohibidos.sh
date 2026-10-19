#!/usr/bin/env bash
# Hook pre-commit: falla si lo que se va a versionar contiene un término de la lista privada
# (empleador, clientes, rutas personales, correos...). La lista vive fuera del repo.
# Sin argumentos revisa lo preparado para el commit; con --trabajo, todo lo que aún no está
# en el último commit (cambios y ficheros nuevos). Solo enseña fichero:línea, nunca el término.
set -uo pipefail
lista="${PHARMASIGNAL_PRIVADO:-}/terminos_prohibidos.txt"
if [ -z "${PHARMASIGNAL_PRIVADO:-}" ] || [ ! -s "$lista" ]; then
  echo "Falta la lista privada de términos prohibidos. Define PHARMASIGNAL_PRIVADO y crea terminos_prohibidos.txt." >&2
  exit 1
fi
patrones="$(grep -vE '^[[:space:]]*(#|$)' "$lista")"
[ -n "$patrones" ] || exit 0

# Convierte un diff -U0 en líneas «fichero:línea:texto» con lo añadido.
anadidas() {
  awk '
    /^\+\+\+ / { f = $0; sub(/^\+\+\+ (b\/)?/, "", f); next }
    /^@@/ { split($3, a, ","); n = substr(a[1], 2) + 0; next }
    /^\+/ { print f ":" n ":" substr($0, 2); n++ }
  '
}

if [ "${1:-}" = "--trabajo" ]; then
  candidatos="$(
    { git -c core.quotepath=off diff HEAD -U0 --no-color --no-ext-diff | anadidas
      git ls-files --others --exclude-standard -z | xargs -0 -r grep -nHI '' -- ; } 2>/dev/null
  )"
else
  candidatos="$(git -c core.quotepath=off diff --cached -U0 --no-color --no-ext-diff | anadidas)"
fi
coincidencias="$(printf '%s\n' "$candidatos" | grep -iF -f <(printf '%s\n' "$patrones") | cut -d: -f1,2 | sort -u)"
if [ -n "$coincidencias" ]; then
  echo "Bloqueado: estas líneas contienen términos de la lista privada (no se enseña cuál):" >&2
  printf '%s\n' "$coincidencias" >&2
  exit 1
fi
exit 0
