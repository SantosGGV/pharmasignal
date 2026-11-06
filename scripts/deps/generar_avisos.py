"""Genera THIRD_PARTY_NOTICES.md con la licencia de cada paquete bloqueado (0.10).

Saca las licencias de los metadatos que declara cada paquete con
`pip install --dry-run --report`, en un venv temporal fuera del repositorio y con
--no-deps e --ignore-installed. No instala nada ni baja ruedas: si pip empieza a
descargar una rueda completa, se corta y el script falla.

pyspark no tiene rueda en PyPI, solo un paquete fuente muy grande, así que su
licencia se lee del entorno activo, comprobando antes que la versión sea la fijada.

Se ejecuta a mano, con red, cada vez que cambie un bloqueo. tests/test_licencia.py
comprueba sin red que el fichero sigue coincidiendo con los bloqueos.

Uso: python scripts/deps/generar_avisos.py
Código de salida: 0 si lo escribe, 1 si falla pip o un dato no cuadra, 3 si pip
intenta descargar una rueda completa y 4 si hay una licencia que revisar en
requirements.txt o en requirements-interfaz.txt (entonces no escribe nada).
"""
import importlib.metadata
import json
import re
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
DESTINO = RAIZ / "THIRD_PARTY_NOTICES.md"
PRINCIPAL = "requirements.txt"
INTERFAZ = "requirements-interfaz.txt"
TRADUCCION = "requirements-traduccion.txt"

# Sin rueda en PyPI: la licencia se lee del entorno activo.
SIN_RUEDA = {"pyspark"}

PIN = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+)")
# Una rueda o un paquete fuente enteros; los .metadata no casan porque el nombre
# no termina en la extensión.
DESCARGA_COMPLETA = re.compile(r"Downloading \S+\.(?:whl|tar\.gz|zip)\s")
# Lista blanca: cada término de la licencia tiene que estar aquí entero, para que
# «MIT AND CC-BY-NC-4.0» o «BSD-4-Clause» no pasen por contener una palabra conocida.
TERMINO_COMPATIBLE = re.compile(
    r"MIT(?: License)?|MIT-CMU|0BSD|BSD(?: License)?|BSD-[23]-Clause"
    r"|3-Clause BSD License|BSD 3-Clause License"
    r"|Apache-2\.0|Apache Software License|Apache License 2\.0|LLVM-exception"
    r"|PSF-2\.0|Python Software Foundation License"
    r"|MPL-2\.0|Mozilla Public License 2\.0 \(MPL 2\.0\)"
    r"|ISC(?: License)?(?: \(ISCL\))?|Zlib|CC0-1\.0|Unlicense|HPND"
    r"|AGPL-3\.0(?:-only|-or-later)?|GNU Affero General Public License v3"
    r"(?: or later \(AGPLv3\+\))?",
    re.IGNORECASE)
SEPARADOR_TERMINOS = re.compile(r"\s+(?:AND|OR|WITH)\s+|\s+/\s+", re.IGNORECASE)
PROPIETARIA = re.compile(r"propriet|NVIDIA", re.IGNORECASE)
SIN_DECLARAR = "no declarada en los metadatos"
NO_LEGIBLE = "no legible en los metadatos"
# Los metadatos de PyPI son entrada externa y acaban en un Markdown versionado: solo
# pasan letras, números y esta puntuación, sin | [ ] < > ni acentos graves.
TEXTO_SEGURO = re.compile(r"[\w .,()/+-]+")
LONGITUD_MAX_LICENCIA = 300


class DescargaCompleta(RuntimeError):
    """pip ha empezado a bajar una rueda o un paquete fuente enteros."""


def normalizar(nombre):
    """Nombre canónico de un paquete (PEP 503)."""
    return re.sub(r"[-_.]+", "-", nombre).lower()


def leer_bloqueo(ruta):
    """Devuelve {nombre normalizado: versión} con los paquetes fijados del fichero."""
    fijados = {}
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        m = PIN.match(linea.strip())
        if m:
            fijados[normalizar(m[1])] = m[2]
    return fijados


def _sanear(licencia):
    """Devuelve la licencia si es texto seguro y de longitud razonable, o NO_LEGIBLE."""
    licencia = licencia.strip()
    if len(licencia) <= LONGITUD_MAX_LICENCIA and TEXTO_SEGURO.fullmatch(licencia):
        return licencia
    return NO_LEGIBLE


def licencia_de(expresion, clasificadores, texto):
    """Licencia legible: la expresión SPDX, si no los clasificadores y si no el texto."""
    if expresion:
        return _sanear(expresion)
    licencias = [c.split("::")[-1].strip() for c in clasificadores or []
                 if c.startswith("License")]
    if licencias:
        return _sanear(" / ".join(licencias))
    lineas = (texto or "").strip().splitlines()
    return _sanear(lineas[0][:80]) if lineas else SIN_DECLARAR


def clasificar(licencia):
    """«compatible» con AGPL-3.0, «propietaria» o «revisar» (decide una persona)."""
    if PROPIETARIA.search(licencia):
        return "propietaria"
    terminos = (t.strip().lstrip("(") for t in SEPARADOR_TERMINOS.split(licencia))
    todos = all(TERMINO_COMPATIBLE.fullmatch(t) or TERMINO_COMPATIBLE.fullmatch(t.rstrip(")"))
                for t in terminos)
    return "compatible" if todos else "revisar"


def es_de_nvidia(nombre, licencia):
    """Bibliotecas CUDA que arrastra torch: van en su propia tabla."""
    return (nombre.startswith("nvidia-") or nombre == "cuda-toolkit"
            or clasificar(licencia) == "propietaria")


def licencias_de_pip(pip, bloqueo, carpeta):
    """Devuelve {nombre: (versión, licencia)} de un bloqueo sin instalar nada."""
    fijados = leer_bloqueo(RAIZ / bloqueo)
    filtrado = Path(carpeta) / f"{bloqueo}.filtrado"
    filtrado.write_text(
        "".join(f"{n}=={v}\n" for n, v in fijados.items() if n not in SIN_RUEDA),
        encoding="utf-8")
    informe = Path(carpeta) / f"{bloqueo}.json"
    orden = [pip, "install", "--dry-run", "--ignore-installed", "--no-deps",
             "--only-binary=:all:", "--progress-bar", "off",
             "--report", str(informe), "-r", str(filtrado)]
    proceso = subprocess.Popen(orden, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    salida = []
    for linea in proceso.stdout:
        salida.append(linea)
        if DESCARGA_COMPLETA.search(linea):
            proceso.kill()
            raise DescargaCompleta(linea.strip())
    if proceso.wait() != 0:
        raise RuntimeError(f"pip falló con {bloqueo}: {''.join(salida[-3:])}")

    licencias = {}
    for paquete in json.loads(informe.read_text(encoding="utf-8"))["install"]:
        meta = paquete["metadata"]
        licencias[normalizar(meta["name"])] = (meta["version"], licencia_de(
            meta.get("license_expression"), meta.get("classifier"), meta.get("license")))
    for nombre in SIN_RUEDA & fijados.keys():
        meta = importlib.metadata.metadata(nombre)
        licencias[nombre] = (meta["Version"], licencia_de(
            meta.get("License-Expression"), meta.get_all("Classifier"), meta.get("License")))

    if {n: v for n, (v, _) in licencias.items()} != fijados:
        raise RuntimeError(f"Las versiones de {bloqueo} no coinciden con el bloqueo")
    return licencias


def _tabla(cabecera, filas):
    lineas = ["| " + " | ".join(cabecera) + " |",
              "| " + " | ".join("---" for _ in cabecera) + " |"]
    lineas += ["| " + " | ".join(fila) + " |" for fila in filas]
    return "\n".join(lineas)


def componer(principal, interfaz, traduccion):
    """Texto completo del fichero a partir de las licencias de los tres bloqueos."""
    tabla_principal = _tabla(
        ["Paquete", "Versión", "Licencia declarada", "En la imagen Docker"],
        [[n, v, lic, "Sí" if n in interfaz else "No"]
         for n, (v, lic) in sorted(principal.items())])
    tabla_traduccion = _tabla(
        ["Paquete", "Versión", "Licencia declarada"],
        [[n, v, lic] for n, (v, lic) in sorted(traduccion.items())
         if not es_de_nvidia(n, lic)])
    tabla_nvidia = _tabla(
        ["Paquete", "Versión", "Licencia declarada"],
        [[n, v, lic] for n, (v, lic) in sorted(traduccion.items())
         if es_de_nvidia(n, lic)])
    return f"""# Avisos de terceros

La licencia [AGPL-3.0-only](LICENSE) cubre solo el código de PharmaSignal. Los
paquetes y los datos de terceros conservan sus propias condiciones, que se recogen
aquí.

Fichero generado con `python scripts/deps/generar_avisos.py`: no se edita a mano.
Las licencias son las que declara cada paquete en sus metadatos.

## Paquetes de Python

Incluye `{PRINCIPAL}` ({len(principal)} paquetes) y `{INTERFAZ}` ({len(interfaz)}
paquetes, con las mismas versiones). Todas las licencias de esta tabla son
compatibles con la AGPL-3.0.

{tabla_principal}

## Entorno opcional de traducción

`{TRADUCCION}` ({len(traduccion)} paquetes) es el venv aparte de
`src/curacion/traducir_terminos.py`. Este entorno no se distribuye: no va ni en la
imagen Docker ni en el repositorio.

{tabla_traduccion}

### Bibliotecas CUDA de NVIDIA

`torch` arrastra las bibliotecas CUDA de NVIDIA, con licencia propietaria de NVIDIA.
Solo son dependencias de este entorno opcional y tampoco se distribuyen.

{tabla_nvidia}

## Datos

### FAERS y openFDA

Según los [términos de openFDA](https://open.fda.gov/terms/), su contenido es de
dominio público y se ofrece con la dedicación Creative Commons CC0 1.0 Universal,
salvo los datos marcados expresamente como no públicos. Se ofrece «tal cual», sin
garantías de ningún tipo: la FDA no garantiza que los datos estén libres de errores.

Una señal estadística es una hipótesis de trabajo, no una prueba de causalidad, y una
tasa de notificación no es una incidencia.

### MedDRA

MedDRA® es una marca registrada de la ICH. Los términos de reacción se usan tal como
vienen en FAERS. Este aviso no concede ningún derecho sobre MedDRA.

### Traducción de los términos

La traducción al español de los términos es automática, hecha con Argos Translate,
con un diccionario propio de correcciones (`data/diccionarios/terminos_es.txt`). No
es la traducción oficial de MedDRA al español.
"""


def main():
    with tempfile.TemporaryDirectory() as carpeta:
        entorno = Path(carpeta) / "venv"
        venv.create(entorno, with_pip=True)
        pip = str(entorno / "bin" / "pip")
        # El pip que trae el venv puede ser tan antiguo que ignore License-Expression.
        subprocess.run([pip, "install", "--quiet",
                        f"pip=={importlib.metadata.version('pip')}"], check=True)
        try:
            principal = licencias_de_pip(pip, PRINCIPAL, carpeta)
            interfaz = licencias_de_pip(pip, INTERFAZ, carpeta)
            traduccion = licencias_de_pip(pip, TRADUCCION, carpeta)
        except DescargaCompleta as e:
            print(f"Parado: pip intenta descargar una rueda completa: {e}")
            return 3
        except RuntimeError as e:
            print(e)
            return 1

    a_revisar = sorted((n, lic) for lote in (principal, interfaz)
                       for n, (_, lic) in lote.items()
                       if clasificar(lic) != "compatible")
    if a_revisar:
        print("Licencias que revisar; no se escribe nada:")
        for nombre, licencia in a_revisar:
            print(f"  {nombre}: {licencia}")
        return 4
    for nombre, (_, licencia) in sorted(traduccion.items()):
        if not es_de_nvidia(nombre, licencia) and clasificar(licencia) != "compatible":
            print(f"Aviso, entorno de traducción: {nombre}: {licencia}")

    DESTINO.write_text(componer(principal, interfaz, traduccion), encoding="utf-8")
    print(f"{DESTINO.name}: {len(principal)} + {len(interfaz)} + {len(traduccion)} paquetes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
