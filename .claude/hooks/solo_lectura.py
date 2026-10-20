#!/usr/bin/env python3
"""Hook PreToolUse (Bash) para los agentes revisores: Bash de solo lectura.

Lo usan metodo, seguridad y calidad desde su frontmatter. Deja pasar las
órdenes de lectura, las pruebas y los escáneres; bloquea (código 2) lo que
escribe, borra, instala o puede ejecutar otra orden; y obliga a preguntar a
Santos ante lo que no reconoce. Sirve para evitar errores, no es una jaula:
la frontera real es la revisión del diff y que los commits los hace Santos.
"""
import json
import os
import re
import shlex
import sys

# Órdenes que solo leen. Las redirecciones se revisan aparte.
LECTURA = {
    "ls", "cat", "head", "tail", "grep", "egrep", "fgrep", "rg", "wc", "cut", "tr",
    "diff", "cmp", "stat", "du", "df", "pwd", "echo", "printf", "which", "basename",
    "dirname", "realpath", "readlink", "test", "[", "true", "false", "cd", "nl",
    "comm", "column", "date", "jq", "pytest",
}
# Órdenes que escriben, borran, instalan, enseñan el entorno (con posibles secretos)
# o pueden ejecutar cualquier otra orden.
PROHIBIDAS = {
    "rm", "rmdir", "mv", "cp", "mkdir", "touch", "chmod", "chown", "chgrp", "ln",
    "truncate", "dd", "install", "tee", "shred", "unlink", "rsync", "scp", "patch",
    "curl", "wget", "apt", "apt-get", "dpkg", "snap", "npm", "npx", "yarn", "pnpm",
    "kill", "pkill", "killall", "docker", "podman", "sudo", "su", "bash", "sh", "zsh",
    "dash", "eval", "exec", "source", ".", "xargs", "env", "printenv", "export",
    "unset", "set", "alias", "nohup", "setsid", "crontab", "systemctl",
}
GIT_LECTURA = {
    "status", "diff", "log", "show", "ls-files", "ls-tree", "grep", "rev-parse", "blame",
    "describe", "shortlog", "cat-file", "rev-list", "merge-base", "show-ref",
    "for-each-ref", "check-ignore", "name-rev",
}
GIT_ESCRITURA = {
    "add", "commit", "push", "pull", "fetch", "merge", "rebase", "reset", "restore",
    "checkout", "switch", "rm", "mv", "clean", "cherry-pick", "revert", "am", "apply",
    "init", "clone", "gc", "prune", "update-ref", "update-index", "notes", "submodule",
    "filter-branch", "replace", "bisect", "format-patch", "archive", "bundle",
    "hash-object", "lfs",
}
FIND_PROHIBIDO = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
SCRIPTS_DEL_PROYECTO = ("scripts/git/terminos_prohibidos.sh",)
# Ficheros privados que ningún agente lee: la lista solo la usa terminos_prohibidos.sh.
PRIVADOS = ("terminos_prohibidos.txt", "horas.csv")
PUNTUACION = set("();<>|&")
ASIGNACION = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
RANGO_SED = re.compile(r"\s*\d+(\s*,\s*(\d+|\$))?\s*p\s*")
OK = ("ok", "")


def bloquear(motivo):
    return ("bloquear", motivo)


def preguntar(motivo):
    return ("preguntar", motivo)


def es_puntuacion(token):
    return bool(token) and all(c in PUNTUACION for c in token)


def opcion_corta_con(argumentos, letra):
    """True si alguna opción corta agrupada (-ni, -uo...) lleva esa letra."""
    return any(a.startswith("-") and not a.startswith("--") and letra in a[1:] for a in argumentos)


def evaluar_git(argumentos):
    i = 0
    while i < len(argumentos) and argumentos[i].startswith("-"):
        opcion = argumentos[i]
        if opcion == "-C" and i + 1 < len(argumentos):
            i += 2
        elif opcion in ("--no-pager", "-P", "--no-optional-locks"):
            i += 1
        elif opcion == "-c" or opcion.startswith(("--config-env", "--exec-path")):
            return bloquear("git -c y --exec-path pueden ejecutar otras órdenes")
        else:
            return preguntar(f"opción de git no reconocida ({opcion})")
    if i == len(argumentos):
        return OK
    sub, resto = argumentos[i], argumentos[i + 1:]
    if any(a.startswith("--output") for a in resto):
        return bloquear("git --output escribe un fichero")
    if sub in GIT_LECTURA:
        if sub == "grep" and any(a.startswith(("-O", "--open-files-in-pager")) for a in resto):
            return bloquear("git grep -O ejecuta otra orden")
        return OK
    if sub == "branch":
        cambia = {"-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy", "-f",
                  "--force", "-u", "--unset-upstream", "--edit-description", "-t", "--no-track"}
        if any(a in cambia or a.startswith(("--set-upstream-to", "--track")) for a in resto):
            return bloquear("git branch que crea, borra o mueve ramas")
        listar = {"--list", "-l", "--contains", "--no-contains", "--merged", "--no-merged", "--points-at"}
        if [a for a in resto if not a.startswith("-")] and not listar & set(resto):
            return bloquear("git branch <nombre> crea una rama")
        return OK
    if sub == "worktree":
        return OK if resto[:1] == ["list"] else bloquear("git worktree, solo para listar")
    if sub == "stash":
        return OK if resto[:1] in (["list"], ["show"]) else bloquear("git stash, solo para listar o enseñar")
    if sub == "tag":
        return OK if not resto or resto[0] in ("-l", "--list") else bloquear("git tag, solo para listar")
    if sub == "config":
        leer = ("--get", "--get-all", "--get-regexp", "--list", "-l")
        return OK if resto[:1] and resto[0] in leer else bloquear("git config, solo para leer")
    if sub == "remote":
        return preguntar("git remote puede enseñar credenciales si la URL lleva un token")
    if sub in GIT_ESCRITURA:
        return bloquear(f"git {sub} cambia el repositorio")
    return preguntar(f"git {sub} no está en la lista de lectura")


def evaluar_sed(resto):
    if any(a.startswith("--in-place") for a in resto) or opcion_corta_con(resto, "i"):
        return bloquear("sed -i modifica ficheros")
    opciones = [a for a in resto if a.startswith("-")]
    posicionales = [a for a in resto if not a.startswith("-")]
    if (opciones and set(opciones) <= {"-n", "--quiet", "--silent", "-E", "-r"}
            and posicionales and RANGO_SED.fullmatch(posicionales[0])):
        return OK
    return preguntar("sed fuera de la forma «sed -n 'N,Mp' fichero»")


def evaluar_pip(resto):
    if resto[:1] in (["show"], ["list"], ["freeze"], ["check"], ["--version"], ["-V"]):
        return OK
    return bloquear("pip, solo para show, list, freeze o check")


def desenvolver(argumentos):
    """Quita envoltorios inofensivos (timeout, time, nice) y devuelve la orden de dentro."""
    argumentos = list(argumentos)
    while argumentos and os.path.basename(argumentos[0]) in ("timeout", "time", "nice"):
        programa = os.path.basename(argumentos.pop(0))
        while argumentos and argumentos[0].startswith("-"):
            opcion = argumentos.pop(0)
            if opcion in ("-s", "-k", "--signal", "--kill-after", "-n", "--adjustment") and argumentos:
                argumentos.pop(0)
        if programa == "timeout" and argumentos:
            argumentos.pop(0)  # la duración
    return argumentos


def evaluar(argumentos):
    """Decide sobre una orden simple, ya sin redirecciones."""
    argumentos = desenvolver(argumentos)
    if not argumentos:
        return OK
    if ASIGNACION.match(argumentos[0]):
        return preguntar("variables de entorno delante de la orden")
    if argumentos[0].endswith(SCRIPTS_DEL_PROYECTO) and "tests" not in argumentos[0].split("/"):
        return OK
    programa, resto = os.path.basename(argumentos[0]), argumentos[1:]
    if programa in PROHIBIDAS:
        return bloquear(f"{programa} puede escribir, borrar, instalar o ejecutar otras órdenes")
    if programa == "git":
        return evaluar_git(resto)
    if programa == "find":
        return bloquear("find con -delete o -exec") if FIND_PROHIBIDO & set(resto) else OK
    if programa == "sed":
        return evaluar_sed(resto)
    if programa == "sort":
        if any(a.startswith("--output") for a in resto) or opcion_corta_con(resto, "o"):
            return bloquear("sort -o escribe un fichero")
        return OK
    if programa == "uniq":
        ficheros = [a for a in resto if not a.startswith("-") and not a.isdigit()]
        return bloquear("uniq con fichero de salida") if len(ficheros) > 1 else OK
    if re.fullmatch(r"python3?(\.\d+)?", programa):
        if resto[:2] == ["-m", "pytest"]:
            return OK
        if resto[:2] == ["-m", "pip"]:
            return evaluar_pip(resto[2:])
        return preguntar("python fuera de «python -m pytest»")
    if programa in ("pip", "pip3"):
        return evaluar_pip(resto)
    if programa == "pre-commit":
        return OK if resto[:1] in (["run"], ["validate-config"]) else bloquear("pre-commit, solo para «run»")
    if programa == "gitleaks":
        if any(a == "-r" or a.startswith("--report-path") for a in resto):
            return bloquear("gitleaks con informe a fichero")
        return OK
    if programa in ("bandit", "trivy"):
        if any(a == "-o" or a.startswith("--output") for a in resto):
            return bloquear(f"{programa} con salida a fichero")
        return OK
    if programa == "pip-audit":
        if any(a in ("--fix", "-o") or a.startswith("--output") for a in resto):
            return bloquear("pip-audit --fix o con salida a fichero")
        return OK
    if programa in LECTURA:
        return OK
    return preguntar(f"{programa} no está en la lista de órdenes de solo lectura")


def quitar_redirecciones(tokens):
    """Separa las redirecciones de una orden simple. Devuelve (argumentos, decisión o None)."""
    argumentos, i = [], 0
    while i < len(tokens):
        token = tokens[i]
        if not es_puntuacion(token):
            argumentos.append(token)
            i += 1
            continue
        if "(" in token or ")" in token:
            return argumentos, preguntar("subórdenes entre paréntesis")
        destino = tokens[i + 1] if i + 1 < len(tokens) else ""
        if ">" in token:
            if destino == "/dev/null" or (token.endswith("&") and destino in ("1", "2", "-")):
                if argumentos and argumentos[-1].isdigit():
                    argumentos.pop()  # el 2 de 2>/dev/null
                i += 2
                continue
            return argumentos, bloquear(f"redirección a fichero ({destino or '?'})")
        if token == "<":
            if argumentos and argumentos[-1].isdigit():
                argumentos.pop()
            i += 2
            continue
        return argumentos, preguntar("here-doc o redirección no reconocida")
    return argumentos, None


def decidir(orden):
    """Devuelve ("ok" | "preguntar" | "bloquear", motivo) para una orden de Bash."""
    if not orden.strip():
        return OK
    if any(privado in orden for privado in PRIVADOS):
        return bloquear("la lista privada y las horas no se leen; para la lista, scripts/git/terminos_prohibidos.sh --trabajo")
    if "$(" in orden or "`" in orden:
        return bloquear("sustitución de órdenes ($(...) o comillas invertidas)")
    if "<(" in orden or ">(" in orden:
        return bloquear("sustitución de procesos")
    try:
        lector = shlex.shlex(orden.replace("\n", " ; "), posix=True, punctuation_chars=True)
        lector.whitespace_split = True
        lector.commenters = ""
        tokens = list(lector)
    except ValueError:
        return preguntar("no se pudo analizar la orden (comillas sin cerrar)")
    simples, actual = [], []
    for token in tokens:
        if es_puntuacion(token) and not any(c in token for c in "<>()"):
            simples.append(actual)
            actual = []
        else:
            actual.append(token)
    simples.append(actual)
    resultado = OK
    for simple in simples:
        if not simple:
            continue
        argumentos, decision = quitar_redirecciones(simple)
        if decision is None:
            decision = evaluar(argumentos)
        if decision[0] == "bloquear":
            return decision
        if decision[0] == "preguntar" and resultado[0] == "ok":
            resultado = decision
    return resultado


def main():
    try:
        datos = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print("No se pudo leer la entrada del hook; se bloquea por seguridad.", file=sys.stderr)
        return 2
    orden = (datos.get("tool_input") or {}).get("command")
    if not isinstance(orden, str):
        return 0
    decision, motivo = decidir(orden)
    if decision == "bloquear":
        print(
            f"Bloqueado (agente de solo lectura): {motivo}. "
            "Usa órdenes de lectura, pruebas o escáneres; lo demás lo hace la sesión principal.",
            file=sys.stderr,
        )
        return 2
    if decision == "preguntar":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"Agente de solo lectura: {motivo}.",
            }
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
