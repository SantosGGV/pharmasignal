"""
migrar_capas.py

Traslado de un solo uso (tarea 0.11): mueve las 40 tablas de data/curated a su
capa (data/bronce, data/plata y data/oro), o las devuelve con --revertir.

Uso, desde la raíz del repositorio:
    python src/migrar_capas.py                         enseña los movimientos, no mueve nada
    python src/migrar_capas.py --confirmar             mueve las tablas a su capa
    python src/migrar_capas.py --revertir              enseña la vuelta a data/curated
    python src/migrar_capas.py --revertir --confirmar  devuelve las tablas a data/curated

Garantías:
- Coge el mismo candado que el lanzador: no hace nada si hay una fase en marcha.
- Primero lo comprueba todo y después mueve. Si una tabla está en origen y
  destino, falta en los dos o aparece algo fuera del reparto, no mueve ninguna.
- Nunca pisa, copia ni borra: os.rename dentro del mismo disco, tabla a tabla.
  Si se corta a medias, al relanzarlo sigue donde se quedó.
- _tmp_expl_cruce (temporal de analisis_explorador_cruces.py) nunca se mueve.

Códigos de salida: 0 si todo va bien o no hay nada que mover; 2 por error de
uso, conflicto, tabla que falta o desconocida, otro disco o candado inseguro;
75 si el candado está ocupado; 130 si se interrumpe.
"""

import argparse
import os
import sys
from pathlib import Path

# Raíz del repositorio en el sys.path para importar la configuración común.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config
from src.lanzador import (SALIDA_INTERRUMPIDO, SALIDA_OCUPADO, SALIDA_USO,
                          CandadoInseguro, anotar_candado, coger_candado)

# Reparto de las tablas de data/curated en capas. Describe la estructura vieja,
# por eso vive aquí y no en config.toml.
REPARTO = {
    "bronce": ["demo", "drug", "reac", "outc", "indi", "ther", "rpsr"],
    "plata": ["demo_curado", "drug_curado", "reac_curado", "outc_curado", "indi_curado",
              "ther_curado", "rpsr_curado", "demo_geo", "trad_terminos"],
    "oro": [
        "senales_prr_ror",
        "serie_temporal_familias", "serie_temporal_glp1_farmacos",
        "geo_perfil_paises", "geo_divergencia_farmacos", "geo_divergencia_reacciones",
        "geo_senales_espana", "geo_perfil_renta", "geo_glp1_paises", "geo_evolucion_espana",
        "expl_catalogo_farmacos", "expl_catalogo_reacciones",
        "expl_farmaco_trimestre", "expl_farmaco_pais", "expl_farmaco_indicacion",
        "expl_farmaco_gravedad", "expl_reaccion_trimestre", "expl_reaccion_pais",
        "expl_farmaco_reaccion_trimestre", "expl_farmaco_reaccion_pais",
        "expl_reaccion_farmaco_trimestre", "expl_reaccion_farmaco_pais",
        "expl_farmaco_indicacion_trimestre", "expl_farmaco_gravedad_trimestre",
    ],
}
# Temporales que se avisan pero nunca se mueven.
TEMPORALES = {"_tmp_expl_cruce"}
# Ficheros que pueden estar en una carpeta de datos sin ser tablas.
FICHEROS_PERMITIDOS = {".gitkeep"}


def rutas_por_defecto():
    return {"curated": config.RUTAS_CURATED, "bronce": config.RUTAS_BRONCE,
            "plata": config.RUTAS_PLATA, "oro": config.RUTAS_ORO}


def movimientos(rutas, revertir):
    """Lista de (tabla, origen, destino) de las 40 tablas, en el sentido pedido."""
    movs = []
    for capa, tablas in REPARTO.items():
        for tabla in tablas:
            en_capa = Path(rutas[capa]) / tabla
            en_curated = Path(rutas["curated"]) / tabla
            movs.append((tabla, en_capa, en_curated) if revertir else (tabla, en_curated, en_capa))
    return movs


def esperadas_por_origen(rutas, revertir):
    """Qué tablas puede haber en cada carpeta de origen."""
    if revertir:
        return {Path(rutas[capa]): set(tablas) for capa, tablas in REPARTO.items()}
    return {Path(rutas["curated"]): {t for tablas in REPARTO.values() for t in tablas}}


def revisar_origenes(esperadas):
    """Devuelve (desconocidos, temporales) que hay en las carpetas de origen."""
    desconocidos, temporales = [], []
    for carpeta, tablas in esperadas.items():
        if not carpeta.is_dir():
            continue
        for entrada in sorted(carpeta.iterdir()):
            if entrada.name in TEMPORALES:
                temporales.append(entrada)
            elif entrada.is_dir() and not entrada.is_symlink() and entrada.name in tablas:
                continue
            elif entrada.is_file() and entrada.name in FICHEROS_PERMITIDOS:
                continue
            else:
                desconocidos.append(entrada)
    return desconocidos, temporales


def clasificar(movs):
    """Separa los movimientos en pendientes, hechos, conflictos y que faltan."""
    pendientes, hechos, conflictos, faltan = [], [], [], []
    for mov in movs:
        _, origen, destino = mov
        hay_origen, hay_destino = os.path.lexists(origen), os.path.lexists(destino)
        if hay_origen and hay_destino:
            conflictos.append(mov)
        elif hay_origen:
            pendientes.append(mov)
        elif hay_destino:
            hechos.append(mov)
        else:
            faltan.append(mov)
    return pendientes, hechos, conflictos, faltan


def _dispositivo(ruta):
    """Disco de una ruta, o del primer antecesor que exista si aún no existe."""
    ruta = Path(ruta)
    while not ruta.exists():
        ruta = ruta.parent
    return os.stat(ruta).st_dev


def otro_disco(pendientes):
    """Movimientos cuyo origen y destino están en discos distintos."""
    return [m for m in pendientes if _dispositivo(m[1]) != _dispositivo(m[2].parent)]


def _rel(ruta, base):
    try:
        return str(Path(ruta).relative_to(base))
    except ValueError:
        return str(ruta)


def main(argv=None, *, rutas=None, candado=None, base=None):
    """Punto de entrada. Los parámetros con nombre solo los usan las pruebas."""
    rutas = rutas_por_defecto() if rutas is None else rutas
    candado = config.LANZADOR_CANDADO if candado is None else candado
    base = config.BASE if base is None else base

    parser = argparse.ArgumentParser(
        prog="python src/migrar_capas.py",
        description="Mueve las tablas de data/curated a sus capas, o las devuelve.",
    )
    parser.add_argument("--confirmar", action="store_true", help="mueve de verdad")
    parser.add_argument("--revertir", action="store_true",
                        help="devuelve las tablas de las capas a data/curated")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return SALIDA_USO if e.code else 0

    try:
        fd, quien = coger_candado(candado)
    except CandadoInseguro as e:
        print(f"Error: candado inseguro: {e}", file=sys.stderr)
        return SALIDA_USO
    if fd is None:
        print(f"Hay un lanzamiento en curso ({quien}). Espera a que termine.", file=sys.stderr)
        return SALIDA_OCUPADO
    try:
        anotar_candado(fd, f"pid={os.getpid()} migrar_capas")
        return _migrar(args, rutas, base)
    except KeyboardInterrupt:
        print("\nInterrumpido. Relánzalo para seguir donde se quedó.", file=sys.stderr)
        return SALIDA_INTERRUMPIDO
    finally:
        os.close(fd)


def _migrar(args, rutas, base):
    sentido = "de las capas a data/curated" if args.revertir else "de data/curated a las capas"
    print(f"Base: {base}")
    print(f"Traslado {sentido}.")
    if args.revertir:
        print("Aviso: la estructura vieja solo encaja con el código anterior a la 0.11. "
              "Revierte también el código.")

    movs = movimientos(rutas, args.revertir)
    desconocidos, temporales = revisar_origenes(esperadas_por_origen(rutas, args.revertir))
    pendientes, hechos, conflictos, faltan = clasificar(movs)
    lejos = otro_disco(pendientes)

    for t in temporales:
        print(f"Aviso: {_rel(t, base)} se deja donde está; la borra y la rehace el propio "
              "script en su próxima ejecución, o la borras tú.")

    errores = []
    errores += [f"fuera del reparto: {_rel(d, base)}" for d in desconocidos]
    errores += [f"{t} está en origen y destino; no se pisa: {_rel(o, base)} y {_rel(d, base)}"
                for t, o, d in conflictos]
    errores += [f"{t} no está ni en {_rel(o, base)} ni en {_rel(d, base)}" for t, o, d in faltan]
    errores += [f"{t}: origen y destino en discos distintos; no se copia" for t, _, _ in lejos]
    if errores:
        for error in errores:
            print(f"Error: {error}", file=sys.stderr)
        print("No se ha movido nada.", file=sys.stderr)
        return SALIDA_USO

    if hechos:
        print(f"Ya movidas: {len(hechos)}.")
    if not pendientes:
        print("Nada que mover.")
        return 0

    print(f"Por mover: {len(pendientes)}.")
    if not args.confirmar:
        for _, origen, destino in pendientes:
            print(f"   {_rel(origen, base)} → {_rel(destino, base)}")
        orden = "--revertir --confirmar" if args.revertir else "--confirmar"
        print(f"No se ha movido nada. Para mover: python src/migrar_capas.py {orden}")
        return 0

    for _, origen, destino in pendientes:
        destino.parent.mkdir(parents=True, exist_ok=True)
        # os.rename pisaría un directorio vacío: se vuelve a mirar justo antes.
        if os.path.lexists(destino):
            print(f"Error: {_rel(destino, base)} ha aparecido durante el traslado; "
                  "se para aquí.", file=sys.stderr)
            return SALIDA_USO
        os.rename(origen, destino)
        print(f"   {_rel(origen, base)} → {_rel(destino, base)}", flush=True)
    print(f"Movidas: {len(pendientes)}. Las carpetas vacías no se borran.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
