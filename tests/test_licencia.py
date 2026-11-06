"""
test_licencia.py

Pruebas de la licencia y de los avisos de terceros (tarea 0.10): LICENSE es el
texto oficial sin tocar, THIRD_PARTY_NOTICES.md coincide con los tres bloqueos, la
interfaz enlaza el código y la licencia antes de ejecutar la vista, y la imagen
Docker lleva los dos ficheros.

No usan red ni Spark.

Ejecución:  pytest tests/ -q
"""

import hashlib
import importlib.util
import re
import sys
from pathlib import Path

import pytest

from src import config

RAIZ = Path(__file__).resolve().parent.parent
# sha256 de https://www.gnu.org/licenses/agpl-3.0.txt, descargado el 2026-11-06.
SHA256_AGPL = "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0"

_spec = importlib.util.spec_from_file_location(
    "generar_avisos", RAIZ / "scripts" / "deps" / "generar_avisos.py")
avisos = importlib.util.module_from_spec(_spec)
sys.modules["generar_avisos"] = avisos
_spec.loader.exec_module(avisos)


def _notices():
    return (RAIZ / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")


def _filas(seccion):
    """Filas de datos (nombre, versión, licencia) de las tablas de un trozo de texto."""
    filas = []
    for linea in seccion.splitlines():
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if linea.startswith("|") and celdas[0] not in ("Paquete", "---"):
            filas.append(celdas)
    return filas


def _secciones():
    texto = _notices()
    python, resto = texto.split("## Entorno opcional de traducción")
    traduccion, datos = resto.split("## Datos")
    return python, traduccion, datos


def test_license_es_el_texto_oficial():
    assert hashlib.sha256((RAIZ / "LICENSE").read_bytes()).hexdigest() == SHA256_AGPL


def test_avisos_coinciden_con_el_bloqueo_principal():
    python, _, _ = _secciones()
    assert {f[0]: f[1] for f in _filas(python)} == avisos.leer_bloqueo(RAIZ / avisos.PRINCIPAL)


def test_avisos_coinciden_con_el_bloqueo_de_la_interfaz():
    python, _, _ = _secciones()
    en_imagen = {f[0]: f[1] for f in _filas(python) if f[3] == "Sí"}
    assert en_imagen == avisos.leer_bloqueo(RAIZ / avisos.INTERFAZ)


def test_avisos_coinciden_con_el_bloqueo_de_traduccion():
    _, traduccion, _ = _secciones()
    assert {f[0]: f[1] for f in _filas(traduccion)} == avisos.leer_bloqueo(RAIZ / avisos.TRADUCCION)


def test_lo_que_se_distribuye_es_compatible_con_agpl():
    python, _, _ = _secciones()
    a_revisar = [f[0] for f in _filas(python) if avisos.clasificar(f[2]) != "compatible"]
    assert a_revisar == []


def test_nvidia_va_en_su_tabla_aparte():
    _, traduccion, _ = _secciones()
    general, nvidia = traduccion.split("### Bibliotecas CUDA de NVIDIA")
    assert not [f[0] for f in _filas(general) if avisos.es_de_nvidia(f[0], f[2])]
    assert {"nvidia-cublas", "cuda-toolkit"} <= {f[0] for f in _filas(nvidia)}
    assert "no se distribuye" in traduccion
    assert "licencia propietaria de NVIDIA" in nvidia


def test_avisos_de_los_datos():
    _, _, datos = _secciones()
    for frase in ("CC0", "sin\ngarantías", "marca registrada de la ICH",
                  "tal como\nvienen en FAERS", "es automática", "oficial de MedDRA"):
        assert frase in datos, frase


@pytest.mark.parametrize("licencia, esperado", [
    ("MIT", "compatible"),
    ("BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0", "compatible"),
    ("Mozilla Public License 2.0 (MPL 2.0)", "compatible"),
    ("PSF-2.0", "compatible"),
    ("GNU Affero General Public License v3", "compatible"),
    ("LicenseRef-NVIDIA-Proprietary", "propietaria"),
    ("Other/Proprietary License", "propietaria"),
    ("GNU General Public License v2 (GPLv2)", "revisar"),
    ("LGPL-2.1-only", "revisar"),
    ("BSD AND GPL-2.0-only", "revisar"),
    ("CC-BY-NC-4.0", "revisar"),
    ("MIT AND CC-BY-NC-4.0", "revisar"),
    ("CC-BY-SA-4.0 AND MIT", "revisar"),
    ("SSPL-1.0 OR MIT", "revisar"),
    ("BSD-4-Clause", "revisar"),
    ("Apache-1.1", "revisar"),
    ("MPL-1.1", "revisar"),
    ("(MIT OR Apache-2.0) AND Zlib", "compatible"),
    ("Apache-2.0 WITH LLVM-exception", "compatible"),
    ("BSD License / Apache Software License", "compatible"),
    (avisos.SIN_DECLARAR, "revisar"),
    (avisos.NO_LEGIBLE, "revisar"),
])
def test_clasificar(licencia, esperado):
    assert avisos.clasificar(licencia) == esperado


@pytest.mark.parametrize("linea, completa", [
    ("  Downloading torch-2.13.0-cp312-manylinux_2_28_x86_64.whl (526.6 MB)\n", True),
    ("  Downloading pyspark-4.1.1.tar.gz (400 MB)\n", True),
    ("  Downloading torch-2.13.0-cp312-manylinux_2_28_x86_64.whl.metadata (38 kB)\n", False),
    ("  Using cached torch-2.13.0-cp312-manylinux_2_28_x86_64.whl.metadata (38 kB)\n", False),
])
def test_detecta_la_descarga_de_una_rueda_completa(linea, completa):
    assert bool(avisos.DESCARGA_COMPLETA.search(linea)) is completa


def test_licencia_de_prioriza_la_expresion():
    assert avisos.licencia_de("MIT", ["License :: OSI Approved :: BSD License"], "x") == "MIT"
    assert avisos.licencia_de(None, ["License :: OSI Approved :: BSD License"], "x") == "BSD License"
    assert avisos.licencia_de(None, None, "Mi licencia\nmás texto") == "Mi licencia"
    assert avisos.licencia_de(None, None, None) == avisos.SIN_DECLARAR


@pytest.mark.parametrize("malicioso", [
    "MIT | x | y",
    "[MIT](https://ejemplo.invalid)",
    "<img src=x>",
    "`MIT`",
    "MIT\nsegunda línea",
    "M" * (avisos.LONGITUD_MAX_LICENCIA + 1),
])
def test_metadatos_no_seguros_no_llegan_al_fichero(malicioso):
    assert avisos.licencia_de(malicioso, None, None) == avisos.NO_LEGIBLE


def test_clasificadores_no_seguros_no_llegan_al_fichero():
    clasificador = ["License :: OSI Approved :: [MIT](https://ejemplo.invalid)"]
    assert avisos.licencia_de(None, clasificador, None) == avisos.NO_LEGIBLE


def test_interfaz_enlaza_antes_de_ejecutar_la_vista():
    app = (RAIZ / "src" / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    enlaces = app.index("config.PROYECTO_URL_CODIGO")
    assert "config.PROYECTO_URL_LICENCIA" in app
    assert enlaces < re.search(r'^if zona == "inicio":', app, re.MULTILINE).start()
    for texto in ("Código fuente", "Source code", "Licencia", "License"):
        assert texto in app


def test_url_del_proyecto():
    assert config.PROYECTO_URL_CODIGO.startswith("https://github.com/")
    assert config.PROYECTO_URL_LICENCIA.startswith(config.PROYECTO_URL_CODIGO)
    assert config.PROYECTO_URL_LICENCIA.endswith("/LICENSE")


def test_imagen_docker_lleva_licencia_y_avisos():
    dockerfile = (RAIZ / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^COPY LICENSE THIRD_PARTY_NOTICES\.md /app/$", dockerfile, re.MULTILINE)


def test_readme_dice_que_cubre_solo_el_codigo():
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    seccion = readme.split("## Licencia")[1].split("\n## ")[0]
    assert "AGPL-3.0-only" in seccion
    assert "solo el código" in seccion
    assert "(LICENSE)" in seccion and "(THIRD_PARTY_NOTICES.md)" in seccion
