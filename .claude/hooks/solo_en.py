#!/usr/bin/env python3
"""Hook PreToolUse para Edit y Write: limita dónde puede escribir un agente.

Uso: solo_en.py tests/             (calidad)
     solo_en.py docs/ CHANGELOG.md (documentador)
Las rutas se comparan con la raíz del repositorio en el que trabaja la sesión,
también dentro de un worktree y aunque el agente haya cambiado de carpeta.
Sale con código 2 (bloquea) si el fichero queda fuera de lo permitido o si la
entrada del hook no se entiende.
"""
import json
import os
import subprocess
import sys


def raiz_del_repo(cwd):
    """Raíz del repositorio que contiene cwd; si no hay, la del proyecto o cwd."""
    try:
        salida = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, capture_output=True, text=True, check=True,
        ).stdout.strip()
        if salida:
            return salida
    except (OSError, subprocess.CalledProcessError):
        pass
    return os.environ.get("CLAUDE_PROJECT_DIR") or cwd


def main():
    permitidos = sys.argv[1:]
    try:
        datos = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print("No se pudo leer la entrada del hook; se bloquea por seguridad.", file=sys.stderr)
        return 2
    entrada = datos.get("tool_input") or {}
    ruta = entrada.get("file_path") or entrada.get("notebook_path") or ""
    if not ruta:
        return 0
    cwd = datos.get("cwd") or os.getcwd()
    raiz = os.path.realpath(raiz_del_repo(cwd))
    relativa = os.path.relpath(os.path.realpath(os.path.join(cwd, ruta)), raiz)
    if not relativa.startswith(".."):
        for permitido in permitidos:
            if relativa == permitido or (permitido.endswith("/") and relativa.startswith(permitido)):
                return 0
    print(
        f"Bloqueado: este agente solo puede escribir en {', '.join(permitidos)} (intentó: {relativa}).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
