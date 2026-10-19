#!/usr/bin/env bash
# Hook prepare-commit-msg (vía pre-commit): antepone [id] de la tarea, sacado de la rama faseN/<id>-<nombre>.
set -euo pipefail
mensaje="${1:-${PRE_COMMIT_COMMIT_MSG_FILENAME:-}}"
origen="${PRE_COMMIT_COMMIT_MSG_SOURCE:-${2:-}}"
[ -n "$mensaje" ] && [ -f "$mensaje" ] || exit 0
case "$origen" in merge|squash|commit) exit 0 ;; esac
rama="$(git branch --show-current 2>/dev/null || true)"
id="$(printf '%s' "$rama" | sed -nE 's#^fase[0-9]+/([0-9]+\.[0-9]+)-.*#\1#p')"
[ -n "$id" ] || exit 0
if head -n 1 "$mensaje" | grep -qF "[$id]"; then exit 0; fi
sed -i "1s/^/[$id] /" "$mensaje"
