"""
test_capas.py

Pruebas de la separación por capas (tarea 0.11): data/bronce, data/plata y
data/oro, cómo las encadenan las fases del lanzador y qué capa usa cada script.

Ninguna lanza Spark ni lee tablas Delta, así que valen en el CI.

Ejecución:  pytest tests/ -q
"""

import os
import re
import subprocess
import tarfile
from pathlib import Path

import pytest

from src import config, lanzador

CAPAS = {
    "bronce": config.RUTAS_BRONCE,
    "plata": config.RUTAS_PLATA,
    "oro": config.RUTAS_ORO,
}


# --- Configuración ----------------------------------------------------------

def test_capas_absolutas_bajo_la_base_y_distintas():
    rutas = [Path(r) for r in CAPAS.values()]
    raw = Path(config.RUTAS_RAW)
    assert len(set(rutas)) == 3
    for r in rutas:
        assert r.is_absolute()
        assert r.is_relative_to(config.BASE)
        assert not (r.is_relative_to(raw) or raw.is_relative_to(r))
        for otra in rutas:
            if otra != r:
                assert not r.is_relative_to(otra), f"{r} está dentro de {otra}"


def test_fases_escriben_cada_una_en_su_capa():
    esperado = {
        "ingesta": ([config.RUTAS_RAW], [config.RUTAS_BRONCE]),
        "curacion": ([config.RUTAS_BRONCE], [config.RUTAS_PLATA]),
        "validacion": ([config.RUTAS_PLATA], []),
        "analisis": ([config.RUTAS_PLATA], [config.RUTAS_ORO]),
        "control": ([config.RUTAS_ORO], [config.RUTAS_OUTPUTS]),
    }
    for fase in config.LANZADOR_FASES:
        assert (fase["entrada"], fase["salida"]) == esperado[fase["nombre"]], fase["nombre"]


def test_cada_fase_lee_lo_que_escribio_una_anterior():
    # Se relanza desde cualquier fase porque su entrada la deja una fase previa
    # (o es data/raw, que no escribe nadie).
    escritas = {config.RUTAS_RAW}
    for fase in config.LANZADOR_FASES:
        for ruta in fase["entrada"]:
            assert ruta in escritas, f"{fase['nombre']} lee {ruta}, que no escribe ninguna fase anterior"
        escritas.update(fase["salida"])


def test_desde_cada_fase_la_primera_entrada_es_su_capa():
    entradas = {"curacion": config.RUTAS_BRONCE, "validacion": config.RUTAS_PLATA,
                "analisis": config.RUTAS_PLATA, "control": config.RUTAS_ORO}
    for nombre, capa in entradas.items():
        plan = lanzador.seleccionar(config.LANZADOR_FASES, desde=nombre)
        assert plan[0]["entrada"] == [capa]


# --- Qué capa usa cada script -----------------------------------------------

def _fuentes(carpeta):
    return sorted((config.RAIZ_REPO / "src" / carpeta).glob("*.py"))


def test_nadie_usa_la_carpeta_vieja():
    # data/curated se retiró en la 0.9: ni clave en config.toml ni RUTAS_CURATED.
    assert not hasattr(config, "RUTAS_CURATED")
    assert "curated" not in config._cfg["rutas"]
    for carpeta in ("src", "scripts", "docker", ".github"):
        for ruta in sorted((config.RAIZ_REPO / carpeta).rglob("*")):
            if ruta.is_file() and ruta.suffix in {".py", ".sh", ".yml", ".yaml", ""}:
                texto = ruta.read_text(encoding="utf-8", errors="replace")
                assert "RUTAS_CURATED" not in texto and "data/curated" not in texto, ruta


def test_cada_carpeta_de_src_usa_sus_capas():
    # ingesta escribe bronce; curación lee bronce y escribe plata; análisis lee
    # plata y escribe oro. Ningún script de análisis toca bronce.
    capas_por_carpeta = {
        "ingesta": {"RUTAS_BRONCE"},
        "curacion": {"RUTAS_BRONCE", "RUTAS_PLATA"},
        "analisis": {"RUTAS_PLATA", "RUTAS_ORO"},
        "app": {"RUTAS_PLATA", "RUTAS_ORO"},
    }
    todas = {"RUTAS_BRONCE", "RUTAS_PLATA", "RUTAS_ORO"}
    for carpeta, permitidas in capas_por_carpeta.items():
        for ruta in _fuentes(carpeta):
            texto = ruta.read_text(encoding="utf-8")
            usadas = {c for c in todas if c in texto}
            assert usadas <= permitidas, f"{ruta.name} usa {usadas - permitidas}"


def test_scripts_del_lanzador_usan_alguna_capa():
    for fase in config.LANZADOR_FASES:
        for s in fase["scripts"]:
            texto = Path(s).read_text(encoding="utf-8")
            assert any(c in texto for c in ("RUTAS_BRONCE", "RUTAS_PLATA", "RUTAS_ORO")), s


# --- Tablas de oro que lee la interfaz ----------------------------------------

# Las 24 tablas de data/oro (0.11). La lista vivía en migrar_capas.REPARTO, que
# se retiró en la 0.9 junto con data/curated.
TABLAS_ORO = {
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
}


def test_tablas_oro_son_24():
    assert len(TABLAS_ORO) == 24


def test_la_interfaz_y_la_demo_leen_de_oro_salvo_trad_terminos():
    oro = TABLAS_ORO
    app = config.RAIZ_REPO / "src" / "app"
    leidas = set()
    for ruta in app.glob("*.py"):
        leidas |= set(re.findall(r'(?:cargar|_leer)\("(\w+)"', ruta.read_text(encoding="utf-8")))
    demo = (config.RAIZ_REPO / "docker" / "preparar_demo.sh").read_text(encoding="utf-8")
    bloque = re.search(r"TABLAS=\((.*?)\n\)", demo, re.S).group(1)
    en_demo = {linea.split("#")[0].strip() for linea in bloque.splitlines()} - {""}
    assert leidas and en_demo
    assert leidas <= en_demo
    assert en_demo - {"trad_terminos"} <= oro
    assert len(en_demo) == 24


# --- Paquete de la demo -------------------------------------------------------

def _tablas_demo():
    texto = (config.RAIZ_REPO / "docker" / "preparar_demo.sh").read_text(encoding="utf-8")
    bloque = re.search(r"TABLAS=\((.*?)\n\)", texto, re.S).group(1)
    return [t for t in (linea.split("#")[0].strip() for linea in bloque.splitlines()) if t]


def _base_demo(tmp_path):
    """Base falsa con tablas Delta pequeñas; senales_prr_ror con una versión antigua."""
    deltalake = pytest.importorskip("deltalake")
    pd = pytest.importorskip("pandas")
    base = tmp_path / "base"
    for tabla in _tablas_demo():
        capa = "plata" if tabla == "trad_terminos" else "oro"
        ruta = str(base / "data" / capa / tabla)
        deltalake.write_deltalake(ruta, pd.DataFrame({"x": [1, 2, 3]}), mode="overwrite")
    deltalake.write_deltalake(str(base / "data" / "oro" / "senales_prr_ror"),
                              pd.DataFrame({"x": [1, 2, 3, 4]}), mode="overwrite")
    (base / "data" / "diccionarios").mkdir(parents=True)
    for nombre in ("paises.txt", "terminos_es.txt"):
        (base / "data" / "diccionarios" / nombre).write_text("en|es\n")
    return base


def _preparar_demo(base, salida):
    entorno = dict(os.environ, PHARMASIGNAL_BASE=str(base))
    return subprocess.run(["bash", str(config.RAIZ_REPO / "docker" / "preparar_demo.sh"), str(salida)],
                          capture_output=True, text=True, env=entorno, timeout=120)


def test_la_demo_no_lleva_geo_senales_espana():
    # Retirada de la interfaz por método: no se publica.
    assert "geo_senales_espana" not in _tablas_demo()
    assert len(_tablas_demo()) == 24


def test_preparar_demo_empaqueta_por_capas_solo_la_version_vigente(tmp_path):
    base = _base_demo(tmp_path)
    salida = tmp_path / "demo.tar.gz"
    r = _preparar_demo(base, salida)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Tablas comprobadas: 24; con problemas: 0" in r.stdout
    with tarfile.open(salida) as tar:
        miembros = tar.getmembers()
    nombres = [m.name for m in miembros]
    # Paquete público: rutas relativas y sin dueño local.
    for m in miembros:
        assert not m.name.startswith("/") and ".." not in m.name.split("/"), m.name
        assert (m.uid, m.gid, m.uname, m.gname) == (0, 0, "", ""), m.name
        assert not (m.issym() or m.islnk()), m.name
    permitidos = ("data/oro/", "data/plata/trad_terminos/", "data/diccionarios/")
    assert all(n.startswith(permitidos) for n in nombres), nombres
    assert "data/diccionarios/paises.txt" in nombres
    tablas = {"/".join(n.split("/")[:3]) for n in nombres if not n.startswith("data/diccionarios/")}
    assert len(tablas) == 24
    assert "data/plata/trad_terminos" in tablas
    # De senales_prr_ror solo va el parquet de la versión vigente, no el antiguo.
    en_base = list((base / "data" / "oro" / "senales_prr_ror").glob("*.parquet"))
    en_paquete = [n for n in nombres if n.startswith("data/oro/senales_prr_ror/") and n.endswith(".parquet")]
    assert len(en_base) == 2 and len(en_paquete) == 1


def test_preparar_demo_sin_una_tabla_sale_con_1(tmp_path):
    base = _base_demo(tmp_path)
    tabla = base / "data" / "oro" / "senales_prr_ror"
    tabla.rename(tmp_path / "apartada")
    salida = tmp_path / "demo.tar.gz"
    r = _preparar_demo(base, salida)
    assert r.returncode == 1
    assert "falta la tabla" in r.stdout
    assert not salida.exists()


def test_preparar_demo_borra_el_paquete_si_no_cuadra(tmp_path):
    # Un parquet vigente que no se puede leer: la comprobación final lo detecta.
    base = _base_demo(tmp_path)
    for f in (base / "data" / "oro" / "geo_perfil_renta").glob("*.parquet"):
        f.write_bytes(b"no es parquet")
    salida = tmp_path / "demo.tar.gz"
    r = _preparar_demo(base, salida)
    assert r.returncode != 0
    assert not salida.exists()
