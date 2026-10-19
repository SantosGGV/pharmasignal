#!/usr/bin/env python3
"""Hook Stop: no deja cerrar una tarea sin su entrada de bitácora de hoy.

Solo actúa cuando el último mensaje de Claude anuncia «Cierre de la tarea»,
para no cortar las preguntas a mitad de trabajo. Ese mensaje sale del campo
last_assistant_message, como recomienda la documentación de Claude Code, y
solo si no viene se busca en la transcripción. En una rama de tarea exige la
entrada de esa tarea. Si algo falla al leer la entrada, deja terminar: no
bloquea por un error del propio hook.
"""
import datetime
import json
import pathlib
import re
import subprocess
import sys

MARCA = "cierre de la tarea"
RAMA_DE_TAREA = re.compile(r"^fase\d+/(\d+\.\d+)-")


def texto_de(valor):
    """Texto de un mensaje, venga como cadena, como lista de bloques o como mensaje completo."""
    if isinstance(valor, str):
        return valor
    if isinstance(valor, dict):
        if "content" in valor:
            return texto_de(valor["content"])
        return str(valor.get("text", "")) if valor.get("type", "text") == "text" else ""
    if isinstance(valor, list):
        return "\n".join(texto_de(bloque) for bloque in valor)
    return ""


def ultimo_texto_de_la_transcripcion(ruta):
    """Plan B: texto del último mensaje del asistente en la transcripción JSONL."""
    try:
        lineas = pathlib.Path(ruta).read_text(encoding="utf-8").splitlines()
    except (OSError, TypeError, ValueError):
        return ""
    for linea in reversed(lineas[-400:]):
        try:
            entrada = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if not isinstance(entrada, dict) or entrada.get("type") != "assistant":
            continue
        texto = texto_de(entrada.get("message", {}))
        if texto.strip():
            return texto
    return ""


def git(argumentos, cwd):
    """Salida de una orden de git, o None si falla."""
    try:
        return subprocess.run(
            ["git", *argumentos], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    try:
        datos = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(datos, dict) or datos.get("stop_hook_active"):
        return 0
    texto = texto_de(datos.get("last_assistant_message"))
    if not texto.strip():
        texto = ultimo_texto_de_la_transcripcion(datos.get("transcript_path"))
    if MARCA not in texto.lower():
        return 0
    raiz = (git(["rev-parse", "--show-toplevel"], datos.get("cwd") or ".") or "").strip()
    if not raiz:
        return 0
    estado = git(["status", "--porcelain", "--untracked-files=all"], raiz)
    if estado is None:
        return 0
    rutas = [linea[3:].split(" -> ")[-1].strip('"') for linea in estado.splitlines() if len(linea) > 3]
    if not [r for r in rutas if not (r.startswith("docs/") or r == "CHANGELOG.md")]:
        return 0
    hoy = datetime.date.today().isoformat()
    tarea = RAMA_DE_TAREA.match((git(["branch", "--show-current"], raiz) or "").strip())
    patron = f"{hoy}_{tarea.group(1)}-*.md" if tarea else f"{hoy}_*.md"
    if list((pathlib.Path(raiz) / "docs" / "bitacora").glob(patron)):
        return 0
    print(
        f"Antes de cerrar la tarea falta su entrada de bitácora de hoy (docs/bitacora/{patron}). "
        "Delega en el documentador, que la crea con docs/bitacora/PLANTILLA.md: "
        "sin horas ni datos personales.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
