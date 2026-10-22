"""
lanzador.py

Orden única del pipeline. Ejecuta las fases declaradas en config.toml
([[lanzador.fases]]) en su orden obligatorio, con un candado (flock) para que
nunca corran dos lanzamientos a la vez en la máquina.

Uso, desde la raíz del repositorio:
    python src/lanzador.py todo               reconstruye todo
    python src/lanzador.py --desde <fase>     relanza desde una fase hasta el final
    python src/lanzador.py --solo <fase>      ejecuta una sola fase
    python src/lanzador.py --lista            enseña el plan y no ejecuta nada

Sobre la base del repositorio, las fases que escriben tablas exigen
--confirmar. Para reconstruir sin pisar los datos actuales, se usa una base
aparte con la variable de entorno PHARMASIGNAL_BASE.

Códigos de salida: 0 si todo va bien; el del script que falle (137 suele ser
falta de memoria y 139, SIGSEGV); 2 por error de uso, de las comprobaciones
previas o de un candado inseguro (enlace, de otro usuario o con permisos abiertos); 75 si el candado está ocupado; 130 si se interrumpe (Ctrl+C o
SIGTERM).

Ojo: algunos scripts terminan con código 0 aunque algo vaya mal (por ejemplo,
validar_curacion.py imprime «ATENCIÓN»). El lanzador solo ve el código de
salida: hay que leer el log.
"""

import argparse
import fcntl
import os
import shutil
import signal
import stat
# subprocess solo lanza sys.executable con scripts validados, sin shell.
import subprocess  # nosec B404
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# Raíz del repositorio en el sys.path para importar la configuración común.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config

SALIDA_USO = 2
SALIDA_OCUPADO = os.EX_TEMPFAIL  # 75
SALIDA_INTERRUMPIDO = 128 + signal.SIGINT  # 130

# El candado es privado: solo lo lee y escribe el usuario que lanza.
PERMISOS_CARPETA_CANDADO = 0o700
PERMISOS_CANDADO = 0o600
# Los logs llevan la ruta de la base, que incluye el usuario: solo para él.
PERMISOS_LOG = 0o600
# Lo que se lee del candado ocupado para decir quién lo tiene («pid=… fase=…»).
MAX_BYTES_QUIEN = 200

PISTAS = {
    137: "posible falta de memoria",
    139: "SIGSEGV, revisa la versión de pyarrow (fijada en 24.0.0)",
}


class Interrumpido(Exception):
    """El lanzador ha recibido SIGTERM."""


class CandadoInseguro(Exception):
    """El fichero o la carpeta del candado no son del usuario, son enlaces o tienen permisos abiertos."""


def _comprobar_privado(st, ruta, tipo):
    """El candado y su carpeta tienen que ser del usuario, del tipo esperado y sin permisos para otros."""
    if not tipo(st.st_mode):
        raise CandadoInseguro(f"{ruta} no es del tipo esperado (¿un enlace simbólico?)")
    if st.st_uid != os.getuid():
        raise CandadoInseguro(f"{ruta} no es del usuario que lanza")
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise CandadoInseguro(f"{ruta} tiene permisos para otros usuarios: quítalos con chmod go-rwx")


def _al_recibir_sigterm(signum, frame):
    raise Interrumpido


def _relativa(ruta, raiz):
    """Ruta relativa a la raíz del repositorio para enseñarla, si se puede."""
    try:
        return str(Path(ruta).relative_to(raiz))
    except ValueError:
        return str(ruta)


def seleccionar(fases, desde=None, solo=None):
    """Fases a ejecutar: todas, desde una hasta el final o una sola."""
    nombres = [f["nombre"] for f in fases]
    elegida = desde or solo
    if elegida is None:
        return list(fases)
    if elegida not in nombres:
        raise ValueError(f"fase desconocida «{elegida}»; las fases son: {', '.join(nombres)}")
    i = nombres.index(elegida)
    return fases[i:i + 1] if solo else fases[i:]


def validar_scripts(plan, raiz_scripts):
    """Cada script tiene que ser un .py que exista dentro de raiz_scripts."""
    raiz = Path(raiz_scripts).resolve()
    errores = []
    for fase in plan:
        for script in fase["scripts"]:
            ruta = Path(script).resolve()
            if ruta.suffix != ".py" or not ruta.is_relative_to(raiz):
                errores.append(f"{script}: el script tiene que ser un .py dentro de {raiz}")
            elif not ruta.is_file():
                errores.append(f"{script}: no existe")
    return errores


def menor_espacio_libre(base, discos_extra):
    """(ruta, GB libres) del disco con menos espacio entre la base, la temporal y los
    discos extra que existan, o None si no existe ninguno.

    La temporal es donde Spark vuelca el shuffle por defecto. En WSL2 el disco de
    Linux es virtual y aparenta casi 1 TB libre: el que se llena es /mnt/c.
    """
    rutas = [str(base), tempfile.gettempdir(), *map(str, discos_extra)]
    libres = [(ruta, shutil.disk_usage(ruta).free / 1024**3)
              for ruta in dict.fromkeys(rutas) if Path(ruta).exists()]
    return min(libres, key=lambda par: par[1], default=None)


def comprobar_previas(plan, base, raiz_repo, espacio_min_gb, confirmar, discos_extra=()):
    """Entrada de la primera fase, espacio libre y protección de la base del repositorio."""
    errores = []
    primera = plan[0]
    for ruta in primera["entrada"]:
        p = Path(ruta)
        if not p.is_dir() or not any(p.iterdir()):
            errores.append(f"la entrada de la fase {primera['nombre']} no existe o está vacía: {ruta}")

    menor = menor_espacio_libre(base, discos_extra)
    if menor is not None and menor[1] < espacio_min_gb:
        errores.append(f"solo quedan {menor[1]:.1f} GB libres en {menor[0]} (mínimo {espacio_min_gb} GB)")

    escriben = [f["nombre"] for f in plan if f["escribe_tablas"]]
    if escriben and not confirmar and Path(base).resolve() == Path(raiz_repo).resolve():
        errores.append(
            f"las fases {', '.join(escriben)} escriben tablas sobre la base del repositorio "
            "y pisarían los datos actuales: usa una base aparte con PHARMASIGNAL_BASE "
            "o añade --confirmar"
        )
    return errores


def coger_candado(ruta):
    """Devuelve (descriptor, None) si coge el candado, o (None, quién lo tiene) si está ocupado.

    El fichero nunca se borra: el núcleo suelta el candado cuando muere el
    proceso que lo tiene, así que no quedan candados huérfanos. Lanza
    CandadoInseguro si el fichero o su carpeta son enlaces, de otro usuario o
    tienen permisos para otros.
    """
    carpeta = Path(ruta).parent
    carpeta.mkdir(mode=PERMISOS_CARPETA_CANDADO, parents=True, exist_ok=True)
    _comprobar_privado(os.lstat(carpeta), carpeta, stat.S_ISDIR)
    try:
        fd = os.open(ruta, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, PERMISOS_CANDADO)
    except OSError as e:
        raise CandadoInseguro(f"no se puede abrir {ruta} sin seguir enlaces: {e.strerror}") from e
    try:
        _comprobar_privado(os.fstat(fd), ruta, stat.S_ISREG)
    except CandadoInseguro:
        os.close(fd)
        raise
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        quien = os.read(fd, MAX_BYTES_QUIEN).decode(errors="replace").strip()
        os.close(fd)
        return None, quien or "sin datos"
    return fd, None


def anotar_candado(fd, texto):
    """Deja en el fichero del candado quién lo tiene, para el aviso de ocupado."""
    os.ftruncate(fd, 0)
    os.pwrite(fd, f"{texto}\n".encode(), 0)


def terminar(proc, espera):
    """Para el grupo del script (también la JVM de Spark): SIGTERM, espera y SIGKILL.

    Mientras apaga, ignora un segundo Ctrl+C o SIGTERM para no saltarse el SIGKILL.
    """
    anteriores = {s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=espera)
        except subprocess.TimeoutExpired:
            pass
        # Lo que quede vivo del grupo, fuera.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
    finally:
        for s, anterior in anteriores.items():
            signal.signal(s, anterior)


def ejecutar_script(script, log, fd_candado, cwd, espera):
    """Ejecuta un script con el mismo Python, copia su salida a la terminal y al log
    y devuelve su código de salida."""
    entorno = dict(os.environ, PYTHONUNBUFFERED="1")
    # El script va en su propia sesión para poder pararlo entero (con la JVM)
    # y hereda el candado: si el lanzador muere, el candado sigue cogido hasta
    # que el script termina. Sin shell; el script lo valida validar_scripts.
    # El Popen va dentro del try para que una señal recién arrancado el script
    # también lo pare.
    proc = None
    try:
        proc = subprocess.Popen(  # nosec B603
            [sys.executable, script],
            cwd=cwd,
            env=entorno,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            pass_fds=(fd_candado,),
        )
        for linea in proc.stdout:
            texto = linea.decode(errors="replace")
            sys.stdout.write(texto)
            sys.stdout.flush()
            log.write(texto)
        return proc.wait()
    except (KeyboardInterrupt, Interrumpido):
        if proc is not None:
            terminar(proc, espera)
        raise
    finally:
        if proc is not None:
            proc.stdout.close()


def codigo_salida(rc):
    """Un proceso muerto por una señal da -N en Python; en la terminal sería 128 + N."""
    return 128 - rc if rc < 0 else rc


def ejecutar_plan(plan, fd, logs, raiz_repo, espera, confirmar):
    """Ejecuta las fases en orden y para en el primer script que falle."""
    Path(logs).mkdir(parents=True, exist_ok=True)
    extra = " --confirmar" if confirmar else ""
    for fase in plan:
        nombre = fase["nombre"]
        anotar_candado(fd, f"pid={os.getpid()} fase={nombre}")
        sello = datetime.now().strftime("%Y%m%d-%H%M%S")
        ruta_log = Path(logs) / f"{sello}_{nombre}.log"
        print(f"\n=== Fase {nombre} · log en {ruta_log}", flush=True)
        fd_log = os.open(ruta_log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, PERMISOS_LOG)
        with os.fdopen(fd_log, "w", encoding="utf-8") as log:
            log.write(f"fase {nombre}\nbase {config.BASE}\ninicio {datetime.now().isoformat(timespec='seconds')}\n")
            for script in fase["scripts"]:
                visible = _relativa(script, raiz_repo)
                cabecera = f"--- {visible}\n"
                print(cabecera, end="", flush=True)
                log.write(cabecera)
                inicio = time.monotonic()
                try:
                    rc = codigo_salida(ejecutar_script(script, log, fd, raiz_repo, espera))
                except (KeyboardInterrupt, Interrumpido):
                    log.write(f"--- {visible}: interrumpido\n")
                    print(f"\nInterrumpido en {visible}. Para relanzar: "
                          f"python src/lanzador.py --desde {nombre}{extra}", file=sys.stderr)
                    raise
                duracion = time.monotonic() - inicio
                resumen = f"--- {visible}: código {rc}, {duracion:.0f} s\n"
                print(resumen, end="", flush=True)
                log.write(resumen)
                if rc != 0:
                    pista = f", {PISTAS[rc]}" if rc in PISTAS else ""
                    print(f"\nFalló {visible} (código {rc}{pista}). Para relanzar: "
                          f"python src/lanzador.py --desde {nombre}{extra}", file=sys.stderr)
                    return rc
    print("\nTerminado sin errores.", flush=True)
    return 0


def mostrar_lista(plan, fuera, base, candado, raiz_repo, avisos, menor=None):
    """Enseña el plan sin ejecutar nada."""
    print(f"Base: {base}")
    print(f"Candado: {candado}")
    if menor is not None:
        print(f"Disco con menos espacio libre: {menor[0]} ({menor[1]:.1f} GB)")
    for i, fase in enumerate(plan, 1):
        tablas = "escribe tablas" if fase["escribe_tablas"] else "no escribe tablas"
        print(f"\n{i}. {fase['nombre']} ({tablas})")
        print(f"   entrada: {', '.join(fase['entrada']) or '-'}")
        print(f"   salida:  {', '.join(fase['salida']) or '-'}")
        for script in fase["scripts"]:
            print(f"   - {_relativa(script, raiz_repo)}")
    if fuera:
        print("\nNo los reconstruye el lanzador:")
        for f in fuera:
            print(f"   - {_relativa(f['script'], raiz_repo)}: {f['motivo']}")
    print()
    if avisos:
        print("Comprobaciones previas (un lanzamiento real se pararía):")
        for aviso in avisos:
            print(f"   - {aviso}")
    else:
        print("Comprobaciones previas: bien.")


def main(argv=None, *, fases=None, fuera=None, base=None, raiz_repo=None,
         raiz_scripts=None, candado=None, espacio_min_gb=None, logs=None, espera=None,
         discos_extra=None):
    """Punto de entrada. Los parámetros con nombre solo los usan las pruebas."""
    fases = config.LANZADOR_FASES if fases is None else fases
    fuera = config.LANZADOR_FUERA if fuera is None else fuera
    base = config.BASE if base is None else base
    raiz_repo = config.RAIZ_REPO if raiz_repo is None else raiz_repo
    raiz_scripts = Path(raiz_repo) / "src" if raiz_scripts is None else raiz_scripts
    candado = config.LANZADOR_CANDADO if candado is None else candado
    espacio_min_gb = config.LANZADOR_ESPACIO_MIN_GB if espacio_min_gb is None else espacio_min_gb
    logs = config.RUTAS_LOGS if logs is None else logs
    espera = config.LANZADOR_ESPERA_TERMINAR_S if espera is None else espera
    discos_extra = config.LANZADOR_DISCOS_EXTRA if discos_extra is None else discos_extra

    parser = argparse.ArgumentParser(
        prog="python src/lanzador.py",
        description="Lanza el pipeline de PharmaSignal por fases, con candado.",
    )
    parser.add_argument("orden", nargs="?", choices=["todo"], help="reconstruye todas las fases")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--desde", metavar="FASE", help="relanza desde esta fase hasta el final")
    grupo.add_argument("--solo", metavar="FASE", help="ejecuta solo esta fase")
    grupo.add_argument("--lista", action="store_true", help="enseña el plan y no ejecuta nada")
    parser.add_argument("--confirmar", action="store_true",
                        help="permite escribir tablas sobre la base del repositorio")
    args = parser.parse_args(argv)

    elegidas = sum([args.orden is not None, args.desde is not None,
                    args.solo is not None, args.lista])
    if elegidas != 1:
        parser.error("elige una orden: todo, --desde FASE, --solo FASE o --lista")

    try:
        plan = seleccionar(fases, args.desde, args.solo)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return SALIDA_USO

    errores = validar_scripts(plan, raiz_scripts)
    errores += comprobar_previas(plan, base, raiz_repo, espacio_min_gb, args.confirmar, discos_extra)

    if args.lista:
        mostrar_lista(plan, fuera, base, candado, raiz_repo, errores,
                      menor_espacio_libre(base, discos_extra))
        return 0

    if errores:
        for error in errores:
            print(f"Error: {error}", file=sys.stderr)
        return SALIDA_USO

    try:
        fd, quien = coger_candado(candado)
    except CandadoInseguro as e:
        print(f"Error: candado inseguro: {e}", file=sys.stderr)
        return SALIDA_USO
    if fd is None:
        print(f"Ya hay un lanzamiento en curso ({quien}). Espera a que termine.", file=sys.stderr)
        return SALIDA_OCUPADO

    anterior = signal.signal(signal.SIGTERM, _al_recibir_sigterm)
    try:
        return ejecutar_plan(plan, fd, logs, raiz_repo, espera, args.confirmar)
    except (KeyboardInterrupt, Interrumpido):
        return SALIDA_INTERRUMPIDO
    finally:
        signal.signal(signal.SIGTERM, anterior)
        os.close(fd)


if __name__ == "__main__":
    sys.exit(main())
