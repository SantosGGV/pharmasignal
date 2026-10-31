#!/usr/bin/env python3
"""Hook Stop: no deja cerrar una tarea ni una sesión sin su entrada de bitácora de hoy.

Solo actúa cuando el último mensaje de Claude empieza por «## Cierre de la
tarea» o «## Cierre de la sesión» (/cerrar), para no cortar las preguntas a
mitad de trabajo ni los mensajes que solo mencionan el cierre. Ese mensaje sale del campo last_assistant_message, como recomienda
la documentación de Claude Code, y solo si no viene se busca en la
transcripción. En una rama de tarea exige la
entrada de esa tarea. Si algo falla al leer la entrada, deja terminar: no
bloquea por un error del propio hook. rastro_sesion.py y guardar_cierre.py
reutilizan sus funciones.
"""
import datetime
import json
import pathlib
import re
import subprocess
import sys

MARCAS = ("## cierre de la tarea", "## cierre de la sesión")
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
    """Salida de una orden de git, o None si falla. Las rutas con acentos salen tal cual, no en octal."""
    try:
        return subprocess.run(
            ["git", "-c", "core.quotepath=false", *argumentos], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def rutas_fuera_de_docs(rutas):
    """Las rutas que no son de docs/ ni CHANGELOG.md: las que piden entrada de bitácora."""
    return [r for r in rutas if not (r.startswith("docs/") or r == "CHANGELOG.md")]


def rutas_sucias(raiz):
    """Rutas con cambios sin commit (incluidas las nuevas), o None si git falla.

    Con -z git no escapa los nombres, y en un renombrado da el nombre nuevo y,
    en la entrada siguiente, el viejo: cuentan los dos.
    """
    estado = git(["status", "--porcelain", "-z", "--untracked-files=all"], raiz)
    if estado is None:
        return None
    rutas, entradas = [], iter(estado.split("\0"))
    for entrada in entradas:
        if len(entrada) > 3:
            rutas.append(entrada[3:])
            if "R" in entrada[:2] or "C" in entrada[:2]:
                viejo = next(entradas, "")
                if "R" in entrada[:2] and viejo:
                    rutas.append(viejo)
    return rutas


def patron_de_entrada(rama, fecha):
    """Patrón de la entrada de bitácora de esa fecha: la de su tarea en una rama de tarea."""
    tarea = RAMA_DE_TAREA.match(rama or "")
    return f"{fecha}_{tarea.group(1)}-*.md" if tarea else f"{fecha}_*.md"


def hay_entrada(raiz, rama, fecha):
    return bool(list((pathlib.Path(raiz) / "docs" / "bitacora").glob(patron_de_entrada(rama, fecha))))


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
    if not texto.lstrip().lower().startswith(MARCAS):
        return 0
    raiz = (git(["rev-parse", "--show-toplevel"], datos.get("cwd") or ".") or "").strip()
    if not raiz:
        return 0
    rutas = rutas_sucias(raiz)
    if not rutas or not rutas_fuera_de_docs(rutas):
        return 0
    hoy = datetime.date.today().isoformat()
    rama = (git(["branch", "--show-current"], raiz) or "").strip()
    if hay_entrada(raiz, rama, hoy):
        return 0
    patron = patron_de_entrada(rama, hoy)
    print(
        f"Antes de cerrar falta la entrada de bitácora de hoy (docs/bitacora/{patron}). "
        "Delega en el documentador, que la crea con docs/bitacora/PLANTILLA.md: "
        "sin horas de trabajo ni datos personales.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
