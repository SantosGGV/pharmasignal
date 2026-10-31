#!/usr/bin/env python3
"""Hook Stop: guarda el Cierre de una tarea o de una sesión en $PHARMASIGNAL_PRIVADO/cierres/.

Solo actúa si el último mensaje de Claude empieza por «## Cierre de la tarea»
o «## Cierre de la sesión». Lo guarda tal cual, listo para pegarlo en el chat:
AAAA-MM-DD_<id>-<nombre>.md en una rama de tarea y AAAA-MM-DD_sesion-<rama>.md
en cualquier otra. Un Cierre repetido en la misma sesión (por ejemplo, tras el
bloqueo de exigir_bitacora.py) pisa al anterior; otra sesión el mismo día
añade _2, _3... Nunca bloquea: sale siempre con 0.
"""
import datetime
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from exigir_bitacora import git, texto_de, ultimo_texto_de_la_transcripcion  # noqa: E402
from rastro_sesion import carpeta, carpeta_privada, escribir, guardar_estado, leer_estado, limpio  # noqa: E402

INICIOS = ("## cierre de la tarea", "## cierre de la sesión")
RAMA_DE_TAREA = re.compile(r"^fase\d+/(\d+\.\d+-.+)$")


def nombre_base(rama, hoy):
    tarea = RAMA_DE_TAREA.match(rama or "")
    return f"{hoy}_{limpio(tarea.group(1))}" if tarea else f"{hoy}_sesion-{limpio(rama) or 'sin-rama'}"


def destino(cierres, base, estado):
    """El fichero de esta sesión si ya tiene uno; si no, el primer nombre libre."""
    propio = (estado or {}).get("cierre")
    if propio and propio.startswith(base) and pathlib.Path(propio).name == propio:
        return cierres / propio
    candidato, numero = cierres / f"{base}.md", 2
    while candidato.exists():
        candidato, numero = cierres / f"{base}_{numero}.md", numero + 1
    return candidato


def main():
    try:
        datos = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(datos, dict):
        return 0
    texto = texto_de(datos.get("last_assistant_message"))
    if not texto.strip():
        texto = ultimo_texto_de_la_transcripcion(datos.get("transcript_path"))
    texto = texto.lstrip()
    if not texto.lower().startswith(INICIOS):
        return 0
    raiz = (git(["rev-parse", "--show-toplevel"], datos.get("cwd") or ".") or "").strip()
    privada = carpeta_privada(raiz)
    if privada is None:
        return 0
    rama = (git(["branch", "--show-current"], raiz) or "").strip() if raiz else ""
    sid = limpio(str(datos.get("session_id") or ""), 8) or "sin-id"
    try:
        cierres = carpeta(privada / "cierres")
        estado = leer_estado(privada, sid)
        fichero = destino(cierres, nombre_base(rama, datetime.date.today().isoformat()), estado)
        escribir(fichero, texto if texto.endswith("\n") else texto + "\n")
        if estado is not None:
            estado["cierre"] = fichero.name
            guardar_estado(privada, sid, estado)
        print(f"Cierre guardado en {fichero}")
    except OSError as error:
        print(f"Aviso: no se pudo guardar el Cierre ({error.strerror}).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
