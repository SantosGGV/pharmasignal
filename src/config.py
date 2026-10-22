"""
config.py

Carga config.toml y expone sus valores como constantes con el prefijo de su
sección: [senal] prr_min -> SENAL_PRR_MIN. Solo usa la biblioteca estándar,
para que funcione igual en el pipeline, en la interfaz, en Docker y en el CI.

La base del proyecto es la raíz del repositorio. Si se define la variable de
entorno PHARMASIGNAL_BASE, se usa esa en su lugar.
"""

import os
import tomllib
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[1]

with open(RAIZ_REPO / "config.toml", "rb") as f:
    _cfg = tomllib.load(f)

BASE = Path(os.environ.get("PHARMASIGNAL_BASE", RAIZ_REPO)).expanduser()

# Rutas absolutas, como texto, porque los scripts las componen con f-strings.
RUTAS_RAW = str(BASE / _cfg["rutas"]["raw"])
RUTAS_CURATED = str(BASE / _cfg["rutas"]["curated"])
RUTAS_DICCIONARIOS = str(BASE / _cfg["rutas"]["diccionarios"])
RUTAS_OUTPUTS = str(BASE / _cfg["rutas"]["outputs"])
RUTAS_LOGS = str(BASE / _cfg["rutas"]["logs"])

SENAL_PRR_MIN = _cfg["senal"]["prr_min"]
SENAL_CASOS_MIN = _cfg["senal"]["casos_min"]
SENAL_CHI2_MIN = _cfg["senal"]["chi2_min"]
SENAL_ROR_IC_INF_UMBRAL = _cfg["senal"]["ror_ic_inf_umbral"]

INTERFAZ_MIN_CASOS_RESPALDO = _cfg["interfaz"]["min_casos_respaldo"]

LISTADOS_TRIVIAL_MIN_C = _cfg["listados"]["trivial_min_c"]
LISTADOS_TRIVIAL_MIN_REPORTES_FARMACO = _cfg["listados"]["trivial_min_reportes_farmaco"]

GEOGRAFIA_MIN_CASOS_ES = _cfg["geografia"]["min_casos_es"]
GEOGRAFIA_MIN_CASOS_GLOBAL = _cfg["geografia"]["min_casos_global"]
GEOGRAFIA_MIN_CASOS_DIVERGENCIA = _cfg["geografia"]["min_casos_divergencia"]
GEOGRAFIA_MIN_GLOBAL_DIVERGENCIA = _cfg["geografia"]["min_global_divergencia"]
GEOGRAFIA_MIN_REPORTES_PAIS = _cfg["geografia"]["min_reportes_pais"]
GEOGRAFIA_ULTIMO_TRIMESTRE_ES = _cfg["geografia"]["ultimo_trimestre_es"]
GEOGRAFIA_TRIMESTRES_RECODIFICADOS = _cfg["geografia"]["trimestres_recodificados"]

EXPLORADOR_MIN_REPORTES_FARMACO = _cfg["explorador"]["min_reportes_farmaco"]
EXPLORADOR_MIN_CASOS_REACCION = _cfg["explorador"]["min_casos_reaccion"]
EXPLORADOR_MIN_REPORTES_PAIS = _cfg["explorador"]["min_reportes_pais"]

LANZADOR_CANDADO = str(Path(_cfg["lanzador"]["candado"]).expanduser())
LANZADOR_ESPACIO_MIN_GB = _cfg["lanzador"]["espacio_min_gb"]
LANZADOR_ESPERA_TERMINAR_S = _cfg["lanzador"]["espera_terminar_s"]
LANZADOR_DISCOS_EXTRA = _cfg["lanzador"]["discos_extra"]


def _ruta(clave):
    """Ruta absoluta de una clave de [rutas]; falla con un mensaje claro si no existe."""
    if clave not in _cfg["rutas"]:
        raise KeyError(f"config.toml: la clave «{clave}» no está en [rutas]")
    return str(BASE / _cfg["rutas"][clave])


# Fases del lanzador con los scripts y las rutas ya resueltos a absolutos.
LANZADOR_FASES = [
    {
        "nombre": f["nombre"],
        "scripts": [str(RAIZ_REPO / s) for s in f["scripts"]],
        "entrada": [_ruta(c) for c in f["entrada"]],
        "salida": [_ruta(c) for c in f["salida"]],
        "escribe_tablas": f["escribe_tablas"],
    }
    for f in _cfg["lanzador"]["fases"]
]
LANZADOR_FUERA = [
    {"script": str(RAIZ_REPO / f["script"]), "motivo": f["motivo"]}
    for f in _cfg["lanzador"].get("fuera", [])
]
