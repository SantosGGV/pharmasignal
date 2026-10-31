#!/usr/bin/env python3
"""Hooks SessionStart (modo inicio) y SessionEnd (modo fin): rastro de cada sesión, sin IA.

inicio: guarda en $PHARMASIGNAL_PRIVADO/sesiones/estado/<sid>.json la raíz, la
rama, el HEAD, la fecha y los ficheros que ya estaban sucios con su hash.
Cierra como «sesión sin cierre» los estados de otras sesiones con más de
HORAS_SIN_CIERRE horas (las que murieron sin SessionEnd) y avisa de las marcas
pendientes, borrando las que ya tienen su entrada de bitácora.

fin: compara con el estado y escribe sesiones/AAAA-MM-DD_<rama>_<sid>.md con
los commits y los ficheros tocados. Si tocó algo fuera de docs/ y no hay
entrada de bitácora, deja una marca en sesiones/pendientes/.

Las horas de inicio y fin solo van a horas_sesiones.csv, con la lectura
denegada en settings.json: nada de lo que lee Claude lleva horas. Siempre sale
con 0, porque un fallo del rastro no debe cortar la sesión.
"""
import datetime
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from exigir_bitacora import git, hay_entrada, rutas_fuera_de_docs, rutas_sucias  # noqa: E402

HORAS_SIN_CIERRE = 24
SIN_CIERRE = "sesión sin cierre"


def carpeta_privada(raiz):
    """La carpeta privada, o None si falta, no es absoluta o cae dentro del repositorio."""
    valor = os.environ.get("PHARMASIGNAL_PRIVADO", "")
    if not valor or not os.path.isabs(valor) or not os.path.isdir(valor):
        return None
    privada = pathlib.Path(valor).resolve()
    if raiz and privada.is_relative_to(pathlib.Path(raiz).resolve()):
        print("Aviso: PHARMASIGNAL_PRIVADO está dentro del repositorio; no se guarda el rastro.", file=sys.stderr)
        return None
    return privada


def limpio(texto, largo=None):
    """Solo letras, cifras, punto, guion y guion bajo, para nombres de fichero y para el CSV."""
    texto = re.sub(r"[^A-Za-z0-9._-]+", "-", texto or "").strip("-")
    return texto[:largo] if largo else texto


def carpeta(ruta):
    ruta.mkdir(mode=0o700, parents=True, exist_ok=True)
    return ruta


def escribir(ruta, texto):
    """Escribe con permisos 0600."""
    descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as fichero:
        fichero.write(texto)


def apuntar_hora(privada, *campos, momento=None):
    """Añade una línea a horas_sesiones.csv, el único fichero con horas."""
    momento = momento or datetime.datetime.now().astimezone()
    linea = ",".join([campos[0], momento.isoformat(timespec="seconds"), *(limpio(c) for c in campos[1:])])
    descriptor = os.open(privada / "horas_sesiones.csv", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as fichero:
        fichero.write(linea + "\n")


def huella(raiz, ruta):
    """Hash git del fichero tal como está, o None si ya no existe."""
    if not (pathlib.Path(raiz) / ruta).is_file():
        return None
    salida = git(["hash-object", "--", ruta], raiz)
    return salida.strip() if salida else None


def rama_de(raiz):
    return (git(["branch", "--show-current"], raiz) or "").strip()


def ruta_estado(privada, sid):
    return privada / "sesiones" / "estado" / f"{sid}.json"


def leer_estado(privada, sid):
    try:
        return json.loads(ruta_estado(privada, sid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def guardar_estado(privada, sid, estado):
    escribir(carpeta(privada / "sesiones" / "estado") / f"{sid}.json", json.dumps(estado, ensure_ascii=False, indent=1))


def cerrar(privada, sid, estado, raiz, motivo, fecha_fin):
    """Escribe el rastro de la sesión y, si hace falta, su marca. Devuelve el nombre del rastro."""
    raiz = (estado or {}).get("raiz") or raiz
    rama_inicio = (estado or {}).get("rama", "")
    fecha_inicio = (estado or {}).get("fecha", fecha_fin)
    hay_repo = bool(raiz) and pathlib.Path(raiz).is_dir() and git(["rev-parse", "HEAD"], raiz) is not None
    rama_fin = rama_de(raiz) if hay_repo else ""
    commits, tocados = [], set()
    if hay_repo:
        head = (estado or {}).get("head")
        if head:
            commits = (git(["log", "--format=%h %s", f"{head}..HEAD"], raiz) or "").splitlines()
            tocados.update((git(["diff", "--name-only", "--no-renames", head, "HEAD"], raiz) or "").splitlines())
        iniciales = (estado or {}).get("sucios", {})
        en_commits = set(tocados)
        for ruta in rutas_sucias(raiz) or []:
            if ruta in iniciales and ruta not in en_commits and huella(raiz, ruta) == iniciales[ruta]:
                continue
            tocados.add(ruta)
    tocados = sorted(t for t in tocados if t)
    fechas = sorted({fecha_inicio, fecha_fin})
    rama_nombre = rama_inicio or rama_fin
    con_entrada = hay_repo and any(hay_entrada(raiz, rama_nombre, f) for f in fechas)
    lineas = [
        f"# Rastro de la sesión {sid}",
        "",
        f"- Fecha: {fecha_inicio}" + (f" (fin: {fecha_fin})" if fecha_fin != fecha_inicio else ""),
        f"- Rama: {rama_inicio or 'sin rama'} al empezar; {rama_fin or 'sin rama'} al terminar",
        f"- Cierre: {motivo}",
        f"- Entrada de bitácora de esas fechas: {'sí' if con_entrada else 'no'}",
        "",
        "## Commits",
        *([f"- {c}" for c in commits] or ["- ninguno" if estado else "- sin estado de inicio"]),
        "",
        "## Ficheros tocados",
        *([f"- {t}" for t in tocados] or ["- ninguno"]),
        "",
    ]
    nombre = f"{fecha_inicio}_{limpio(rama_nombre) or 'sin-rama'}_{sid}.md"
    escribir(carpeta(privada / "sesiones") / nombre, "\n".join(lineas))
    if rutas_fuera_de_docs(tocados) and not con_entrada:
        marca = {"rastro": nombre, "raiz": raiz, "rama": rama_nombre, "fechas": fechas}
        escribir(carpeta(privada / "sesiones" / "pendientes") / f"{nombre[:-3]}.json", json.dumps(marca, ensure_ascii=False))
    return nombre


def cerrar_huerfanos(privada, sid_actual, raiz):
    """Cierra los estados de otras sesiones que llevan más de HORAS_SIN_CIERRE horas sin SessionEnd."""
    limite = datetime.datetime.now().timestamp() - HORAS_SIN_CIERRE * 3600
    for ruta in sorted((privada / "sesiones" / "estado").glob("*.json")):
        sid = ruta.stem
        if sid == sid_actual or ruta.stat().st_mtime > limite:
            continue
        estado = leer_estado(privada, sid)
        ultima = datetime.datetime.fromtimestamp(ruta.stat().st_mtime).astimezone()
        cerrar(privada, sid, estado, raiz, SIN_CIERRE, ultima.date().isoformat())
        apuntar_hora(privada, "fin", sid, (estado or {}).get("rama", ""), "sin_cierre", momento=ultima)
        ruta.unlink()
        print(f"Aviso: la sesión {sid} no llegó a cerrarse; su rastro queda como «{SIN_CIERRE}».")


def avisar_pendientes(privada, raiz):
    """Borra las marcas ya resueltas y avisa de las que siguen sin entrada de bitácora."""
    for ruta in sorted((privada / "sesiones" / "pendientes").glob("*.json")):
        try:
            marca = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        donde = marca.get("raiz") if pathlib.Path(marca.get("raiz") or "").is_dir() else raiz
        if donde and any(hay_entrada(donde, marca.get("rama"), f) for f in marca.get("fechas", [])):
            ruta.unlink()
            continue
        fecha = (marca.get("fechas") or ["?"])[0]
        print(
            f"Aviso: la sesión del {fecha} en {marca.get('rama') or 'sin rama'} tocó código y no tiene bitácora. "
            f"Lee el rastro {privada / 'sesiones' / marca.get('rastro', '?')} y pásaselo al documentador."
        )


def inicio(datos, privada, raiz, sid):
    hoy = datetime.date.today().isoformat()
    origen = str(datos.get("source") or "startup")
    carpeta(privada / "sesiones" / "estado")
    cerrar_huerfanos(privada, sid, raiz)
    estado = leer_estado(privada, sid)
    if estado is None and raiz:
        sucios = {r: huella(raiz, r) for r in rutas_sucias(raiz) or []}
        estado = {"raiz": raiz, "rama": rama_de(raiz), "head": (git(["rev-parse", "HEAD"], raiz) or "").strip(),
                  "fecha": hoy, "sucios": sucios}
    if estado is not None:
        guardar_estado(privada, sid, estado)  # también renueva la fecha de modificación al reanudar
    if origen != "compact":
        apuntar_hora(privada, "inicio", sid, (estado or {}).get("rama", ""), origen)
    avisar_pendientes(privada, raiz)


def fin(datos, privada, raiz, sid):
    estado = leer_estado(privada, sid)
    motivo = limpio(str(datos.get("reason") or "other"))
    cerrar(privada, sid, estado, raiz, motivo, datetime.date.today().isoformat())
    apuntar_hora(privada, "fin", sid, (estado or {}).get("rama", "") or rama_de(raiz), motivo)
    ruta_estado(privada, sid).unlink(missing_ok=True)


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        datos = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if modo not in ("inicio", "fin") or not isinstance(datos, dict):
        return 0
    raiz = (git(["rev-parse", "--show-toplevel"], datos.get("cwd") or ".") or "").strip()
    privada = carpeta_privada(raiz)
    if privada is None:
        return 0
    sid = limpio(str(datos.get("session_id") or ""), 8) or "sin-id"
    try:
        (inicio if modo == "inicio" else fin)(datos, privada, raiz, sid)
    except OSError as error:
        print(f"Aviso: no se pudo guardar el rastro de la sesión ({error.strerror}).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
