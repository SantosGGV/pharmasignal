"""
test_criterio.py

docs/criterio.md es el único documento del criterio (tarea 0.8). Estas pruebas
fallan si su tabla de valores y config.toml dejan de coincidir, si README,
CLAUDE.md o el agente de método dejan de enlazarlo, o si vuelven a la interfaz
los nombres o a la geografía los umbrales escritos a mano que se retiraron.
"""

import re
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
DOCUMENTO = RAIZ / "docs" / "criterio.md"
SECCIONES = ("senal", "interfaz", "listados", "geografia", "explorador")
INICIO = "<!-- criterio:valores:inicio -->"
FIN = "<!-- criterio:valores:fin -->"
FILA = re.compile(r"^\|\s*`([a-z_0-9]+\.[a-z_0-9]+)`\s*\|\s*`([^`]+)`\s*\|")


def valores_del_documento(texto):
    """Devuelve {clave: valor} de la tabla y los errores de forma que encuentre."""
    tabla = texto.split(INICIO, 1)[1].split(FIN, 1)[0]
    valores, errores = {}, []
    # Las dos primeras filas de la tabla son la cabecera y el separador.
    for linea in [l for l in tabla.splitlines() if l.startswith("|")][2:]:
        fila = FILA.match(linea)
        if fila is None:
            errores.append(f"fila mal formada en el documento: {linea}")
            continue
        clave, valor = fila.groups()
        if clave in valores:
            errores.append(f"repetida en el documento: {clave}")
        # El valor se escribe en sintaxis TOML: así 2.0, "2025q2" y las listas
        # se comparan con su tipo y no como texto.
        valores[clave] = tomllib.loads(f"v = {valor}")["v"]
    return valores, errores


def valores_de_config(texto):
    """Aplana las secciones del criterio a {seccion.clave: valor}."""
    cfg = tomllib.loads(texto)
    return {f"{sec}.{clave}": valor
            for sec in SECCIONES for clave, valor in cfg[sec].items()}


def discrepancias(documento, config):
    """Lista legible de lo que no coincide entre el documento y config.toml."""
    doc, errores = valores_del_documento(documento)
    cfg = valores_de_config(config)
    errores += [f"falta en el documento: {c}" for c in cfg.keys() - doc.keys()]
    errores += [f"sobra en el documento: {c}" for c in doc.keys() - cfg.keys()]
    for clave in cfg.keys() & doc.keys():
        # type() distingue 2 de 2.0, que en Python se comparan como iguales.
        if doc[clave] != cfg[clave] or type(doc[clave]) is not type(cfg[clave]):
            errores.append(f"{clave}: documento {doc[clave]!r}, config {cfg[clave]!r}")
    return sorted(errores)


@pytest.fixture
def documento():
    return DOCUMENTO.read_text(encoding="utf-8")


@pytest.fixture
def config_toml():
    return (RAIZ / "config.toml").read_text(encoding="utf-8")


def test_documento_y_config_coinciden(documento, config_toml):
    assert discrepancias(documento, config_toml) == []


def test_la_tabla_cubre_las_cinco_secciones(documento):
    valores, _ = valores_del_documento(documento)
    assert {clave.split(".")[0] for clave in valores} == set(SECCIONES)


@pytest.mark.parametrize("original, alterado, clave", [
    ("prr_min = 2.0", "prr_min = 3.0", "senal.prr_min"),
    ("prr_min = 2.0", "prr_min = 2", "senal.prr_min"),
    ("min_casos_es = 5", "min_casos_es = 6", "geografia.min_casos_es"),
    ('ultimo_trimestre_es = "2025q2"', 'ultimo_trimestre_es = "2025q3"',
     "geografia.ultimo_trimestre_es"),
    ('trimestres_recodificados = ["2025q3", "2025q4"]',
     'trimestres_recodificados = ["2025q3"]',
     "geografia.trimestres_recodificados"),
])
def test_detecta_un_valor_cambiado_en_config(documento, config_toml, original,
                                             alterado, clave):
    assert original in config_toml
    errores = discrepancias(documento, config_toml.replace(original, alterado))
    assert len(errores) == 1 and errores[0].startswith(f"{clave}:")


def test_detecta_un_valor_cambiado_en_el_documento(documento, config_toml):
    fila = "| `senal.chi2_min` | `4.0` |"
    assert fila in documento
    errores = discrepancias(documento.replace(fila, "| `senal.chi2_min` | `5.0` |"),
                            config_toml)
    assert len(errores) == 1 and errores[0].startswith("senal.chi2_min:")


def test_detecta_una_clave_nueva_en_config(documento, config_toml):
    errores = discrepancias(documento,
                            config_toml.replace("[listados]", "[listados]\nnueva = 1"))
    assert errores == ["falta en el documento: listados.nueva"]


def test_detecta_una_fila_sobrante_y_una_repetida(documento, config_toml):
    extra = "| `senal.prr_min` | `2.0` | r | d |\n| `senal.vieja` | `1` | r | d |\n"
    errores = discrepancias(documento.replace(FIN, extra + FIN), config_toml)
    assert errores == ["repetida en el documento: senal.prr_min",
                       "sobra en el documento: senal.vieja"]


def test_detecta_una_fila_mal_formada(documento, config_toml):
    fila = "| senal.vieja | 1 | r | d |"
    errores = discrepancias(documento.replace(FIN, fila + "\n" + FIN), config_toml)
    assert errores == [f"fila mal formada en el documento: {fila}"]


@pytest.mark.parametrize("fichero, enlace", [
    ("README.md", "docs/criterio.md"),
    ("CLAUDE.md", "docs/criterio.md"),
    (".claude/agents/metodo.md", "docs/criterio.md"),
])
def test_los_demas_documentos_enlazan_al_criterio(fichero, enlace):
    assert enlace in (RAIZ / fichero).read_text(encoding="utf-8")


def test_la_senal_de_espana_lee_los_umbrales_de_config():
    fuente = (RAIZ / "src/analisis/analisis_geografico.py").read_text(encoding="utf-8")
    assert 'col("prr_es") >= lit(config.SENAL_PRR_MIN)' in fuente
    assert 'col("chi2_es") >= lit(config.SENAL_CHI2_MIN)' in fuente


def test_la_interfaz_no_llama_confirmadas_a_lo_que_no_lo_es():
    """«Confirmadas» es solo PRR y ROR a la vez, y la interfaz no muestra esa cifra."""
    fuente = (RAIZ / "src/app/streamlit_app.py").read_text(encoding="utf-8")
    assert not re.search(r"confirmad|confirmed", fuente, re.IGNORECASE)
