"""Pruebas del rastro de sesión, del guardado del Cierre y de su configuración (ampliación de la 0.13).

Cada prueba usa un repositorio git temporal y una carpeta privada temporal en
PHARMASIGNAL_PRIVADO: nunca se toca la carpeta privada de Santos.
"""
import datetime
import json
import os
import pathlib
import re
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
RASTRO = RAIZ / ".claude" / "hooks" / "rastro_sesion.py"
CONTEXTO = RAIZ / ".claude" / "hooks" / "contexto_sesion.sh"
HOY = datetime.date.today().isoformat()
HORA = re.compile(r"\d{1,2}:\d{2}")


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
    (repo / "README.md").write_text("inicio\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "inicio")
    git(repo, "checkout", "-qb", "fase0/0.3-orden")
    return repo


@pytest.fixture
def privada(tmp_path):
    carpeta = tmp_path / "privado"
    carpeta.mkdir()
    return carpeta


def lanzar(modo, cwd, privada, sid="abcd1234-ffff", **extra):
    datos = {"session_id": sid, "cwd": str(cwd), **extra}
    entorno = dict(os.environ, PHARMASIGNAL_PRIVADO=str(privada))
    return subprocess.run(
        ["python3", str(RASTRO), modo], input=json.dumps(datos), env=entorno, capture_output=True, text=True
    )


def rastros(privada):
    return sorted((privada / "sesiones").glob("*.md"))


def marcas(privada):
    return sorted((privada / "sesiones" / "pendientes").glob("*.json"))


def test_inicio_guarda_estado_sin_horas_y_la_hora_aparte(repo, privada):
    assert lanzar("inicio", repo, privada, source="startup").returncode == 0
    estado = privada / "sesiones" / "estado" / "abcd1234.json"
    contenido = json.loads(estado.read_text(encoding="utf-8"))
    assert contenido["rama"] == "fase0/0.3-orden" and contenido["fecha"] == HOY
    assert not HORA.search(estado.read_text(encoding="utf-8"))
    horas = privada / "horas_sesiones.csv"
    assert horas.read_text(encoding="utf-8").startswith("inicio,")
    assert oct(horas.stat().st_mode & 0o777) == "0o600"


def test_compact_no_pisa_el_estado_ni_apunta_hora(repo, privada):
    lanzar("inicio", repo, privada, source="startup")
    estado = privada / "sesiones" / "estado" / "abcd1234.json"
    head_inicial = json.loads(estado.read_text(encoding="utf-8"))["head"]
    (repo / "a.py").write_text("a = 1\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "otro")
    lanzar("inicio", repo, privada, source="compact")
    assert json.loads(estado.read_text(encoding="utf-8"))["head"] == head_inicial
    assert len((privada / "horas_sesiones.csv").read_text(encoding="utf-8").splitlines()) == 1


def test_fin_con_commit_y_codigo_deja_rastro_y_marca(repo, privada):
    lanzar("inicio", repo, privada)
    (repo / "src").mkdir()
    (repo / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Añade x")
    sha = git(repo, "rev-parse", "--short", "HEAD").strip()
    (repo / "tests.py").write_text("t = 1\n", encoding="utf-8")
    assert lanzar("fin", repo, privada, reason="prompt_input_exit").returncode == 0
    [rastro] = rastros(privada)
    texto = rastro.read_text(encoding="utf-8")
    assert rastro.name == f"{HOY}_fase0-0.3-orden_abcd1234.md"
    assert f"- {sha} Añade x" in texto and "- src/x.py" in texto and "- tests.py" in texto
    assert "prompt_input_exit" in texto
    assert oct(rastro.stat().st_mode & 0o777) == "0o600"
    [marca] = marcas(privada)
    for fichero in (rastro, marca):
        assert not HORA.search(fichero.read_text(encoding="utf-8"))
    assert not (privada / "sesiones" / "estado" / "abcd1234.json").exists()
    assert [l.split(",")[0] for l in (privada / "horas_sesiones.csv").read_text().splitlines()] == ["inicio", "fin"]


def test_solo_docs_no_deja_marca(repo, privada):
    lanzar("inicio", repo, privada)
    (repo / "docs").mkdir()
    (repo / "docs" / "nota.md").write_text("nota\n", encoding="utf-8")
    lanzar("fin", repo, privada)
    assert len(rastros(privada)) == 1 and marcas(privada) == []


def test_con_bitacora_de_la_tarea_no_deja_marca(repo, privada):
    lanzar("inicio", repo, privada)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    entrada = repo / "docs" / "bitacora" / f"{HOY}_0.3-orden.md"
    entrada.parent.mkdir(parents=True)
    entrada.write_text("# entrada\n", encoding="utf-8")
    lanzar("fin", repo, privada)
    assert marcas(privada) == []


def test_fichero_sucio_al_empezar_y_sin_tocar_no_cuenta(repo, privada):
    (repo / "viejo.py").write_text("v = 1\n", encoding="utf-8")
    lanzar("inicio", repo, privada)
    lanzar("fin", repo, privada)
    assert "- viejo.py" not in rastros(privada)[0].read_text(encoding="utf-8")
    assert marcas(privada) == []


def test_fichero_sucio_al_empezar_y_cambiado_si_cuenta(repo, privada):
    (repo / "viejo.py").write_text("v = 1\n", encoding="utf-8")
    lanzar("inicio", repo, privada)
    (repo / "viejo.py").write_text("v = 2\n", encoding="utf-8")
    lanzar("fin", repo, privada)
    assert "- viejo.py" in rastros(privada)[0].read_text(encoding="utf-8")


def test_worktree_lleva_su_rama_y_sus_ficheros(repo, privada, tmp_path):
    otro = tmp_path / "pharmasignal-0.4"
    git(repo, "worktree", "add", "-q", str(otro), "-b", "fase0/0.4-sello")
    lanzar("inicio", otro, privada, sid="11112222")
    (otro / "sello.py").write_text("s = 1\n", encoding="utf-8")
    lanzar("fin", otro, privada, sid="11112222")
    [rastro] = rastros(privada)
    assert rastro.name == f"{HOY}_fase0-0.4-sello_11112222.md"
    assert "- sello.py" in rastro.read_text(encoding="utf-8")


def test_sin_carpeta_privada_no_escribe_nada(repo, tmp_path):
    entorno = {k: v for k, v in os.environ.items() if k != "PHARMASIGNAL_PRIVADO"}
    for modo in ("inicio", "fin"):
        resultado = subprocess.run(
            ["python3", str(RASTRO), modo], input=json.dumps({"session_id": "x", "cwd": str(repo)}),
            env=entorno, capture_output=True, text=True,
        )
        assert resultado.returncode == 0
    assert list(tmp_path.rglob("*.json")) == [] and list(tmp_path.rglob("horas_sesiones.csv")) == []


def test_carpeta_privada_dentro_del_repo_no_escribe_nada(repo):
    dentro = repo / "privado"
    dentro.mkdir()
    assert lanzar("inicio", repo, dentro).returncode == 0
    assert list(dentro.iterdir()) == []


def test_entrada_ilegible_sale_con_cero(privada):
    entorno = dict(os.environ, PHARMASIGNAL_PRIVADO=str(privada))
    resultado = subprocess.run(["python3", str(RASTRO), "fin"], input="no es json", env=entorno, capture_output=True, text=True)
    assert resultado.returncode == 0
    assert list(privada.iterdir()) == []


def test_inicio_avisa_de_la_marca_y_la_borra_cuando_hay_entrada(repo, privada):
    lanzar("inicio", repo, privada)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    lanzar("fin", repo, privada)
    aviso = lanzar("inicio", repo, privada, sid="99998888").stdout
    assert "no tiene bitácora" in aviso and "fase0/0.3-orden" in aviso
    assert not HORA.search(aviso)
    lanzar("fin", repo, privada, sid="99998888")
    entrada = repo / "docs" / "bitacora" / f"{HOY}_0.3-orden.md"
    entrada.parent.mkdir(parents=True)
    entrada.write_text("# entrada\n", encoding="utf-8")
    assert "no tiene bitácora" not in lanzar("inicio", repo, privada, sid="77776666").stdout
    assert marcas(privada) == []


def test_inicio_cierra_las_sesiones_de_mas_de_24_horas(repo, privada):
    lanzar("inicio", repo, privada, sid="aaaa0000")
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    viejo = privada / "sesiones" / "estado" / "aaaa0000.json"
    hace_dos_dias = datetime.datetime.now().timestamp() - 48 * 3600
    os.utime(viejo, (hace_dos_dias, hace_dos_dias))
    salida = lanzar("inicio", repo, privada, sid="bbbb1111").stdout
    assert "aaaa0000" in salida and "sin cierre" in salida
    assert not viejo.exists()
    [rastro] = rastros(privada)
    texto = rastro.read_text(encoding="utf-8")
    assert "sesión sin cierre" in texto and "- x.py" in texto
    assert len(marcas(privada)) == 1
    lineas = (privada / "horas_sesiones.csv").read_text(encoding="utf-8").splitlines()
    assert any(l.startswith("fin,") and l.endswith(",sin_cierre") for l in lineas)


def test_inicio_no_cierra_sesiones_recientes(repo, privada):
    lanzar("inicio", repo, privada, sid="aaaa0000")
    lanzar("inicio", repo, privada, sid="bbbb1111")
    assert (privada / "sesiones" / "estado" / "aaaa0000.json").exists()
    assert rastros(privada) == []


def test_contexto_de_inicio_ensena_el_aviso_de_la_marca(repo, privada):
    lanzar("inicio", repo, privada)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    lanzar("fin", repo, privada)
    entorno = dict(os.environ, PHARMASIGNAL_PRIVADO=str(privada), CLAUDE_PROJECT_DIR=str(repo))
    entorno.pop("CLAUDE_ENV_FILE", None)
    datos = json.dumps({"session_id": "55554444", "cwd": str(repo), "source": "startup"})
    resultado = subprocess.run(["bash", str(CONTEXTO)], input=datos, env=entorno, capture_output=True, text=True)
    assert resultado.returncode == 0
    assert "Rama actual: fase0/0.3-orden" in resultado.stdout
    assert "no tiene bitácora" in resultado.stdout
    assert (privada / "sesiones" / "estado" / "55554444.json").exists()


GUARDAR = RAIZ / ".claude" / "hooks" / "guardar_cierre.py"


def guardar(cwd, privada, mensaje, sid="abcd1234", **extra):
    datos = {"session_id": sid, "cwd": str(cwd), "last_assistant_message": mensaje, **extra}
    entorno = dict(os.environ, PHARMASIGNAL_PRIVADO=str(privada))
    return subprocess.run(["python3", str(GUARDAR)], input=json.dumps(datos), env=entorno, capture_output=True, text=True)


def cierres(privada):
    return sorted(p.name for p in (privada / "cierres").glob("*.md")) if (privada / "cierres").exists() else []


def test_cierre_de_tarea_se_guarda_tal_cual(repo, privada):
    mensaje = "## Cierre de la tarea 0.3\n\nTodo en verde.\n"
    assert guardar(repo, privada, mensaje).returncode == 0
    fichero = privada / "cierres" / f"{HOY}_0.3-orden.md"
    assert fichero.read_text(encoding="utf-8") == mensaje
    assert oct(fichero.stat().st_mode & 0o777) == "0o600"


def test_cierre_de_sesion_en_otra_rama(repo, privada):
    git(repo, "checkout", "-qb", "main-pruebas")
    guardar(repo, privada, "## Cierre de la sesión\nRelease publicada.")
    assert cierres(privada) == [f"{HOY}_sesion-main-pruebas.md"]


def test_cierre_a_mitad_del_texto_no_se_guarda(repo, privada):
    assert guardar(repo, privada, "Antes del ## Cierre de la tarea 0.3 falta la bitácora.").returncode == 0
    assert cierres(privada) == []


def test_misma_sesion_pisa_y_otra_sesion_numera(repo, privada):
    lanzar("inicio", repo, privada, sid="abcd1234")
    guardar(repo, privada, "## Cierre de la tarea 0.3\nborrador", sid="abcd1234")
    guardar(repo, privada, "## Cierre de la tarea 0.3\ndefinitivo", sid="abcd1234")
    assert cierres(privada) == [f"{HOY}_0.3-orden.md"]
    assert "definitivo" in (privada / "cierres" / f"{HOY}_0.3-orden.md").read_text(encoding="utf-8")
    guardar(repo, privada, "## Cierre de la tarea 0.3\notra sesión", sid="eeee5555")
    assert cierres(privada) == [f"{HOY}_0.3-orden.md", f"{HOY}_0.3-orden_2.md"]


def test_cierre_sin_carpeta_privada_no_escribe(repo, tmp_path):
    entorno = {k: v for k, v in os.environ.items() if k != "PHARMASIGNAL_PRIVADO"}
    datos = json.dumps({"cwd": str(repo), "last_assistant_message": "## Cierre de la tarea 0.3"})
    resultado = subprocess.run(["python3", str(GUARDAR)], input=datos, env=entorno, capture_output=True, text=True)
    assert resultado.returncode == 0
    assert list(tmp_path.rglob("cierres")) == []


def test_cierre_se_lee_de_la_transcripcion_si_falta_el_mensaje(repo, privada, tmp_path):
    transcripcion = tmp_path / "t.jsonl"
    linea = {"type": "assistant", "message": {"content": [{"type": "text", "text": "## Cierre de la tarea 0.3\nok"}]}}
    transcripcion.write_text(json.dumps(linea) + "\n", encoding="utf-8")
    guardar(repo, privada, None, transcript_path=str(transcripcion))
    assert cierres(privada) == [f"{HOY}_0.3-orden.md"]


def test_guardar_cierre_con_entrada_ilegible_sale_con_cero(privada):
    entorno = dict(os.environ, PHARMASIGNAL_PRIVADO=str(privada))
    resultado = subprocess.run(["python3", str(GUARDAR)], input="no es json", env=entorno, capture_output=True, text=True)
    assert resultado.returncode == 0


def test_settings_niega_las_horas_y_conecta_los_hooks():
    ajustes = json.loads((RAIZ / ".claude" / "settings.json").read_text(encoding="utf-8"))
    permisos = ajustes["permissions"]
    for regla in ("Read(~/pharmasignal_privado/horas_sesiones.csv)", "Edit(~/pharmasignal_privado/horas_sesiones.csv)",
                  "Read(~/pharmasignal_privado/horas.csv)"):
        assert regla in permisos["deny"]
    assert not [r for r in permisos["allow"] if "horas" in r or "cierres" in r]
    [fin] = ajustes["hooks"]["SessionEnd"][0]["hooks"]
    assert "rastro_sesion.py\" fin" in fin["command"] and fin["timeout"] >= 10
    parada = " ".join(h["command"] for h in ajustes["hooks"]["Stop"][0]["hooks"])
    assert "exigir_bitacora.py" in parada and "guardar_cierre.py" in parada
