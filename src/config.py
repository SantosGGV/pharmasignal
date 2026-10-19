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
