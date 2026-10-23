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

from src import config, lanzador, migrar_capas

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


def test_solo_migrar_capas_usa_la_carpeta_vieja():
    permitidos = {"config.py", "migrar_capas.py"}
    for ruta in sorted((config.RAIZ_REPO / "src").rglob("*.py")):
        if ruta.name not in permitidos:
            assert "RUTAS_CURATED" not in ruta.read_text(encoding="utf-8"), ruta


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


# --- Reparto de migrar_capas -------------------------------------------------

TABLAS = [t for tablas in migrar_capas.REPARTO.values() for t in tablas]


def test_reparto_7_9_24_sin_repetidas():
    assert [len(migrar_capas.REPARTO[c]) for c in ("bronce", "plata", "oro")] == [7, 9, 24]
    assert len(set(TABLAS)) == 40
    assert "trad_terminos" in migrar_capas.REPARTO["plata"]


def test_la_interfaz_y_la_demo_leen_de_oro_salvo_trad_terminos():
    oro = set(migrar_capas.REPARTO["oro"])
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


# --- migrar_capas sobre una base falsa ---------------------------------------

@pytest.fixture
def base_falsa(tmp_path):
    """data/curated con las 40 tablas falsas (un _delta_log y un fichero de control)."""
    rutas = {c: str(tmp_path / "data" / c) for c in ("curated", "bronce", "plata", "oro")}
    curated = Path(rutas["curated"])
    for tabla in TABLAS:
        (curated / tabla / "_delta_log").mkdir(parents=True)
        (curated / tabla / "control.txt").write_text(tabla)
    (curated / ".gitkeep").write_text("")
    opciones = dict(rutas=rutas, candado=str(tmp_path / "cache" / "pipeline.lock"), base=tmp_path)
    return rutas, opciones


def _arbol(raiz):
    """Instantánea de carpetas y ficheros, sin la carpeta del candado de prueba."""
    return sorted((str(Path(d).relative_to(raiz)), sorted(fs)) for d, _, fs in os.walk(raiz)
                  if Path(d).relative_to(raiz).parts[:1] != ("cache",))


def _cuantas(ruta):
    p = Path(ruta)
    return len([e for e in p.iterdir() if e.is_dir()]) if p.is_dir() else 0


def _migrar(opciones, *argv):
    return migrar_capas.main(list(argv), **opciones)


def test_sin_confirmar_solo_enseña_la_lista(base_falsa, capsys):
    rutas, opciones = base_falsa
    antes = _arbol(opciones["base"])
    assert _migrar(opciones) == 0
    assert _arbol(opciones["base"]) == antes
    salida = capsys.readouterr().out
    assert "Por mover: 40." in salida
    assert "data/curated/demo → data/bronce/demo" in salida
    assert "No se ha movido nada" in salida


def test_confirmar_mueve_las_40_a_su_capa(base_falsa):
    rutas, opciones = base_falsa
    assert _migrar(opciones, "--confirmar") == 0
    assert [_cuantas(rutas[c]) for c in ("bronce", "plata", "oro")] == [7, 9, 24]
    assert [e.name for e in Path(rutas["curated"]).iterdir()] == [".gitkeep"]
    assert (Path(rutas["oro"]) / "senales_prr_ror" / "control.txt").read_text() == "senales_prr_ror"
    assert (Path(rutas["plata"]) / "trad_terminos" / "_delta_log").is_dir()


def test_relanzar_tras_completar_no_mueve_nada(base_falsa, capsys):
    rutas, opciones = base_falsa
    assert _migrar(opciones, "--confirmar") == 0
    antes = _arbol(opciones["base"])
    assert _migrar(opciones, "--confirmar") == 0
    assert _arbol(opciones["base"]) == antes
    assert "Nada que mover." in capsys.readouterr().out


def test_se_reanuda_donde_se_quedo(base_falsa, capsys):
    rutas, opciones = base_falsa
    for tabla in TABLAS[:10]:
        capa = next(c for c, ts in migrar_capas.REPARTO.items() if tabla in ts)
        Path(rutas[capa]).mkdir(parents=True, exist_ok=True)
        os.rename(Path(rutas["curated"]) / tabla, Path(rutas[capa]) / tabla)
    assert _migrar(opciones, "--confirmar") == 0
    salida = capsys.readouterr().out
    assert "Ya movidas: 10." in salida and "Por mover: 30." in salida
    assert [_cuantas(rutas[c]) for c in ("bronce", "plata", "oro")] == [7, 9, 24]


def test_conflicto_no_pisa_ni_mueve_nada(base_falsa):
    rutas, opciones = base_falsa
    destino = Path(rutas["oro"]) / "senales_prr_ror"
    destino.mkdir(parents=True)
    (destino / "otra.txt").write_text("no tocar")
    antes = _arbol(opciones["base"])
    assert _migrar(opciones, "--confirmar") == 2
    assert _arbol(opciones["base"]) == antes


def test_tabla_que_falta_no_mueve_nada(base_falsa):
    rutas, opciones = base_falsa
    (Path(rutas["curated"]) / "demo" / "control.txt").unlink()
    (Path(rutas["curated"]) / "demo" / "_delta_log").rmdir()
    (Path(rutas["curated"]) / "demo").rmdir()
    antes = _arbol(opciones["base"])
    assert _migrar(opciones, "--confirmar") == 2
    assert _arbol(opciones["base"]) == antes


@pytest.mark.parametrize("crear", [
    lambda c: (c / "tabla_nueva" / "_delta_log").mkdir(parents=True),
    lambda c: (c / "suelto.parquet").write_text("x"),
])
def test_algo_fuera_del_reparto_no_mueve_nada(base_falsa, crear, capsys):
    rutas, opciones = base_falsa
    crear(Path(rutas["curated"]))
    antes = _arbol(opciones["base"])
    assert _migrar(opciones, "--confirmar") == 2
    assert _arbol(opciones["base"]) == antes
    assert "fuera del reparto" in capsys.readouterr().err


def test_tmp_expl_cruce_se_avisa_y_no_se_mueve(base_falsa, capsys):
    rutas, opciones = base_falsa
    (Path(rutas["curated"]) / "_tmp_expl_cruce").mkdir()
    assert _migrar(opciones, "--confirmar") == 0
    assert (Path(rutas["curated"]) / "_tmp_expl_cruce").is_dir()
    assert not (Path(rutas["oro"]) / "_tmp_expl_cruce").exists()
    assert _cuantas(rutas["oro"]) == 24
    assert "_tmp_expl_cruce se deja donde está" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [[], ["--confirmar"], ["--revertir", "--confirmar"]])
def test_candado_ocupado_da_75_sin_mover_nada(base_falsa, argv):
    rutas, opciones = base_falsa
    fd, _ = lanzador.coger_candado(opciones["candado"])
    try:
        antes = _arbol(opciones["base"])
        assert _migrar(opciones, *argv) == 75
        assert _arbol(opciones["base"]) == antes
    finally:
        os.close(fd)


def test_otro_disco_no_mueve_nada(base_falsa, monkeypatch):
    rutas, opciones = base_falsa
    curated = rutas["curated"]
    monkeypatch.setattr(migrar_capas, "_dispositivo",
                        lambda ruta: 1 if str(ruta).startswith(curated) else 2)
    antes = _arbol(opciones["base"])
    assert _migrar(opciones, "--confirmar") == 2
    assert _arbol(opciones["base"]) == antes


def test_revertir_sin_confirmar_no_toca_nada(base_falsa, capsys):
    rutas, opciones = base_falsa
    assert _migrar(opciones, "--confirmar") == 0
    antes = _arbol(opciones["base"])
    capsys.readouterr()
    assert _migrar(opciones, "--revertir") == 0
    assert _arbol(opciones["base"]) == antes
    salida = capsys.readouterr().out
    assert "data/oro/senales_prr_ror → data/curated/senales_prr_ror" in salida
    assert "código anterior a la 0.11" in salida


def test_ida_y_vuelta_deja_el_arbol_igual_salvo_las_capas_vacias(base_falsa):
    rutas, opciones = base_falsa
    antes = _arbol(Path(rutas["curated"]))
    assert _migrar(opciones, "--confirmar") == 0
    assert _migrar(opciones, "--revertir", "--confirmar") == 0
    assert _arbol(Path(rutas["curated"])) == antes
    # Las capas quedan vacías pero no se borran.
    for c in ("bronce", "plata", "oro"):
        assert Path(rutas[c]).is_dir() and not any(Path(rutas[c]).iterdir())


def test_revertir_se_reanuda_y_no_pisa(base_falsa):
    rutas, opciones = base_falsa
    assert _migrar(opciones, "--confirmar") == 0
    os.rename(Path(rutas["bronce"]) / "demo", Path(rutas["curated"]) / "demo")
    assert _migrar(opciones, "--revertir", "--confirmar") == 0
    assert _cuantas(rutas["curated"]) == 40
    # Conflicto al revertir: una tabla en la capa y en data/curated.
    assert _migrar(opciones, "--confirmar") == 0
    (Path(rutas["curated"]) / "demo").mkdir()
    antes = _arbol(opciones["base"])
    assert _migrar(opciones, "--revertir", "--confirmar") == 2
    assert _arbol(opciones["base"]) == antes


def test_revertir_con_tabla_desconocida_en_oro_no_mueve_nada(base_falsa):
    rutas, opciones = base_falsa
    assert _migrar(opciones, "--confirmar") == 0
    (Path(rutas["oro"]) / "tabla_de_otra_tarea").mkdir()
    antes = _arbol(opciones["base"])
    assert _migrar(opciones, "--revertir", "--confirmar") == 2
    assert _arbol(opciones["base"]) == antes


def test_revertir_deja_tmp_expl_cruce_en_oro(base_falsa):
    rutas, opciones = base_falsa
    assert _migrar(opciones, "--confirmar") == 0
    (Path(rutas["oro"]) / "_tmp_expl_cruce").mkdir()
    assert _migrar(opciones, "--revertir", "--confirmar") == 0
    assert _cuantas(rutas["curated"]) == 40
    assert (Path(rutas["oro"]) / "_tmp_expl_cruce").is_dir()


def test_argumento_desconocido_da_2(base_falsa):
    _, opciones = base_falsa
    assert _migrar(opciones, "--mover") == 2


def test_migrar_capas_no_borra_ni_lanza_procesos():
    texto = (config.RAIZ_REPO / "src" / "migrar_capas.py").read_text(encoding="utf-8")
    for prohibido in ("subprocess", "rmtree", "shutil", "os.remove", "unlink", "rmdir"):
        assert prohibido not in texto, prohibido


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


def test_interrumpido_da_130_y_se_reanuda(base_falsa, monkeypatch):
    rutas, opciones = base_falsa
    real = os.rename
    movidas = []

    def rename_con_corte(origen, destino):
        if len(movidas) == 3:
            raise KeyboardInterrupt
        real(origen, destino)
        movidas.append(destino)

    monkeypatch.setattr(migrar_capas.os, "rename", rename_con_corte)
    assert _migrar(opciones, "--confirmar") == 130
    assert len(movidas) == 3
    monkeypatch.setattr(migrar_capas.os, "rename", real)
    # El candado se soltó y al relanzar termina el trabajo.
    assert _migrar(opciones, "--confirmar") == 0
    assert [_cuantas(rutas[c]) for c in ("bronce", "plata", "oro")] == [7, 9, 24]
