"""Casos límite del rastro de sesión (0.13): rama separada, renombrados, borrados, nombres con acentos,
reanudación y cambio de día. Todo en repositorios y carpetas privadas temporales."""
import datetime
import json
import os
import pathlib
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
RASTRO = RAIZ / ".claude" / "hooks" / "rastro_sesion.py"


def git(repo, *argumentos):
    return subprocess.run(
        ["git", "-c", "user.email=pruebas@example.org", "-c", "user.name=Pruebas", *argumentos],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "a b.py").write_text("a\n", encoding="utf-8")
    (repo / "viejo.py").write_text("v\n", encoding="utf-8")
    (repo / "borrar.py").write_text("b\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "inicio")
    git(repo, "checkout", "-qb", "fase0/0.3-orden")
    return repo


@pytest.fixture
def privada(tmp_path):
    carpeta = tmp_path / "privado"
    carpeta.mkdir()
    return carpeta


def lanzar(modo, cwd, privada, sid="abcd1234", **extra):
    datos = {"session_id": sid, "cwd": str(cwd), **extra}
    entorno = dict(os.environ, PHARMASIGNAL_PRIVADO=str(privada))
    return subprocess.run(["python3", str(RASTRO), modo], input=json.dumps(datos), env=entorno,
                          capture_output=True, text=True)


def rastro(privada):
    [fichero] = (privada / "sesiones").glob("*.md")
    return fichero.read_text(encoding="utf-8")


def test_rama_separada(repo, privada):
    git(repo, "checkout", "-q", "--detach")
    lanzar("inicio", repo, privada)
    (repo / "x.py").write_text("x\n", encoding="utf-8")
    assert lanzar("fin", repo, privada).returncode == 0
    assert "- x.py" in rastro(privada)


def test_renombrado_y_borrado(repo, privada):
    lanzar("inicio", repo, privada)
    git(repo, "mv", "viejo.py", "nuevo.py")
    (repo / "borrar.py").unlink()
    lanzar("fin", repo, privada)
    texto = rastro(privada)
    assert "- nuevo.py" in texto
    assert "- borrar.py" in texto


def test_renombrado_cuenta_tambien_el_nombre_viejo(repo, privada):
    lanzar("inicio", repo, privada)
    git(repo, "mv", "viejo.py", "nuevo.py")
    lanzar("fin", repo, privada)
    assert "- viejo.py" in rastro(privada)


def test_nombre_con_acentos(repo, privada):
    lanzar("inicio", repo, privada)
    (repo / "ñandú.py").write_text("x\n", encoding="utf-8")
    lanzar("fin", repo, privada)
    assert "- ñandú.py" in rastro(privada)


def test_nombre_con_espacio_sucio(repo, privada):
    lanzar("inicio", repo, privada)
    (repo / "a b.py").write_text("cambiado\n", encoding="utf-8")
    lanzar("fin", repo, privada)
    assert "- a b.py" in rastro(privada)


def test_borrado_antes_de_empezar_y_sigue_borrado_no_cuenta(repo, privada):
    (repo / "borrar.py").unlink()
    lanzar("inicio", repo, privada)
    lanzar("fin", repo, privada)
    assert "- borrar.py" not in rastro(privada)


def test_reanudar_conserva_el_head_de_inicio(repo, privada):
    lanzar("inicio", repo, privada, source="startup")
    (repo / "x.py").write_text("x\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Añade x")
    lanzar("inicio", repo, privada, source="resume")
    lanzar("fin", repo, privada)
    assert "Añade x" in rastro(privada)


def test_cruza_la_medianoche(repo, privada):
    lanzar("inicio", repo, privada)
    ruta = privada / "sesiones" / "estado" / "abcd1234.json"
    estado = json.loads(ruta.read_text(encoding="utf-8"))
    ayer = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    estado["fecha"] = ayer
    ruta.write_text(json.dumps(estado), encoding="utf-8")
    (repo / "x.py").write_text("x\n", encoding="utf-8")
    # entrada de bitácora de hoy para la tarea: debe valer porque la sesión abarca ayer y hoy
    entrada = repo / "docs" / "bitacora" / f"{datetime.date.today().isoformat()}_0.3-orden.md"
    entrada.parent.mkdir(parents=True)
    entrada.write_text("#\n", encoding="utf-8")
    lanzar("fin", repo, privada)
    assert not list((privada / "sesiones" / "pendientes").glob("*.json"))
    assert (privada / "sesiones" / f"{ayer}_fase0-0.3-orden_abcd1234.md").exists()
