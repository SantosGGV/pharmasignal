"""Comprueba que lo instalado coincide con uno o varios ficheros de bloqueo.

Un fichero de bloqueo (requirements.txt, requirements-interfaz.txt…) lleva un
paquete por línea con su versión exacta (`nombre==versión`). Este script lee lo
que hay instalado en el intérprete que lo ejecuta (con importlib.metadata, sin
lanzar pip) y avisa de tres cosas:
- paquetes del bloqueo que faltan;
- paquetes instalados con otra versión;
- paquetes instalados que no están en el bloqueo (sobrantes), salvo pip.

Es lo que da sentido al «hecho cuando» de la 0.7: una instalación limpia da
las mismas versiones. Se ejecuta en el CI en un entorno recién creado y dentro
de la imagen Docker.

Uso:
    python scripts/deps/comprobar_bloqueo.py requirements.txt
    python scripts/deps/comprobar_bloqueo.py --permitir-sobrantes requirements.txt
Código de salida: 0 si coincide, 1 si no, 2 si un fichero de bloqueo es inválido.
"""
import argparse
import re
import sys
from importlib import metadata
from pathlib import Path

# Lo que trae cualquier entorno virtual y no forma parte del proyecto.
IGNORADOS = {"pip"}

_LINEA = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9.+!_-]+)$")


def normalizar(nombre):
    """Nombre canónico de un paquete (PEP 503): delta_spark == Delta-Spark."""
    return re.sub(r"[-_.]+", "-", nombre).lower()


def leer_bloqueo(ruta):
    """Devuelve {nombre_normalizado: versión} de un fichero de bloqueo.

    Ignora líneas vacías y comentarios. Cualquier otra línea tiene que ser
    `nombre==versión`; si no, lanza ValueError con fichero y número de línea.
    """
    paquetes = {}
    texto = Path(ruta).read_text(encoding="utf-8")
    for num, linea in enumerate(texto.splitlines(), start=1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        m = _LINEA.match(linea)
        if not m:
            raise ValueError(f"{ruta}:{num}: se esperaba «nombre==versión»")
        nombre = normalizar(m.group(1))
        if nombre in paquetes and paquetes[nombre] != m.group(2):
            raise ValueError(f"{ruta}:{num}: {nombre} aparece con dos versiones")
        paquetes[nombre] = m.group(2)
    return paquetes


def instalados():
    """Devuelve {nombre_normalizado: versión} de lo instalado en este intérprete."""
    return {normalizar(d.metadata["Name"]): d.version
            for d in metadata.distributions()}


def comparar(bloqueo, presentes, permitir_sobrantes=False):
    """Compara el bloqueo con lo instalado.

    Devuelve (faltan, distintos, sobrantes): listas ordenadas; `distintos` son
    tuplas (nombre, versión del bloqueo, versión instalada).
    """
    faltan = sorted(n for n in bloqueo if n not in presentes)
    distintos = sorted((n, bloqueo[n], presentes[n])
                       for n in bloqueo
                       if n in presentes and presentes[n] != bloqueo[n])
    sobrantes = [] if permitir_sobrantes else sorted(
        n for n in presentes if n not in bloqueo and n not in IGNORADOS)
    return faltan, distintos, sobrantes


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Comprueba que lo instalado coincide con los bloqueos.")
    p.add_argument("bloqueos", nargs="+", help="ficheros de bloqueo")
    p.add_argument("--permitir-sobrantes", action="store_true",
                   help="no falla por paquetes instalados fuera del bloqueo")
    args = p.parse_args(argv)

    bloqueo = {}
    try:
        for ruta in args.bloqueos:
            for nombre, version in leer_bloqueo(ruta).items():
                if bloqueo.get(nombre, version) != version:
                    raise ValueError(f"{ruta}: {nombre} choca con otro bloqueo")
                bloqueo[nombre] = version
    except (OSError, ValueError) as e:
        print(f"Bloqueo inválido: {e}", file=sys.stderr)
        return 2

    faltan, distintos, sobrantes = comparar(bloqueo, instalados(),
                                            args.permitir_sobrantes)
    for n in faltan:
        print(f"falta      {n}=={bloqueo[n]}")
    for n, esperada, real in distintos:
        print(f"distinta   {n}: bloqueo {esperada}, instalada {real}")
    for n in sobrantes:
        print(f"sobrante   {n}")
    if faltan or distintos or sobrantes:
        print(f"\nNo coincide: {len(faltan)} faltan, {len(distintos)} con otra "
              f"versión y {len(sobrantes)} sobrantes.")
        return 1
    print(f"Coincide: {len(bloqueo)} paquetes con la versión del bloqueo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
