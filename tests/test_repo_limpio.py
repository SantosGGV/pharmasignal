"""
test_repo_limpio.py

Pruebas de que el repositorio solo tiene lo necesario (tarea 0.9): el
.gitignore sin líneas repetidas, ningún .pyc, __pycache__ ni .venv
versionado y ninguna ruta personal en los ficheros versionados.

No usan red ni Spark. Las que llaman a git se saltan si no hay repositorio.

Ejecución:  pytest tests/ -q
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

# Rutas de una carpeta personal concreta. El patrón es genérico para no
# escribir ningún nombre de usuario; los marcadores como C:\Users\<usuario>
# del README no cuentan.
# Se construye por partes para que el propio texto del patrón no case con él.
# La carpeta personal del ejecutor de GitHub Actions no es de nadie y no cuenta.
_B, _W = "/", re.escape("\\")
RUTA_PERSONAL = re.compile("|".join([
    _B + "home" + _B + "(?!runner" + _B + ")[a-z]",
    _B + "mnt" + _B + "c" + _B + "Users" + _B + r"[^<\s]",
    "[Cc]:" + _W + "Users" + _W + r"[^<\s]",
    _B + "Users" + _B + "[A-Za-z]",
]))

hay_git = pytest.mark.skipif(
    shutil.which("git") is None or not (RAIZ / ".git").exists(),
    reason="sin git o fuera de un repositorio",
)


def _versionados():
    """Rutas que git tiene versionadas, relativas a la raíz."""
    salida = subprocess.run(
        ["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, check=True
    ).stdout
    return [r for r in salida.decode("utf-8").split("\0") if r]


def _lineas_utiles(fichero):
    """Líneas del fichero sin las vacías ni los comentarios."""
    lineas = fichero.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lineas if l.strip() and not l.strip().startswith("#")]


def _repetidas(lineas):
    """Líneas que se repiten, contando «data/raw» y «data/raw/» como la misma."""
    normalizadas = [l.rstrip("/") for l in lineas]
    return sorted({l for l in normalizadas if normalizadas.count(l) > 1})


def test_repetidas_cuenta_igual_con_y_sin_barra_final():
    assert _repetidas(["data/raw", "data/raw/", ".venv/"]) == ["data/raw"]
    assert _repetidas(["data/raw/", "data/oro/"]) == []


def test_gitignore_sin_lineas_repetidas():
    repetidas = _repetidas(_lineas_utiles(RAIZ / ".gitignore"))
    assert repetidas == [], f"Líneas repetidas en .gitignore: {repetidas}"


# Los ejemplos se montan por partes, igual que el patrón, para que este
# fichero no tenga ninguna ruta literal.
@pytest.mark.parametrize("texto, es_personal", [
    (_B + "home" + _B + "ana" + _B + "x", True),
    (_B + "mnt" + _B + "c" + _B + "Users" + _B + "ana", True),
    ("C:" + "\\" + "Users" + "\\" + "ana", True),
    (_B + "Users" + _B + "ana", True),
    (_B + "home" + _B + "runner" + _B + "work", False),
    ("C:" + "\\" + "Users" + "\\" + "<usuario>", False),
    ("~" + _B + "pharmasignal", False),
])
def test_patron_de_ruta_personal(texto, es_personal):
    assert bool(RUTA_PERSONAL.search(texto)) is es_personal


@hay_git
def test_sin_compilados_ni_entorno_versionados():
    sobran = [
        r for r in _versionados()
        if r.endswith((".pyc", ".pyo"))
        or "__pycache__/" in r
        or r.startswith(".venv/")
    ]
    assert sobran == [], f"Versionados que no deberían estar: {sobran[:10]}"


@hay_git
def test_sin_rutas_personales_en_lo_versionado():
    con_ruta = []
    for relativa in _versionados():
        fichero = RAIZ / relativa
        if not fichero.is_file():
            continue
        contenido = fichero.read_bytes()
        if b"\0" in contenido[:8000]:
            continue  # binario
        texto = contenido.decode("utf-8", errors="replace")
        for n, linea in enumerate(texto.splitlines(), start=1):
            if RUTA_PERSONAL.search(linea):
                con_ruta.append(f"{relativa}:{n}")
    assert con_ruta == [], f"Rutas personales en: {con_ruta}"
