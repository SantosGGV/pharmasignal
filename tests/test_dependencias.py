"""Pruebas del bloqueo de dependencias (tarea 0.7). Sin red ni instalaciones."""
import importlib.util
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
REQ = RAIZ / "requirements.txt"

_spec = importlib.util.spec_from_file_location(
    "comprobar_bloqueo", RAIZ / "scripts" / "deps" / "comprobar_bloqueo.py")
assert _spec is not None and _spec.loader is not None
cb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cb)


# Comparador

def test_normalizar_nombres():
    assert cb.normalizar("delta_spark") == cb.normalizar("Delta-Spark") == "delta-spark"
    assert cb.normalizar("zope.interface") == "zope-interface"


def test_leer_bloqueo_ignora_comentarios_y_vacias(tmp_path):
    f = tmp_path / "req.txt"
    f.write_text("# cabecera\n\nGitPython==3.2.1\ndelta_spark==4.3.1\n", encoding="utf-8")
    assert cb.leer_bloqueo(f) == {"gitpython": "3.2.1", "delta-spark": "4.3.1"}


@pytest.mark.parametrize("linea", ["pandas", "pandas>=3.0", "pandas==3.0.3 ; extra",
                                   "-r otro.txt", "git+https://example.org/x.git"])
def test_leer_bloqueo_rechaza_lineas_sin_version_exacta(tmp_path, linea):
    f = tmp_path / "req.txt"
    f.write_text(linea + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="req.txt:1"):
        cb.leer_bloqueo(f)


def test_leer_bloqueo_rechaza_paquete_con_dos_versiones(tmp_path):
    f = tmp_path / "req.txt"
    f.write_text("pillow==12.3.0\nPillow==13.0.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dos versiones"):
        cb.leer_bloqueo(f)


def test_comparar_detecta_faltan_distintos_y_sobrantes():
    bloqueo = {"a": "1.0", "b": "2.0", "c": "3.0"}
    presentes = {"a": "1.0", "b": "2.1", "d": "4.0", "pip": "26.2"}
    faltan, distintos, sobrantes = cb.comparar(bloqueo, presentes)
    assert faltan == ["c"]
    assert distintos == [("b", "2.0", "2.1")]
    assert sobrantes == ["d"]  # pip se ignora


def test_comparar_permitir_sobrantes():
    _, _, sobrantes = cb.comparar({"a": "1"}, {"a": "1", "x": "9"}, permitir_sobrantes=True)
    assert sobrantes == []


def test_main_codigos_de_salida(tmp_path):
    bueno = tmp_path / "bueno.txt"
    bueno.write_text("", encoding="utf-8")
    malo = tmp_path / "malo.txt"
    malo.write_text("pandas>=3\n", encoding="utf-8")
    inexistente = tmp_path / "no_existe.txt"
    assert cb.main(["--permitir-sobrantes", str(bueno)]) == 0
    assert cb.main([str(malo)]) == 2
    assert cb.main([str(inexistente)]) == 2


def test_main_falla_si_dos_bloqueos_chocan(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("pandas==3.0.3\n", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("pandas==3.0.2\n", encoding="utf-8")
    assert cb.main(["--permitir-sobrantes", str(a), str(b)]) == 2


# Bloqueo del repositorio

def test_requirements_es_un_bloqueo_valido():
    paquetes = cb.leer_bloqueo(REQ)  # lanza si alguna línea no es nombre==versión
    assert len(paquetes) > 0


def test_requirements_mantiene_pines_criticos():
    paquetes = cb.leer_bloqueo(REQ)
    # pyarrow 25 da SIGSEGV con deltalake 1.6.2 (CLAUDE.md).
    assert paquetes["pyarrow"] == "24.0.0"
    assert paquetes["deltalake"] == "1.6.2"
    assert paquetes["pyspark"] == "4.1.1"
    # Transitivas de deltalake que faltaban antes de la 0.7.
    for n in ("arro3-core", "deprecated", "wrapt"):
        assert n in paquetes


def test_interfaz_es_subconjunto_con_las_mismas_versiones():
    principal = cb.leer_bloqueo(REQ)
    interfaz = cb.leer_bloqueo(RAIZ / "requirements-interfaz.txt")
    fuera = sorted(n for n in interfaz if n not in principal)
    distintas = sorted((n, v, principal[n]) for n, v in interfaz.items()
                       if n in principal and principal[n] != v)
    assert fuera == [], f"en la interfaz pero no en requirements.txt: {fuera}"
    assert distintas == [], f"versiones distintas (interfaz, principal): {distintas}"
    for n in ("streamlit", "deltalake", "pyarrow", "pandas", "plotly", "numpy"):
        assert n in interfaz
    # La imagen no lleva Spark.
    assert "pyspark" not in interfaz and "delta-spark" not in interfaz


def test_dockerfile_instala_desde_el_bloqueo_de_la_interfaz():
    texto = (RAIZ / "docker" / "Dockerfile").read_text(encoding="utf-8")
    instrucciones = [l for l in texto.splitlines() if not l.lstrip().startswith("#")]
    codigo = "\n".join(instrucciones)
    assert "pip install --no-cache-dir -r /tmp/requirements-interfaz.txt" in codigo
    # Ningún pin escrito a mano en el Dockerfile: todos van en el bloqueo.
    assert "==" not in codigo


def test_traduccion_es_bloqueo_aparte_coherente_con_el_principal():
    principal = cb.leer_bloqueo(REQ)
    trad = cb.leer_bloqueo(RAIZ / "requirements-traduccion.txt")
    assert "argostranslate" in trad
    # argostranslate no entra en el entorno principal: rompería pip check.
    assert "argostranslate" not in principal and "stanza" not in principal
    distintas = sorted((n, v, principal[n]) for n, v in trad.items()
                       if n in principal and principal[n] != v)
    assert distintas == [], f"versiones distintas (traducción, principal): {distintas}"


def test_pip_audit_revisa_los_tres_bloqueos_en_pre_commit_y_ci():
    precommit = (RAIZ / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    ci = (RAIZ / ".github" / "workflows" / "pruebas.yml").read_text(encoding="utf-8")
    for fichero in ("requirements.txt", "requirements-interfaz.txt",
                    "requirements-traduccion.txt"):
        assert fichero in precommit, f"pre-commit no audita {fichero}"
        assert fichero in ci, f"el CI no audita {fichero}"


def test_requirements_dev_fija_versiones():
    paquetes = cb.leer_bloqueo(RAIZ / "requirements-dev.txt")
    assert "pytest" in paquetes


def test_main_devuelve_1_si_no_coincide_y_0_si_coincide(tmp_path, monkeypatch, capsys):
    bloqueo = tmp_path / "b.txt"
    bloqueo.write_text("a==1.0\nb==2.0\n", encoding="utf-8")
    monkeypatch.setattr(cb, "instalados", lambda: {"a": "1.0", "b": "2.0", "pip": "26"})
    assert cb.main([str(bloqueo)]) == 0
    monkeypatch.setattr(cb, "instalados", lambda: {"a": "1.1", "x": "1"})
    assert cb.main([str(bloqueo)]) == 1
    salida = capsys.readouterr().out
    assert "falta      b==2.0" in salida and "distinta   a" in salida and "sobrante   x" in salida


def test_leer_bloqueo_acepta_version_local_y_nombre_con_punto(tmp_path):
    f = tmp_path / "req.txt"
    f.write_text("torch==2.3.0+cpu\nzope.interface==7.0\n", encoding="utf-8")
    assert cb.leer_bloqueo(f) == {"torch": "2.3.0+cpu", "zope-interface": "7.0"}
