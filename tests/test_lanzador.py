"""
test_lanzador.py

Pruebas del lanzador del pipeline (src/lanzador.py) y de su configuración.

Ninguna lanza Spark: las fases de prueba son scripts falsos en un directorio
temporal (imprimen, esperan o salen con un código), así que valen en el CI.

Ejecución:  pytest tests/ -v
"""

import collections
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import pytest

from src import config, lanzador

RAIZ = Path(__file__).resolve().parents[1]

NOMBRES_FASES = ["ingesta", "curacion", "validacion", "analisis", "control"]


def _nombres_scripts(fase):
    return [Path(s).name for s in fase["scripts"]]


# --- Configuración ----------------------------------------------------------

def test_fases_en_orden():
    assert [f["nombre"] for f in config.LANZADOR_FASES] == NOMBRES_FASES


def test_scripts_de_las_fases_existen_bajo_src():
    raiz_src = config.RAIZ_REPO / "src"
    for fase in config.LANZADOR_FASES:
        assert fase["scripts"], f"la fase {fase['nombre']} no tiene scripts"
        for s in fase["scripts"]:
            ruta = Path(s)
            assert ruta.is_file(), s
            assert ruta.suffix == ".py"
            assert ruta.resolve().is_relative_to(raiz_src)


def test_curar_demo_va_antes_que_el_resto_de_la_curacion():
    fase = next(f for f in config.LANZADOR_FASES if f["nombre"] == "curacion")
    assert _nombres_scripts(fase)[0] == "curar_demo.py"


def test_prr_ror_va_antes_que_analisis_geografico():
    fase = next(f for f in config.LANZADOR_FASES if f["nombre"] == "analisis")
    nombres = _nombres_scripts(fase)
    assert nombres.index("prr_ror.py") < nombres.index("analisis_geografico.py")


def test_rutas_de_las_fases_salen_de_la_base():
    for fase in config.LANZADOR_FASES:
        for ruta in fase["entrada"] + fase["salida"]:
            assert Path(ruta).is_relative_to(config.BASE)


def test_traducir_terminos_queda_fuera_del_lanzador():
    en_fases = [Path(s).name for f in config.LANZADOR_FASES for s in f["scripts"]]
    fuera = [Path(f["script"]).name for f in config.LANZADOR_FUERA]
    assert "traducir_terminos.py" in fuera
    assert "traducir_terminos.py" not in en_fases


def test_candado_y_espacio():
    candado = Path(config.LANZADOR_CANDADO)
    assert candado.is_absolute()
    assert "~" not in config.LANZADOR_CANDADO
    # Único para la máquina: en la carpeta personal, fuera del repo (lo comparten
    # los worktrees) y fuera de /tmp (se borra al reiniciar y cualquiera escribe).
    assert candado.is_relative_to(Path.home())
    assert not candado.is_relative_to(config.RAIZ_REPO)
    assert not candado.is_relative_to(Path(tempfile.gettempdir()))
    assert not candado.is_relative_to(config.BASE)
    assert config.LANZADOR_ESPACIO_MIN_GB > 0
    assert config.LANZADOR_ESPERA_TERMINAR_S > 0
    # En WSL2 se mide también el disco de Windows, que es el que se llena.
    assert "/mnt/c" in config.LANZADOR_DISCOS_EXTRA
    assert all(Path(d).is_absolute() for d in config.LANZADOR_DISCOS_EXTRA)


def test_ninguna_fase_escribe_en_raw():
    raw = Path(config.RUTAS_RAW).resolve()
    for fase in config.LANZADOR_FASES:
        for ruta in fase["salida"]:
            r = Path(ruta).resolve()
            assert not (r == raw or r.is_relative_to(raw) or raw.is_relative_to(r)), \
                f"la fase {fase['nombre']} escribiría en data/raw"


# --- Lanzador con fases falsas ----------------------------------------------

@pytest.fixture
def entorno(tmp_path):
    """Base falsa con una entrada no vacía, scripts falsos y candado propio."""
    scripts = tmp_path / "src"
    scripts.mkdir()
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    (entrada / "algo").write_text("x")
    marcas = tmp_path / "marcas"
    marcas.mkdir()

    def script(nombre, cuerpo=""):
        ruta = scripts / f"{nombre}.py"
        ruta.write_text(textwrap.dedent(f"""\
            import os, pathlib, sys, time
            pathlib.Path({str(marcas)!r}, {nombre!r}).write_text(str(os.getpid()))
            print("hola desde {nombre}")
        """) + textwrap.dedent(cuerpo))
        return str(ruta)

    def fase(nombre, *nombres_scripts, escribe_tablas=False):
        return {"nombre": nombre, "scripts": [script(n) if isinstance(n, str) else script(*n)
                                              for n in nombres_scripts],
                "entrada": [str(entrada)], "salida": [], "escribe_tablas": escribe_tablas}

    opciones = dict(fuera=[], base=tmp_path / "base", raiz_repo=tmp_path / "repo",
                    raiz_scripts=scripts, candado=str(tmp_path / "cache" / "pipeline.lock"),
                    espacio_min_gb=0, logs=str(tmp_path / "logs"), espera=5,
                    discos_extra=[])
    (tmp_path / "base").mkdir()
    (tmp_path / "repo").mkdir()
    E = collections.namedtuple("E", "tmp script fase marcas opciones entrada")
    return E(tmp_path, script, fase, marcas, opciones, entrada)


def _ejecutadas(entorno):
    return sorted(p.name for p in entorno.marcas.iterdir())


def _tres_fases(entorno):
    return [entorno.fase("a", "a1", "a2"), entorno.fase("b", "b1"), entorno.fase("c", "c1")]


def test_todo_ejecuta_todas_las_fases_en_orden(entorno, capsys):
    rc = lanzador.main(["todo"], fases=_tres_fases(entorno), **entorno.opciones)
    assert rc == 0
    salida = capsys.readouterr().out
    assert _ejecutadas(entorno) == ["a1", "a2", "b1", "c1"]
    assert salida.index("hola desde a1") < salida.index("hola desde b1") < salida.index("hola desde c1")


def test_desde_ejecuta_desde_esa_fase(entorno):
    assert lanzador.main(["--desde", "b"], fases=_tres_fases(entorno), **entorno.opciones) == 0
    assert _ejecutadas(entorno) == ["b1", "c1"]


def test_solo_ejecuta_una_fase(entorno):
    assert lanzador.main(["--solo", "b"], fases=_tres_fases(entorno), **entorno.opciones) == 0
    assert _ejecutadas(entorno) == ["b1"]


def test_fase_desconocida_da_2(entorno):
    assert lanzador.main(["--solo", "zeta"], fases=_tres_fases(entorno), **entorno.opciones) == 2
    assert _ejecutadas(entorno) == []


@pytest.mark.parametrize("argv", [[], ["todo", "--solo", "a"], ["--solo", "a", "--desde", "b"]])
def test_sin_orden_o_con_dos_da_error_de_uso(entorno, argv):
    with pytest.raises(SystemExit) as e:
        lanzador.main(argv, fases=_tres_fases(entorno), **entorno.opciones)
    assert e.value.code == 2


def test_lista_no_ejecuta_nada_y_avisa_de_lo_que_queda_fuera(entorno, capsys):
    fuera = [{"script": str(entorno.tmp / "src" / "traducir_terminos.py"), "motivo": "trad_terminos aparte"}]
    opciones = dict(entorno.opciones, fuera=fuera)
    assert lanzador.main(["--lista"], fases=_tres_fases(entorno), **opciones) == 0
    salida = capsys.readouterr().out
    assert _ejecutadas(entorno) == []
    assert "No los reconstruye el lanzador" in salida
    assert "trad_terminos aparte" in salida


def test_para_en_el_primer_fallo_y_devuelve_su_codigo(entorno, capsys):
    fases = [entorno.fase("a", "a1", ("a2", "sys.exit(3)"), "a3"), entorno.fase("b", "b1")]
    assert lanzador.main(["todo"], fases=fases, **entorno.opciones) == 3
    assert _ejecutadas(entorno) == ["a1", "a2"]
    assert "--desde a" in capsys.readouterr().err


def test_muerte_por_senal_da_128_mas_n_y_pista(entorno, capsys):
    fases = [entorno.fase("a", ("a1", "os.kill(os.getpid(), 9)"))]
    assert lanzador.main(["todo"], fases=fases, **entorno.opciones) == 137
    assert "falta de memoria" in capsys.readouterr().err


def test_escribe_un_log_por_fase_con_codigo_y_duracion(entorno):
    assert lanzador.main(["todo"], fases=_tres_fases(entorno), **entorno.opciones) == 0
    logs = sorted(Path(entorno.opciones["logs"]).iterdir())
    assert [p.name.rsplit("_", 1)[1] for p in logs] == ["a.log", "b.log", "c.log"]
    texto = logs[0].read_text(encoding="utf-8")
    assert "hola desde a1" in texto
    assert "a2.py: código 0" in texto
    assert " s\n" in texto


# --- Comprobaciones previas -------------------------------------------------

def test_entrada_vacia_da_2(entorno):
    for p in entorno.entrada.iterdir():
        p.unlink()
    assert lanzador.main(["todo"], fases=_tres_fases(entorno), **entorno.opciones) == 2
    assert _ejecutadas(entorno) == []


def test_poco_espacio_da_2(entorno, monkeypatch):
    Uso = collections.namedtuple("Uso", "total used free")
    monkeypatch.setattr(lanzador.shutil, "disk_usage", lambda ruta: Uso(100, 99, 1024**3))
    opciones = dict(entorno.opciones, espacio_min_gb=25)
    assert lanzador.main(["todo"], fases=_tres_fases(entorno), **opciones) == 2
    assert _ejecutadas(entorno) == []



def _espacio_falso(monkeypatch, libres_gb):
    """disk_usage falso: GB libres por ruta; las demás, de sobra."""
    Uso = collections.namedtuple("Uso", "total used free")
    def disk_usage(ruta):
        return Uso(0, 0, libres_gb.get(str(ruta), 1000) * 1024**3)
    monkeypatch.setattr(lanzador.shutil, "disk_usage", disk_usage)


def test_mide_el_disco_extra_aunque_la_base_aparente_espacio(entorno, monkeypatch):
    disco_c = entorno.tmp / "mnt_c"
    disco_c.mkdir()
    _espacio_falso(monkeypatch, {str(disco_c): 10})
    opciones = dict(entorno.opciones, espacio_min_gb=25, discos_extra=[str(disco_c)])
    assert lanzador.main(["todo"], fases=_tres_fases(entorno), **opciones) == 2
    assert _ejecutadas(entorno) == []


def test_usa_el_menor_de_los_discos(entorno, monkeypatch):
    disco_c = entorno.tmp / "mnt_c"
    disco_c.mkdir()
    base = str(entorno.opciones["base"])
    _espacio_falso(monkeypatch, {base: 900, str(disco_c): 30})
    assert lanzador.menor_espacio_libre(base, [str(disco_c)]) == (str(disco_c), 30)
    opciones = dict(entorno.opciones, espacio_min_gb=25, discos_extra=[str(disco_c)])
    assert lanzador.main(["--solo", "a"], fases=_tres_fases(entorno), **opciones) == 0


def test_disco_extra_que_no_existe_se_ignora(entorno, monkeypatch):
    _espacio_falso(monkeypatch, {})
    opciones = dict(entorno.opciones, espacio_min_gb=25, discos_extra=[str(entorno.tmp / "no_hay")])
    assert lanzador.main(["--solo", "a"], fases=_tres_fases(entorno), **opciones) == 0


def test_lista_ensena_el_disco_con_menos_espacio(entorno, monkeypatch, capsys):
    disco_c = entorno.tmp / "mnt_c"
    disco_c.mkdir()
    _espacio_falso(monkeypatch, {str(disco_c): 10})
    opciones = dict(entorno.opciones, espacio_min_gb=25, discos_extra=[str(disco_c)])
    assert lanzador.main(["--lista"], fases=_tres_fases(entorno), **opciones) == 0
    salida = capsys.readouterr().out
    assert f"Disco con menos espacio libre: {disco_c} (10.0 GB)" in salida
    assert "solo quedan 10.0 GB libres" in salida


def test_script_fuera_de_src_da_2(entorno, tmp_path):
    fases = _tres_fases(entorno)
    otro = tmp_path / "otro.py"
    otro.write_text("print('no')")
    fases[0]["scripts"].append(str(otro))
    assert lanzador.main(["todo"], fases=fases, **entorno.opciones) == 2
    assert _ejecutadas(entorno) == []


def test_base_del_repo_exige_confirmar_si_se_escriben_tablas(entorno):
    fases = [entorno.fase("a", "a1"), entorno.fase("b", "b1", escribe_tablas=True)]
    opciones = dict(entorno.opciones, base=entorno.opciones["raiz_repo"])
    assert lanzador.main(["todo"], fases=fases, **opciones) == 2
    assert _ejecutadas(entorno) == []
    assert lanzador.main(["todo", "--confirmar"], fases=fases, **opciones) == 0
    assert _ejecutadas(entorno) == ["a1", "b1"]


def test_base_del_repo_sin_tablas_no_exige_confirmar(entorno):
    fases = [entorno.fase("a", "a1"), entorno.fase("b", "b1", escribe_tablas=True)]
    opciones = dict(entorno.opciones, base=entorno.opciones["raiz_repo"])
    assert lanzador.main(["--solo", "a"], fases=fases, **opciones) == 0


def test_respeta_pharmasignal_base(tmp_path):
    entorno_proc = dict(os.environ, PHARMASIGNAL_BASE=str(tmp_path))
    r = subprocess.run([sys.executable, str(RAIZ / "src" / "lanzador.py"), "--lista"],
                       capture_output=True, text=True, env=entorno_proc, timeout=60)
    assert r.returncode == 0
    assert f"Base: {tmp_path}" in r.stdout
    assert f"entrada: {tmp_path / 'data' / 'raw'}" in r.stdout
    # Base aparte: no pide --confirmar, pero la entrada no existe.
    assert "--confirmar" not in r.stdout
    assert "no existe o está vacía" in r.stdout


# --- Candado ----------------------------------------------------------------

def _lanzar_en_otro_proceso(entorno, fases, argv):
    """Lanza main() en un proceso aparte con las mismas opciones."""
    opciones = {k: str(v) if isinstance(v, Path) else v for k, v in entorno.opciones.items()}
    codigo = textwrap.dedent(f"""\
        import sys
        sys.path.insert(0, {str(RAIZ)!r})
        from src import lanzador
        sys.exit(lanzador.main({argv!r}, fases={fases!r}, **{opciones!r}))
    """)
    return subprocess.Popen([sys.executable, "-c", codigo], start_new_session=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _esperar(condicion, segundos=20):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.05)
    return False


def _vivo(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # Un zombi aún responde a kill 0: se mira su estado en /proc.
    try:
        estado = Path(f"/proc/{pid}/stat").read_text().split()[2]
    except FileNotFoundError:
        return False
    return estado != "Z"


def _pid_de(entorno, nombre):
    marca = entorno.marcas / nombre
    assert _esperar(lambda: marca.exists() and marca.read_text())
    return int(marca.read_text())


def test_candado_ocupado_da_75_sin_ejecutar_nada(entorno, capsys):
    lento = [entorno.fase("a", ("lento", "time.sleep(60)"))]
    rapido = [entorno.fase("b", "b1")]
    primero = _lanzar_en_otro_proceso(entorno, lento, ["todo"])
    try:
        _pid_de(entorno, "lento")
        assert lanzador.main(["todo"], fases=rapido, **entorno.opciones) == 75
        assert "Ya hay un lanzamiento en curso" in capsys.readouterr().err
        assert "fase=a" in Path(entorno.opciones["candado"]).read_text()
        assert not (entorno.marcas / "b1").exists()
    finally:
        os.killpg(primero.pid, signal.SIGKILL)
        primero.wait()
        os.kill(_pid_de(entorno, "lento"), signal.SIGKILL)


def test_candado_queda_libre_al_terminar(entorno):
    assert lanzador.main(["--solo", "a"], fases=_tres_fases(entorno), **entorno.opciones) == 0
    assert lanzador.main(["--solo", "b"], fases=_tres_fases(entorno), **entorno.opciones) == 0


def test_tras_kill_9_el_script_conserva_el_candado_hasta_terminar(entorno):
    lento = [entorno.fase("a", ("lento", "time.sleep(60)"))]
    rapido = [entorno.fase("b", "b1")]
    primero = _lanzar_en_otro_proceso(entorno, lento, ["todo"])
    hijo = _pid_de(entorno, "lento")
    os.killpg(primero.pid, signal.SIGKILL)
    primero.wait()
    try:
        # Lanzador muerto, script vivo: el candado sigue cogido.
        assert _vivo(hijo)
        assert lanzador.main(["todo"], fases=rapido, **entorno.opciones) == 75
    finally:
        os.kill(hijo, signal.SIGKILL)
    assert _esperar(lambda: not _vivo(hijo))
    # Sin nadie vivo, el candado queda libre aunque el fichero siga ahí.
    assert lanzador.main(["todo"], fases=rapido, **entorno.opciones) == 0
    assert Path(entorno.opciones["candado"]).exists()


@pytest.mark.parametrize("senal", [signal.SIGINT, signal.SIGTERM])
def test_ctrl_c_o_sigterm_paran_el_script_y_dan_130(entorno, senal):
    fases = [entorno.fase("a", ("lento", "time.sleep(60)"), "despues")]
    primero = _lanzar_en_otro_proceso(entorno, fases, ["todo"])
    hijo = _pid_de(entorno, "lento")
    primero.send_signal(senal)
    _, err = primero.communicate(timeout=30)
    assert primero.returncode == 130
    assert "--desde a" in err
    assert _esperar(lambda: not _vivo(hijo))
    assert not (entorno.marcas / "despues").exists()
    # Y el candado queda libre.
    assert lanzador.main(["--solo", "a"], fases=[entorno.fase("a", "otro")], **entorno.opciones) == 0


def test_script_que_ignora_sigterm_muere_con_sigkill_y_su_nieto_tambien(entorno):
    cuerpo = f"""\
        import signal, subprocess
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        nieto = subprocess.Popen([sys.executable, "-c",
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"])
        pathlib.Path({str(entorno.marcas)!r}, "nieto").write_text(str(nieto.pid))
        time.sleep(60)
    """
    fases = [entorno.fase("a", ("lento", cuerpo))]
    corto = entorno._replace(opciones=dict(entorno.opciones, espera=1))
    primero = _lanzar_en_otro_proceso(corto, fases, ["todo"])
    hijo = _pid_de(entorno, "lento")
    nieto = _pid_de(entorno, "nieto")
    primero.send_signal(signal.SIGINT)
    primero.communicate(timeout=30)
    assert primero.returncode == 130
    assert _esperar(lambda: not _vivo(hijo))
    assert _esperar(lambda: not _vivo(nieto))



# --- Candado y logs privados ------------------------------------------------

def test_log_solo_para_el_usuario(entorno):
    assert lanzador.main(["--solo", "a"], fases=_tres_fases(entorno), **entorno.opciones) == 0
    for log in Path(entorno.opciones["logs"]).iterdir():
        assert log.stat().st_mode & 0o777 == 0o600


def test_candado_enlace_simbolico_da_2_sin_tocar_el_destino(entorno, capsys):
    candado = Path(entorno.opciones["candado"])
    candado.parent.mkdir(mode=0o700)
    destino = entorno.tmp / "otro_fichero"
    destino.write_text("no tocar")
    candado.symlink_to(destino)
    assert lanzador.main(["--solo", "a"], fases=_tres_fases(entorno), **entorno.opciones) == 2
    assert "candado inseguro" in capsys.readouterr().err
    assert destino.read_text() == "no tocar"
    assert _ejecutadas(entorno) == []


def test_carpeta_del_candado_abierta_da_2(entorno):
    carpeta = Path(entorno.opciones["candado"]).parent
    carpeta.mkdir()
    carpeta.chmod(0o755)
    assert lanzador.main(["--solo", "a"], fases=_tres_fases(entorno), **entorno.opciones) == 2
    assert _ejecutadas(entorno) == []


def test_candado_con_permisos_abiertos_da_2(entorno):
    candado = Path(entorno.opciones["candado"])
    candado.parent.mkdir(mode=0o700)
    candado.write_text("")
    candado.chmod(0o644)
    assert lanzador.main(["--solo", "a"], fases=_tres_fases(entorno), **entorno.opciones) == 2
    assert _ejecutadas(entorno) == []
