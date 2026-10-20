"""Pruebas de las guardas de los agentes (tarea 0.13): dónde escriben y qué Bash pueden usar."""
import json
import pathlib
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SOLO_EN = RAIZ / ".claude" / "hooks" / "solo_en.py"
SOLO_LECTURA = RAIZ / ".claude" / "hooks" / "solo_lectura.py"


def lanzar(script, datos, *argumentos):
    entrada = datos if isinstance(datos, str) else json.dumps(datos)
    return subprocess.run(["python3", str(script), *argumentos], input=entrada, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    raiz = tmp_path / "repo"
    (raiz / "tests").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=raiz, check=True)
    return raiz


def escribir(repo, ruta, *permitidos, cwd=None):
    datos = {"cwd": str(cwd or repo), "tool_input": {"file_path": ruta}}
    return lanzar(SOLO_EN, datos, *permitidos).returncode


def test_calidad_escribe_en_tests(repo):
    assert escribir(repo, str(repo / "tests" / "test_x.py"), "tests/") == 0


def test_calidad_no_escribe_en_src(repo):
    assert escribir(repo, str(repo / "src" / "x.py"), "tests/") == 2


def test_calidad_no_escribe_fuera_del_repo(repo):
    assert escribir(repo, str(repo.parent / "fuera.txt"), "tests/") == 2


def test_ruta_relativa_tras_cambiar_de_carpeta(repo):
    assert escribir(repo, "test_x.py", "tests/", cwd=repo / "tests") == 0


def test_documentador_solo_docs_y_changelog(repo):
    assert escribir(repo, str(repo / "docs" / "bitacora" / "x.md"), "docs/", "CHANGELOG.md") == 0
    assert escribir(repo, str(repo / "CHANGELOG.md"), "docs/", "CHANGELOG.md") == 0
    assert escribir(repo, str(repo / "README.md"), "docs/", "CHANGELOG.md") == 2
    assert escribir(repo, str(repo / "docs_falsos" / "x.md"), "docs/", "CHANGELOG.md") == 2


def test_guarda_de_escritura_bloquea_si_no_entiende_la_entrada():
    assert lanzar(SOLO_EN, "no es json", "tests/").returncode == 2


def decision(orden):
    resultado = lanzar(SOLO_LECTURA, {"tool_input": {"command": orden}})
    if resultado.returncode == 2:
        return "bloquear"
    if resultado.stdout.strip():
        return json.loads(resultado.stdout)["hookSpecificOutput"]["permissionDecision"]
    return "ok"


@pytest.mark.parametrize("orden", [
    "git status",
    "git diff --stat",
    "git -C . log --oneline -5",
    "git branch --show-current",
    "git worktree list",
    "git log -p -- src/analisis/prr_ror.py | head -n 50",
    "pytest tests/ -q",
    "python -m pytest tests/test_prr_ror.py -v",
    "timeout 600 python -m pytest tests/ -q",
    "cd tests && pytest -q 2>&1 | tail -n 5",
    "bandit -r src -ll",
    "pip-audit -r requirements.txt",
    "gitleaks dir . --redact",
    "gitleaks detect --no-git --source . --redact",
    "grep -rn 'PRR' src/ | head -n 20",
    "ls -la && wc -l src/*.py",
    "cat config.toml 2>/dev/null",
    "find src -name '*.py'",
    "sed -n '10,40p' src/config.py",
    "scripts/git/terminos_prohibidos.sh --trabajo",
    "pip show deltalake",
    "git log --format='%h %s' | sort | uniq -c",
])
def test_ordenes_de_lectura_pasan(orden):
    assert decision(orden) == "ok"


@pytest.mark.parametrize("orden", [
    "rm -rf data",
    "/usr/bin/rm fichero",
    "echo hola > src/x.py",
    "cat a >> b",
    "sed -i 's/a/b/' src/x.py",
    "sed -ni 'p' src/x.py",
    "tee src/x.py",
    "mv a b",
    "cp a b",
    "mkdir nueva",
    "touch nuevo",
    "git add -A",
    "git commit -m prueba",
    "git checkout -b otra",
    "git branch nueva",
    "git stash",
    "git worktree add ../otra",
    "git diff --output=cambios.patch",
    "git -c core.pager=less log",
    "find . -name '*.pyc' -delete",
    "find . -exec rm {} \\;",
    "pip install requests",
    "python -m pip install requests",
    "pre-commit install",
    "bash -c 'ls'",
    "ls | xargs rm",
    "curl https://example.org",
    "echo $(rm -rf x)",
    "ls `rm x`",
    "gitleaks dir . --report-path informe.json",
    "bandit -r src -o salida.txt",
    "pip-audit --fix",
    "sort -o salida.txt entrada.txt",
    "printenv",
    "env",
    "cat ~/pharmasignal_privado/terminos_prohibidos.txt",
    "grep -rniF -f \"$PHARMASIGNAL_PRIVADO/terminos_prohibidos.txt\" docs/",
    "git log && rm -rf x",
    "ls\nrm -rf x",
    "echo x>fichero",
    "git diff>cambios.patch",
    "ls 2>&1 | tee salida.txt",
    "echo hola | sh",
    "git branch -D main",
])
def test_ordenes_que_escriben_se_bloquean(orden):
    assert decision(orden) == "bloquear"


@pytest.mark.parametrize("orden", [
    "python -c 'print(1)'",
    "awk '{print $1}' fichero",
    "make test",
    "PYTHONPATH=. pytest",
    "sed 's/a/b/' fichero",
    "cat <<EOF\nhola\nEOF",
    "(cd src && ls)",
    "git difftool",
    "git remote -v",
    "cat fichero | python3",
    "echo 'sin cerrar",
])
def test_lo_desconocido_pregunta(orden):
    assert decision(orden) == "ask"


def test_guarda_de_bash_bloquea_si_no_entiende_la_entrada():
    assert lanzar(SOLO_LECTURA, "no es json").returncode == 2
