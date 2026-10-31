"""Recorre la interfaz con AppTest de Streamlit y falla si alguna vista rompe.

Son los 12 recorridos que se hacían a mano desde la tarea 0.2: las 9 vistas
en español, la búsqueda «ozempic» en Inicio en los dos idiomas y la vista
Geográfico en inglés. Un recorrido falla si lanza una excepción o pinta un
st.error. No es una prueba de pytest porque necesita las tablas de datos
(las del repositorio o las de la demo dentro de la imagen) y tarda.

Uso: python scripts/comprobar_interfaz.py
Código de salida: 0 si los 12 pasan, 1 si falla alguno.
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "src" / "app" / "streamlit_app.py"
# Tiempo máximo por ejecución de la app; la primera carga lee las tablas Delta.
TIEMPO_MAX_S = 180

# streamlit run añade al sys.path la carpeta del script y AppTest no; sin esto
# no se encuentra consultas_explorador.
sys.path.insert(0, str(APP.parent))

# (nombre, zona, subapartado, idioma, búsqueda en Inicio)
RECORRIDOS = [
    ("Inicio", "inicio", None, "Español", None),
    ("Explorar · GLP-1", "explorar", "glp1", "Español", None),
    ("Explorar · COVID-19", "explorar", "covid", "Español", None),
    ("Explorar · Finasterida", "explorar", "fina", "Español", None),
    ("Geográfico", "tecnico", "geo", "Español", None),
    ("Señales", "tecnico", "senales", "Español", None),
    ("Temporal", "tecnico", "temporal", "Español", None),
    ("Conjuntos listos", "crear", "listos", "Español", None),
    ("Constructor", "crear", "constructor", "Español", None),
    ("Inicio · ozempic (es)", "inicio", None, "Español", "ozempic"),
    ("Inicio · ozempic (en)", "inicio", None, "English", "ozempic"),
    ("Geográfico (en)", "tecnico", "geo", "English", None),
]


def recorrer(zona, sub, idioma, busqueda):
    """Ejecuta un recorrido y devuelve la lista de fallos (vacía si va bien)."""
    at = AppTest.from_file(str(APP), default_timeout=TIEMPO_MAX_S)
    at.session_state["nav"] = (zona, sub)
    if busqueda:
        at.session_state["q_farmaco"] = busqueda
    at.run()
    if idioma != "Español":
        at.sidebar.radio[0].set_value(idioma).run()
    fallos = [f"excepción: {e.value}" for e in at.exception]
    fallos += [f"st.error: {e.value}" for e in at.error]
    return fallos


def main():
    total_fallos = 0
    for nombre, zona, sub, idioma, busqueda in RECORRIDOS:
        try:
            fallos = recorrer(zona, sub, idioma, busqueda)
        except Exception as e:  # el arnés también puede romper: cuenta como fallo
            fallos = [f"{type(e).__name__}: {e}"]
        estado = "OK" if not fallos else "FALLA"
        print(f"{estado:5}  {nombre}")
        for f in fallos:
            print(f"       {f[:300]}")
        total_fallos += bool(fallos)
    pasan = len(RECORRIDOS) - total_fallos
    print(f"\n{pasan}/{len(RECORRIDOS)} recorridos sin errores")
    return 0 if total_fallos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
