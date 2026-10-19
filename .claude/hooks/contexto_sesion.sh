#!/usr/bin/env bash
# Hook SessionStart: da a Claude la rama, la tarea de la hoja y lo pendiente de la última entrada de la bitácora,
# y hace que sus órdenes de Bash usen el entorno virtual del proyecto (también en un worktree).
# Lo que se imprime aquí entra en el contexto de la sesión; no se versiona en ningún sitio.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
comun="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [ -n "$comun" ] && [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  activar="$(dirname "$comun")/.venv/bin/activate"
  if [ -f "$activar" ] && ! grep -qF "$activar" "$CLAUDE_ENV_FILE" 2>/dev/null; then
    printf 'source "%s"\n' "$activar" >> "$CLAUDE_ENV_FILE"
  fi
fi
rama="$(git branch --show-current 2>/dev/null)"
echo "Rama actual: ${rama:-desconocida}"
case "$rama" in
  main|master) echo "Aviso: estás en $rama. Las tareas se hacen en su rama faseN/<id>-<nombre>." ;;
esac
tarea="$(printf '%s' "$rama" | sed -nE 's#^fase[0-9]+/([0-9]+\.[0-9]+)-.*#\1#p')"
if [ -n "$tarea" ]; then
  echo "Tarea de la hoja: $tarea"
  hoja="${PHARMASIGNAL_PRIVADO:-}/hoja_de_ruta.md"
  if [ -n "${PHARMASIGNAL_PRIVADO:-}" ] && [ -f "$hoja" ]; then
    patron="^\| *${tarea//./\\.} *\|"
    grep -E "$patron" "$hoja" | head -n 1 || true
  fi
fi
ultima="$(ls -1 docs/bitacora/2*.md 2>/dev/null | sort | tail -n 1)"
if [ -n "$ultima" ]; then
  echo "Última entrada de la bitácora: $ultima"
  awk '/^## Pendiente/{p=1; next} /^## /{p=0} p' "$ultima" | head -n 15
fi
if [ -n "${PHARMASIGNAL_PRIVADO:-}" ]; then
  echo "Hoja de ruta completa (privada, fuera del repo): $PHARMASIGNAL_PRIVADO/hoja_de_ruta.md"
else
  echo "Aviso: PHARMASIGNAL_PRIVADO no está definida; no se puede leer la hoja de ruta privada."
fi
exit 0
