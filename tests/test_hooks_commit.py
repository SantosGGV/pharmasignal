"""Pruebas de los hooks de la tarea 0.12 (cierre con bitácora, términos prohibidos y prefijo de tarea)
y de pruebas.sh (0.13).

Cada prueba trabaja en un repositorio git temporal y con una lista de términos inventada:
nunca se usa la lista real de Santos.
"""
import datetime
import json
import os
import pathlib
import subprocess

RAIZ = pathlib.Path(__file__).resolve().parents[1]
BITACORA = RAIZ / ".claude" / "hooks" / "exigir_bitacora.py"
TERMINOS = RAIZ / "scripts" / "git" / "terminos_prohibidos.sh"
PREFIJO = RAIZ / "scripts" / "git" / "prefijo_tarea.sh"
PRUEBAS = RAIZ / "scripts" / "git" / "pruebas.sh"
HOY = datetime.date.today().isoformat()


def git(repo, *argumentos):
    subprocess.run(
        ["git", "-c", "user.email=pruebas@example.org", "-c", "user.name=Pruebas", *argumentos],
        cwd=repo, check=True, capture_output=True, text=True,
    )


def repo_en_rama(tmp_path, rama="fase0/0.3-orden"):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "README.md").write_text("inicio\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "inicio")
    git(repo, "checkout", "-qb", rama)
    return repo


def cierre(repo, **extra):
    datos = {"cwd": str(repo), "last_assistant_message": "## Cierre de la tarea 0.3\nTodo en verde."}
    datos.update(extra)
    return subprocess.run(["python3", str(BITACORA)], input=json.dumps(datos), capture_output=True, text=True)


def test_cierre_sin_bitacora_bloquea(tmp_path):
    repo = repo_en_rama(tmp_path)
    (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
    resultado = cierre(repo)
    assert resultado.returncode == 2
    assert "bitácora" in resultado.stderr


def test_cierre_con_bitacora_de_la_tarea_deja_pasar(tmp_path):
    repo = repo_en_rama(tmp_path)
    (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
    entrada = repo / "docs" / "bitacora" / f"{HOY}_0.3-orden.md"
    entrada.parent.mkdir(parents=True)
    entrada.write_text("# entrada\n", encoding="utf-8")
    assert cierre(repo).returncode == 0


def test_bitacora_de_otra_tarea_no_vale(tmp_path):
    repo = repo_en_rama(tmp_path)
    (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
    otra = repo / "docs" / "bitacora" / f"{HOY}_0.4-sello.md"
    otra.parent.mkdir(parents=True)
    otra.write_text("# otra\n", encoding="utf-8")
    assert cierre(repo).returncode == 2


def test_sin_marca_de_cierre_deja_pasar(tmp_path):
    repo = repo_en_rama(tmp_path)
    (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
    assert cierre(repo, last_assistant_message="¿Sigo con el paso 3?").returncode == 0


def test_mencionar_el_cierre_a_mitad_del_mensaje_deja_pasar(tmp_path):
    repo = repo_en_rama(tmp_path)
    (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
    mensaje = "La skill termina con «## Cierre de la sesión»; el cierre de la tarea llega después."
    assert cierre(repo, last_assistant_message=mensaje).returncode == 0


def test_stop_hook_active_deja_pasar(tmp_path):
    repo = repo_en_rama(tmp_path)
    (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
    assert cierre(repo, stop_hook_active=True).returncode == 0


def test_solo_cambios_en_docs_deja_pasar(tmp_path):
    repo = repo_en_rama(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "nota.md").write_text("nota\n", encoding="utf-8")
    assert cierre(repo).returncode == 0


def test_sin_last_assistant_message_lee_la_transcripcion(tmp_path):
    repo = repo_en_rama(tmp_path)
    (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
    transcripcion = tmp_path / "t.jsonl"
    linea = {"type": "assistant", "message": {"content": [{"type": "text", "text": "## Cierre de la tarea 0.3"}]}}
    transcripcion.write_text(json.dumps(linea) + "\n", encoding="utf-8")
    assert cierre(repo, last_assistant_message=None, transcript_path=str(transcripcion)).returncode == 2


def test_cierre_de_sesion_sin_bitacora_bloquea(tmp_path):
    repo = repo_en_rama(tmp_path, "main")
    (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
    resultado = cierre(repo, last_assistant_message="## Cierre de la sesión\nRelease publicada.")
    assert resultado.returncode == 2
    assert f"{HOY}_*.md" in resultado.stderr


def test_cierre_de_sesion_con_entrada_de_hoy_deja_pasar(tmp_path):
    repo = repo_en_rama(tmp_path, "main")
    (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
    entrada = repo / "docs" / "bitacora" / f"{HOY}_sesion-release.md"
    entrada.parent.mkdir(parents=True)
    entrada.write_text("# entrada\n", encoding="utf-8")
    assert cierre(repo, last_assistant_message="## Cierre de la sesión\nRelease publicada.").returncode == 0


def test_entrada_ilegible_deja_pasar():
    resultado = subprocess.run(["python3", str(BITACORA)], input="no es json", capture_output=True, text=True)
    assert resultado.returncode == 0


def terminos(repo, carpeta_privada, *argumentos):
    entorno = dict(os.environ, PHARMASIGNAL_PRIVADO=str(carpeta_privada))
    return subprocess.run(["bash", str(TERMINOS), *argumentos], cwd=repo, env=entorno, capture_output=True, text=True)


def lista_inventada(tmp_path):
    privada = tmp_path / "privada"
    privada.mkdir()
    (privada / "terminos_prohibidos.txt").write_text("# comentario\nEmpresaInventada\n", encoding="utf-8")
    return privada


def test_terminos_bloquea_sin_ensenar_el_termino(tmp_path):
    repo, privada = repo_en_rama(tmp_path), lista_inventada(tmp_path)
    (repo / "nota.md").write_text("linea limpia\ntrabajo en empresainventada\n", encoding="utf-8")
    git(repo, "add", "nota.md")
    resultado = terminos(repo, privada)
    assert resultado.returncode == 1
    assert "nota.md:2" in resultado.stderr
    assert "empresainventada" not in resultado.stderr.lower()


def test_terminos_sin_coincidencias_deja_pasar(tmp_path):
    repo, privada = repo_en_rama(tmp_path), lista_inventada(tmp_path)
    (repo / "nota.md").write_text("todo limpio\n", encoding="utf-8")
    git(repo, "add", "nota.md")
    assert terminos(repo, privada).returncode == 0


def test_terminos_sin_lista_falla_avisando(tmp_path):
    repo = repo_en_rama(tmp_path)
    resultado = terminos(repo, tmp_path / "no_existe")
    assert resultado.returncode == 1
    assert "Falta la lista" in resultado.stderr


def test_terminos_modo_trabajo_ve_ficheros_nuevos(tmp_path):
    repo, privada = repo_en_rama(tmp_path), lista_inventada(tmp_path)
    (repo / "nuevo.txt").write_text("EmpresaInventada\n", encoding="utf-8")
    assert terminos(repo, privada).returncode == 0  # sin preparar para el commit, no lo ve
    resultado = terminos(repo, privada, "--trabajo")
    assert resultado.returncode == 1
    assert "nuevo.txt:1" in resultado.stderr


def prefijar(repo, origen=""):
    mensaje = repo / "MENSAJE"
    if not mensaje.exists():
        mensaje.write_text("Arregla el candado\n", encoding="utf-8")
    entorno = dict(os.environ, PRE_COMMIT_COMMIT_MSG_SOURCE=origen)
    subprocess.run(["bash", str(PREFIJO), str(mensaje)], cwd=repo, env=entorno, check=True)
    return mensaje.read_text(encoding="utf-8").splitlines()[0]


def test_prefijo_se_pone_una_sola_vez(tmp_path):
    repo = repo_en_rama(tmp_path, "fase0/0.12-bitacora")
    assert prefijar(repo) == "[0.12] Arregla el candado"
    assert prefijar(repo) == "[0.12] Arregla el candado"


def test_prefijo_no_toca_los_merges(tmp_path):
    repo = repo_en_rama(tmp_path, "fase0/0.12-bitacora")
    assert prefijar(repo, origen="merge") == "Arregla el candado"


def entorno_falso(carpeta):
    """Un .venv con python y python3 falsos que enseñan la primera carpeta del PATH y qué python3 se usa."""
    bin_ = carpeta / ".venv" / "bin"
    bin_.mkdir(parents=True)
    for nombre in ("python", "python3"):
        falso = bin_ / nombre
        falso.write_text('#!/bin/sh\necho "${PATH%%:*}"\ncommand -v python3\n', encoding="utf-8")
        falso.chmod(0o755)
    return bin_


def pruebas(repo, **variables):
    entorno = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    entorno.update(variables)
    return subprocess.run(["bash", str(PRUEBAS)], cwd=repo, env=entorno, capture_output=True, text=True, check=True)


def test_pruebas_pone_el_venv_del_repo_primero_en_el_path(tmp_path):
    repo = repo_en_rama(tmp_path)
    bin_ = entorno_falso(repo)
    assert pruebas(repo).stdout.splitlines() == [str(bin_), str(bin_ / "python3")]


def test_pruebas_respeta_el_entorno_activado(tmp_path):
    repo = repo_en_rama(tmp_path)
    entorno_falso(repo)
    otro = entorno_falso(tmp_path / "otro")
    salida = pruebas(repo, VIRTUAL_ENV=str(otro.parent)).stdout.splitlines()
    assert salida == [str(otro), str(otro / "python3")]
