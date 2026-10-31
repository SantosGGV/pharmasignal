#!/usr/bin/env bash
# Hook pre-commit: pasa las pruebas con el entorno virtual del proyecto, esté activado o no.
# En un worktree usa el entorno del repositorio principal. El bin del entorno va primero en el PATH
# para que los scripts que lanzan las pruebas (como preparar_demo.sh) usen ese mismo Python.
set -euo pipefail
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  py="$VIRTUAL_ENV/bin/python"
else
  comun="$(git rev-parse --path-format=absolute --git-common-dir)"
  py="$(dirname "$comun")/.venv/bin/python"
fi
if [ ! -x "$py" ]; then
  echo "No encuentro el entorno virtual del proyecto ($py)." >&2
  exit 1
fi
export VIRTUAL_ENV="$(dirname "$(dirname "$py")")"
export PATH="$(dirname "$py"):$PATH"
exec "$py" -m pytest tests/ -q
