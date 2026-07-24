"""
streamlit_app.py

Se trata del Frontend de PharmaSignal.

Navegación en acordeón (sección → subapartados)
Bilingüe ES/EN.
Datos de país y traducción de términos se cargan desde ficheros externos
en data/diccionarios/ (paises.txt, terminos_es.txt), sin nada incrustado en el
código.
Los resultados se leen desde Delta Lake.

Ejecución:  streamlit run src/app/streamlit_app.py
"""

# NOTA SOBRE STREAMLIT (importante para entender como funciona el código):
# Streamlit no funciona como una web normal. Cada vez que se toca un
# botón, un slider o cambias de idioma, vuelve a ejecutar este fichero entero, de
# arriba a abajo, como si lo lanzaras de cero. Por eso hay que tener cuidado con
# releer datos pesados (de ahí el caché).

import os

import numpy as np
import pandas as pd
import plotly.express as px          # px = atajos rápidos para gráficas típicas
import plotly.graph_objects as go    # go = control fino cuando px se queda corto
import streamlit as st
from deltalake import DeltaTable     # lee tablas Delta sin necesidad de Spark

# CONFIGURACIÓN GLOBAL
# expanduser convierte el "~" en la ruta real del home, así funciona sin tocar
# nada aunque cambie el usuario de la máquina.
CURATED = os.path.expanduser("~/pharmasignal/data/curated")
DICC_DIR = os.path.expanduser("~/pharmasignal/data/diccionarios")

# Paleta de la app en un único sitio: si algún día quiero cambiar el azul, lo
# cambio aquí.
BLUE = "#4F9BE8"
NAVY = "#2E75B6"
BLUE_SOFT = "#2E5E8C"
INK = "#E6EAF0"        # color del texto principal (casi blanco)
SOFT = "#8A97A8"       # texto secundario, gris apagado
GRID = "#262D3A"       # líneas de la rejilla de las gráficas
POS = "#4F9BE8"        # azul para "a favor" / sobrerrepresentado
NEG = "#E8746E"        # rojo para "en contra" / infrarrepresentado
BG = "#0E1117"         # fondo oscuro
COLORWAY = ["#4F9BE8", "#E8746E", "#7FB3E8", "#2E75B6", "#9EC9F0",
            "#C0894D", "#6FCF97", "#B07FE8"]   # ciclo de colores para series

# set_page_config TIENE que ser lo primero de Streamlit que se ejecuta, si no,
# protesta. layout="wide" usa todo el ancho; el sidebar arranca abierto.
st.set_page_config(page_title="PharmaSignal", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")


def logo_svg(px=42):
    # El logo lo dibujo yo con SVG en vez de meter un PNG: así escala sin
    # pixelarse y no dependo de un fichero de imagen. Me dio muchos problemas al inicio
    # ya que lo introduje en formato imagen, finalmente decidí generarlo con un SVG.
    return (f"<svg width='{px}' height='{px}' viewBox='0 0 44 44' fill='none' "
            "xmlns='http://www.w3.org/2000/svg'>"
            "<rect x='1.5' y='1.5' width='41' height='41' rx='11' fill='#16233A' "
            "stroke='#2E75B6' stroke-width='1.6'/>"
            "<polyline points='7,25 14,25 18,15 23,31 27,21 31,25 37,25' "
            "fill='none' stroke='#4F9BE8' stroke-width='2.4' "
            "stroke-linecap='round' stroke-linejoin='round'/>"
            "<circle cx='23' cy='31' r='2.6' fill='#E8746E'/></svg>")


# LATERAL: LOGO + IDIOMA
# Todo lo que cuelgue de st.sidebar aparece en la barra de la izquierda.
# unsafe_allow_html=True hace falta porque le estoy metiendo HTML/SVG a mano como explico justo arriba
# Streamlit por defecto escapa el HTML por seguridad.
st.sidebar.markdown(
    f"<div style='display:flex;align-items:center;gap:10px;margin:0 0 12px 0;'>"
    f"{logo_svg(30)}<span style='font-size:1.2rem;font-weight:700;color:{INK};'>"
    f"PharmaSignal</span></div>", unsafe_allow_html=True)
st.sidebar.divider()

# Selector de idioma.
st.sidebar.markdown("### Idioma / Language")
_idioma = st.sidebar.radio("idioma", ["Español", "English"],
                           horizontal=True, label_visibility="collapsed")
L = "es" if _idioma == "Español" else "en"


def t(es, en):
    # Atajo de traducción
    return es if L == "es" else en


st.sidebar.divider()

# CSS propio creado a mano. Streamlit no deja tocar estos estilos desde
# Python, así que la única alternativa que me queda era meter un <style> con los selectores internos
st.markdown(
    """
    <style>
        .block-container { padding-top: 2.8rem; padding-bottom: 2rem;
                           max-width: 1320px; }
        [data-testid="stMetric"] {
            background: #1A2332; border: 1px solid #2A3342;
            border-radius: 12px; padding: 16px 20px;
        }
        [data-testid="stMetricValue"] { font-size: 1.55rem; font-weight: 600;
                                        color: #7FB3E8; }
        [data-testid="stMetricLabel"] { color: #8A97A8; }
        h1, h2, h3, h4 { letter-spacing: -0.01em; color: #E6EAF0; }
        .stDataFrame { border: 1px solid #2A3342; border-radius: 10px; }
        hr { margin: 1.0rem 0; border-color: #2A3342; }
        [data-testid="stSpinner"] p { font-size: 1.05rem; color: #7FB3E8; }
        .intro { color:#9AA7B6; font-size:0.9rem; border-left:3px solid #2E75B6;
                 padding:7px 0 7px 12px; margin:0 0 16px 0;
                 background:rgba(46,117,182,0.06); border-radius:0 8px 8px 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Opciones de la barra de herramientas de Plotly. Quito el logo y las
# herramientas que aquí no aportan, y dejo que la descarga
# de PNG salga al doble de resolución para que se vea nítida.
PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}

# Diccionario de las familias de fármacos que se pueden explorar. Cada entrada
# trae la etiqueta que se muestra, el nombre de la serie temporal asociada
# y la lista de nombres de fármaco por los que filtro. La lista
# incluye tanto el principio activo como las marcas comerciales, porque en FAERS
# la gente los notifica de las dos formas.
FAMILIAS = {
    "glp1": {"label": "GLP-1 (Ozempic, Wegovy, Mounjaro…)",
             "serie": "reportes_glp1",
             "drugs": ["semaglutide", "ozempic", "wegovy", "rybelsus",
                       "tirzepatide", "mounjaro", "zepbound", "liraglutide",
                       "saxenda", "victoza", "dulaglutide", "trulicity",
                       "exenatide"]},
    "covid": {"label": "COVID-19 (Paxlovid, Remdesivir…)",
              "serie": "reportes_covid",
              "drugs": ["paxlovid", "nirmatrelvir", "remdesivir", "veklury",
                        "molnupiravir", "lagevrio", "hydroxychloroquine"]},
    "fina": {"label": "Finasterida (Propecia, Proscar)", "serie": None,
             "drugs": ["finasteride", "propecia", "proscar"]},
}

# Códigos de desenlace de FAERS traducidos. Es un conjunto pequeño y cerrado, no
# hace falta sacarlo a fichero externo como los otros diccionarios.
OUTC_ES = {"DE": "Muerte", "LT": "Riesgo vital", "HO": "Hospitalización",
           "DS": "Discapacidad", "CA": "Anomalía congénita",
           "RI": "Intervención requerida", "OT": "Otro"}


# CARGA DE DATOS Y DE LOS DICCIONARIOS
# @st.cache_data es la pieza clave de rendimiento del fronten. Como mencionaba al principio
# el script se reejecuta entero en cada clic, sin caché volvería a leer el Delta una y otra vez.
# Con el decorador, Streamlit guarda el resultado y solo vuelve a leer si
# cambian los argumentos de la función.
@st.cache_data(show_spinner=False)
def cargar(tabla: str):
    ruta = f"{CURATED}/{tabla}"
    if not os.path.isdir(ruta):
        return None                      # tabla que aún no existe → aviso luego
    try:
        return DeltaTable(ruta).to_pandas()   # Delta → DataFrame de pandas
    except Exception:
        return None                      # si algo falla, prefiero None a que falle


@st.cache_data(show_spinner=False)
def cargar_diccionario_txt(nombre):
    """Lee un diccionario 'en|es' desde un .txt de data/diccionarios/."""
    # OJO, esta primera versión está cacheada. Justo debajo la vuelvo a definir
    # SIN caché y esa segunda es la que manda (Python se queda con la última).
    # La dejo documentada para acordarme de por qué hay dos.
    ruta = os.path.join(DICC_DIR, nombre)
    d = {}
    if not os.path.isfile(ruta):
        return d
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            # Ignoro líneas vacías, comentarios (#) y las que no tengan el "|".
            if not linea or linea.startswith("#") or "|" not in linea:
                continue
            en, es = linea.split("|", 1)
            d[en.strip().lower()] = es.strip()
    return d


def cargar_diccionario_txt(nombre):
    """Lee 'en|es' desde un .txt. SIN caché: recoge tus ediciones al recargar."""
    # Esta es la que de verdad se usa. La quiero sin caché a propósito, así,
    # mientras voy ampliando el diccionario a mano, basta con recargar la página
    # para ver los términos nuevos, sin tener que limpiar la caché de Streamlit.
    ruta = os.path.join(DICC_DIR, nombre)
    d = {}
    if not os.path.isfile(ruta):
        return d
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "|" not in linea:
                continue
            en, es = linea.split("|", 1)
            d[en.strip().lower()] = es.strip()
    return d


def cargar_paises():
    # El fichero paises.txt tiene 4 campos por línea que he querido segmentarlo por codigo|iso3|nombre_es|nombre_en
    # Devuelvo dos diccionarios. Uno para pasar del código de 2 letras al ISO3
    # (que es lo que necesita el mapa) y otro con los nombres en los dos idiomas.
    ruta = os.path.join(DICC_DIR, "paises.txt")
    iso3, nombres = {}, {}
    if not os.path.isfile(ruta):
        return iso3, nombres
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "|" not in linea:
                continue
            partes = [p.strip() for p in linea.split("|")]
            if len(partes) < 4:
                continue                   # línea mal formada → la salto
            cod, i3, es, en = partes[0], partes[1], partes[2], partes[3]
            if i3:
                iso3[cod] = i3
            nombres[cod] = (es, en)
    return iso3, nombres


# Estos dos diccionarios los cargo una sola vez al arrancar y los dejo como
# globales, porque los consulto desde muchas funciones distintas.
ISO2_A_ISO3, NOMBRE_PAIS = cargar_paises()


@st.cache_data(show_spinner=False)
def cargar_trad_delta():
    """Traducción automática"""
    # Aparte del diccionario manual, hay una tabla Delta con traducciones
    # generadas automáticamente (argos-translate) mencionada en el stack de la memoria.
    # Si existe y trae las columnas esperadas, la convierto en un dict term_en → term_es.
    ext = cargar("trad_terminos")
    if ext is not None and {"term_en", "term_es"} <= set(ext.columns):
        return dict(zip(ext["term_en"].astype(str).str.lower(),
                        ext["term_es"].astype(str)))
    return {}


def cargar_traduccion():
    # Fusiono las dos fuentes. Primero la automática (Delta) como base y encima
    # el .txt manual. Así puedo corregir a mano cualquier
    # traducción automática que no me guste sin tocar la tabla Delta.
    d = dict(cargar_trad_delta())
    d.update(cargar_diccionario_txt("terminos_es.txt"))
    return d


TRAD = cargar_traduccion()


def tr_terms(serie):
    """Traduce una columna de términos al español"""
    # Si estoy en inglés o no hay diccionario, devuelvo la serie tal cual.
    # Si no, mapeo cada término a su traducción y, para los que no encuentre,
    # fillna deja el original en vez de un hueco vacío.
    if L != "es" or not TRAD:
        return serie
    return serie.astype(str).str.lower().map(TRAD).fillna(serie)


# UTILIDADES
def aviso_tabla(nombre_tabla: str, script: str):
    # Mensaje unificado para cuando falta una tabla. Le digo al usuario qué
    # script tiene que ejecutar para generarla. Así la app no se rompe si el
    # pipeline aún no ha corrido del todo.
    st.warning(t(f"La tabla **{nombre_tabla}** aún no está disponible. Ejecuta "
                 f"`{script}` y recarga.",
                 f"Table **{nombre_tabla}** is not available yet. Run "
                 f"`{script}` and reload."))


def intro(txt):
    # Pinta el recuadrito de introducción (la clase .intro del CSS de arriba).
    st.markdown(f"<div class='intro'>{txt}</div>", unsafe_allow_html=True)


def overlay_cargando(ph, msg):
    """Bloque de carga a pantalla completa (se limpia con ph.empty())."""
    # Detalle que quier mencionar, como algunas gráficas del constructor tardan, pinto una capa fija
    # que tapa toda la pantalla con un "cargando". El 'ph' es un st.empty() que
    # me paso desde fuera, cuando termino, lo vacío y la capa desaparece.
    ph.markdown(
        f"<div style='position:fixed;inset:0;background:rgba(14,17,23,0.80);"
        f"z-index:9999;display:flex;align-items:center;justify-content:center;'>"
        f"<div style='background:#1A2332;border:1px solid #2E75B6;"
        f"border-radius:14px;padding:24px 38px;color:#E6EAF0;font-size:1.15rem;"
        f"box-shadow:0 10px 40px rgba(0,0,0,0.5);'>⏳ {msg}</div></div>",
        unsafe_allow_html=True)


def nombre_pais(codigo):
    # Del código de país al nombre legible en el idioma actual. Si no lo tengo
    # en el diccionario, devuelvo el propio código para no perder el dato.
    tup = NOMBRE_PAIS.get(codigo)
    if not tup:
        return codigo
    return tup[0] if L == "es" else tup[1]


def con_nombre_pais(df, col="reporter_country"):
    # Añade al DataFrame una columna "pais" con el nombre legible, dejando la
    # original intacta. copy() para no modificar el DataFrame cacheado por
    # detrás (si tocara el original, corrompería la caché).
    out = df.copy()
    out["pais"] = out[col].map(nombre_pais).fillna(out[col])
    return out


def estilo_plotly(fig, alto=430):
    """Fondo sólido para que las descargas que realicen los usuarios en (PNG/HTML) salgan también en oscuro."""
    # Todas las gráficas pasan por aquí para quedar homogéneas: tema oscuro,
    # márgenes ajustados y mi paleta. Pongo el fondo sólido (no transparente) a propósito, para que cuando el usuario se
    # descargue el PNG/HTML no salga con fondo blanco cantoso. Por defecto no se veían nada bien al tener fondo blanco.
    fig.update_layout(
        height=alto, margin=dict(l=10, r=10, t=30, b=10),
        template="plotly_dark", colorway=COLORWAY,
        plot_bgcolor=BG, paper_bgcolor=BG,
        font=dict(family="Arial, sans-serif", size=12, color=INK),
        hoverlabel=dict(bgcolor="#1A2332", bordercolor=BLUE,
                        font=dict(size=15, color=INK, family="Arial")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0))
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def eje_paises_grande(fig):
    # En las barras horizontales de países las etiquetas del eje Y se quedaban
    # pequeñas, esto solo las agranda un poco. Función aparte porque lo repito.
    fig.update_yaxes(tickfont=dict(size=13))
    return fig


def mostrar(fig, key=None):
    # Envoltorio para no repetir siempre los mismos parámetros de plotly_chart.
    # El 'key' es un identificador único que Streamlit exige cuando hay varias
    # gráficas, si dos comparten key, la herramienta se lía. Por eso voy pasando keys distintas.
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=key)


def boton_csv(df, nombre):
    # Botón de descarga de CSV. Streamlit necesita los bytes ya codificados,
    # de ahí el .encode("utf-8").
    st.download_button("⬇ CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name=nombre, mime="text/csv", key="csv_" + nombre)


def boton_html(fig, nombre):
    # Descarga la gráfica como HTML interactivo. include_plotlyjs="cdn" hace que
    # el fichero no lleve toda la librería Plotly dentro (pesa menos) y la cargue
    # desde internet al abrirlo.
    st.download_button(
        t("⬇ Gráfica (HTML)", "⬇ Chart (HTML)"),
        fig.to_html(include_plotlyjs="cdn").encode("utf-8"),
        file_name=nombre, mime="text/html", key="html_" + nombre)


def fig_mapa(perfil):
    # Mapa mundial. Necesita el código ISO3, así que primero mapeo
    # desde el ISO2 y descarto los países que no consiga traducir.
    # Por defecto se visualizaba el nombre del país completo, con esto
    # se logra visualizar "ES" en vez de "ESPAÑA". Para algunos países
    # con nombre extenso no llegaba a visualizarse.
    mapa = con_nombre_pais(perfil)
    mapa["iso3"] = mapa["reporter_country"].map(ISO2_A_ISO3)
    mapa = mapa.dropna(subset=["iso3"])
    # Coloreo por el logaritmo de los reportes, no por el valor bruto: EE.UU.
    # aplasta a todos los demás y sin escala log el mapa saldría entero.
    # El colorbar de abajo vuelve a poner las etiquetas en la escala real (10, 100, 1K…) para que se entienda.
    mapa["log_reportes"] = np.log10(mapa["reportes"].clip(lower=1))
    fig = px.choropleth(
        mapa, locations="iso3", color="log_reportes", hover_name="pais",
        hover_data={"reportes": ":,", "log_reportes": False, "iso3": False},
        color_continuous_scale=["#16324F", "#2E75B6", "#7FB3E8"])
    fig.update_layout(
        height=460, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor=BG, font=dict(color=INK, size=13),
        hoverlabel=dict(bgcolor="#1A2332", bordercolor=BLUE,
                        font=dict(size=15, color=INK)),
        geo=dict(bgcolor=BG, showframe=False, showcoastlines=False,
                 showland=True, landcolor="#1A2332",
                 projection_type="natural earth"),
        coloraxis_colorbar=dict(
            title=t("Reportes", "Reports"), tickvals=[1, 2, 3, 4, 5, 6],
            ticktext=["10", "100", "1K", "10K", "100K", "1M"]))
    return fig


def panel_divergencia(div, columna, etiqueta):
    # Pinta las dos barras enfrentadas (sobre / infra representado en España).
    # Reutilizo la misma función para fármacos y para reacciones cambiando la
    # columna y la etiqueta.
    if div is None:
        aviso_tabla(f"geo_divergencia_{etiqueta}", "analisis_geografico.py")
        return
    # Me quedo solo con las divergencias marcadas como significativas
    sig = div[div["significativo"]].copy() if "significativo" in div else div.copy()
    if not len(sig):
        st.info(t("No hay divergencias estadísticamente sostenibles.",
                  "No statistically robust divergences found."))
        return
    ycol = columna
    # Si el eje son reacciones (pt_norm), las traduzco a una columna "disp"
    # para mostrarlas en español.
    if columna == "pt_norm":
        sig["disp"] = tr_terms(sig["pt_norm"])
        ycol = "disp"
    # st.columns(2) parte la pantalla en dos. 'with d1:' dirige lo que pinto a
    # la columna izquierda y 'with d2:' a la derecha.
    d1, d2 = st.columns(2, gap="large")
    with d1:
        st.markdown("**" + t("Sobrerrepresentados en España",
                             "Over-represented in Spain") + "**")
        sob = sig.nlargest(12, "ratio")            # los 12 de ratio más alto
        fig = px.bar(sob.sort_values("ratio"), x="ratio", y=ycol,
                     orientation="h",
                     labels={"ratio": t("Ratio ES / global", "ES / global ratio"),
                             ycol: ""})
        fig.update_traces(marker_color=POS)
        fig = estilo_plotly(fig, 380)
        fig.add_vline(x=1, line_dash="dash", line_color=SOFT)   # línea en ratio=1
        mostrar(eje_paises_grande(fig), key="div_sob_" + etiqueta)
    with d2:
        st.markdown("**" + t("Infrarrepresentados en España",
                             "Under-represented in Spain") + "**")
        inf = sig.nsmallest(12, "ratio")           # los 12 de ratio más bajo
        fig = px.bar(inf.sort_values("ratio", ascending=False), x="ratio",
                     y=ycol, orientation="h",
                     labels={"ratio": t("Ratio ES / global", "ES / global ratio"),
                             ycol: ""})
        fig.update_traces(marker_color=NEG)
        fig = estilo_plotly(fig, 380)
        fig.add_vline(x=1, line_dash="dash", line_color=SOFT)
        mostrar(eje_paises_grande(fig), key="div_inf_" + etiqueta)


# CABECERA
# Cabecera principal de la página (logo grande + título + subtítulo), otra vez
# con HTML a mano para tener el control del layout como mencionaba antes.
st.markdown(
    f"<div style='display:flex;align-items:center;gap:14px;"
    f"margin:0.2rem 0 0.7rem 0;'>{logo_svg(42)}"
    f"<div style='display:flex;flex-direction:column;justify-content:center;'>"
    f"<span style='font-size:1.8rem;font-weight:700;color:{INK};"
    f"line-height:1.25;'>PharmaSignal</span>"
    f"<span style='color:{SOFT};font-size:1.0rem;line-height:1.2;'>"
    f"{t('Detección de señales de farmacovigilancia · FAERS 2020–2025', 'Pharmacovigilance signal detection · FAERS 2020–2025')}"
    f"</span></div></div>", unsafe_allow_html=True)

# NAVEGACIÓN (sección con subapartados)
# Aquí está el corazón del "estado" que sobrevive a los reruns. Guardo en
# session_state una tupla (zona, subapartado) que dice dónde está el usuario.
# La primera vez que se abre la app, la inicializo en Inicio.
if "nav" not in st.session_state:
    st.session_state["nav"] = ("inicio", None)
zona, sub = st.session_state["nav"]

st.sidebar.markdown("### " + t("Navegación", "Navigation"))


def _item(cont, label, z, s=None):
    # Cada botón del menú. 'cont' es dónde lo pinto (el sidebar o un expander).
    # Comparo con la zona/sub actuales para saber si este item es el activo y
    # así resaltarlo.
    activo = (z, s) == (zona, sub)
    if cont.button(("●  " if activo else "◦  ") + label,
                   use_container_width=True,
                   type="primary" if activo else "secondary",
                   key=f"nav_{z}_{s}"):
        # Si lo pulsan, actualizo el estado y fuerzo un rerun para repintar ya
        # con la nueva sección seleccionada. Sin el rerun tardaría un clic en
        # reaccionar.
        st.session_state["nav"] = (z, s)
        st.rerun()


# Menú: Inicio suelto y las otras tres zonas dentro de expanders.
# Cada expander se abre solo si estás dentro de esa zona.
_item(st.sidebar, t("Inicio", "Home"), "inicio")

_exp_e = st.sidebar.expander("" + t("Explorar", "Explore"),
                             expanded=(zona == "explorar"))
_item(_exp_e, "GLP-1", "explorar", "glp1")
_item(_exp_e, "COVID-19", "explorar", "covid")
_item(_exp_e, t("Finasterida", "Finasteride"), "explorar", "fina")

_exp_t = st.sidebar.expander("" + t("Análisis técnico", "Technical analysis"),
                             expanded=(zona == "tecnico"))
_item(_exp_t, t("Geográfico", "Geographic"), "tecnico", "geo")
_item(_exp_t, t("Señales", "Signals"), "tecnico", "senales")
_item(_exp_t, t("Temporal", "Temporal"), "tecnico", "temporal")

_exp_c = st.sidebar.expander("" + t("Crear gráfica", "Create chart"),
                             expanded=(zona == "crear"))
_item(_exp_c, t("Conjuntos listos", "Ready-made sets"), "crear", "listos")
_item(_exp_c, t("Constructor", "Builder"), "crear", "constructor")

st.sidebar.divider()
# IMPORTANTE fijo abajo del menú, es el mensaje defensivo del proyecto, señal
# estadística no es lo mismo que causalidad. Que esté siempre visible.
st.sidebar.caption(t("Una señal estadística es una hipótesis de trabajo, no una "
                     "prueba de causalidad.",
                     "A statistical signal is a working hypothesis, not proof of "
                     "causality."))
# ZONA 1 — INICIO
# A partir de aquí cada zona es una función. No se ejecutan al definirse, abajo
# del todo, según la 'zona' guardada en session_state, llamo a la que toque.
def vista_inicio():
    st.subheader(t("Un vistazo al sistema", "System at a glance"))
    intro(t("Panorámica rápida del sistema y de los datos, para cualquier "
            "visitante.", "A quick overview of the system and data, for anyone."))
    senales = cargar("senales_prr_ror")
    perfil = cargar("geo_perfil_paises")

    # Cuatro métricas en fila. Cada m es una columna, .metric pinta la tarjeta.
    # Uso el "—" como marcador de posición cuando la tabla aún no está.
    m1, m2, m3, m4 = st.columns(4)
    if senales is not None:
        m1.metric(t("Combinaciones evaluadas", "Combinations evaluated"),
                  f"{len(senales):,}")
        m2.metric(t("Señales confirmadas", "Confirmed signals"),
                  f"{int(senales['es_senal'].sum()):,}")   # sum() de un bool = cuántos True
    else:
        m1.metric(t("Combinaciones evaluadas", "Combinations evaluated"), "—")
        m2.metric(t("Señales confirmadas", "Confirmed signals"), "—")
    m3.metric(t("Países notificadores", "Reporting countries"),
              f"{perfil['reporter_country'].nunique():,}"
              if perfil is not None else "—")
    m4.metric(t("Periodo analizado", "Period analysed"), "2020–2025")

    st.markdown(t(
        "PharmaSignal rastrea la base pública de notificaciones de reacciones "
        "adversas de la FDA (FAERS) para detectar **posibles asociaciones entre "
        "fármacos y efectos adversos** que merecen vigilancia.",
        "PharmaSignal mines the FDA's public adverse event database (FAERS) to "
        "detect **possible drug–adverse-effect associations** worth monitoring."))
    st.divider()

    if perfil is not None:
        st.markdown("##### " + t("Dónde se notifica en el mundo",
                                 "Where reporting happens worldwide"))
        mostrar(fig_mapa(perfil), key="inicio_mapa")
        st.caption(t("Volumen de notificaciones por país (escala logarítmica).",
                     "Report volume by country (log scale)."))
    st.divider()

    # Curva de los GLP-1. px.area pinta el área
    # bajo la línea, le fuerzo el color de línea y un relleno azul translúcido.
    fam = cargar("serie_temporal_familias")
    if fam is not None and "reportes_glp1" in fam.columns:
        st.markdown("##### " + t("El fenómeno de la década: los fármacos GLP-1",
                                 "The phenomenon of the decade: GLP-1 drugs"))
        fam = fam.sort_values("trimestre")
        fig = px.area(fam, x="trimestre", y="reportes_glp1",
                      labels={"trimestre": "",
                              "reportes_glp1": t("Notificaciones", "Reports")})
        fig.update_traces(line_color=BLUE, fillcolor="rgba(79,155,232,0.25)")
        mostrar(estilo_plotly(fig, 360), key="inicio_glp1")

    # Ahora en formato destacado, para que nadie salga
    # de la portada pensando que esto prueba causalidad.
    st.info(t("**Importante:** que un efecto se notifique junto a un fármaco no "
              "prueba que el fármaco lo cause. Son hipótesis a investigar.",
              "**Important:** an effect being reported alongside a drug does not "
              "prove causation. These are hypotheses to investigate."))


# ZONA 2 — EXPLORAR (una vista por familia)
def vista_explorar(fam_id):
    # Vista divulgativa de una familia. .get con "glp1" de respaldo por si llega
    # un id raro, así nunca falla con KeyError.
    fam = FAMILIAS.get(fam_id, FAMILIAS["glp1"])
    st.subheader(t("Explorar", "Explore") + " · " + fam["label"])
    intro(t("Qué efectos adversos se notifican junto a esta familia con más "
            "frecuencia de lo esperado, en lenguaje sencillo.",
            "Which adverse effects are reported with this family more often than "
            "expected, in plain language."))

    senales = cargar("senales_prr_ror")
    if senales is None:
        aviso_tabla("senales_prr_ror", "prr_ror.py")
        return

    # Filtro las señales a los fármacos de esta familia. La columna 'a' es la
    # casilla de la tabla 2x2 con la corrección de Haldane-Anscombe (+0.5), así
    # que le resto ese 0.5 para recuperar el nº de casos real y redondeo.
    sen = senales[senales["drugname_norm"].isin(fam["drugs"])].copy()
    sen["casos"] = (sen["a"] - 0.5).round().astype(int)
    # Me quedo solo con lo que es señal confirmada y con respaldo mínimo (>=20),
    # para no enseñar ruido en una vista pensada para usuarios no técnicos.
    sen = sen[sen["es_senal"] & (sen["casos"] >= 20)]

    if not len(sen):
        st.info(t("No hay señales con respaldo suficiente para esta familia.",
                  "No sufficiently supported signals for this family."))
    else:
        # Agrupo por reacción: sumo casos y me quedo con el PRR máximo como
        # medida de "cuántas veces más de lo esperado".
        agg = sen.groupby("pt_norm").agg(
            casos=("casos", "sum"), veces=("prr", "max")).reset_index()
        top = agg.sort_values("casos", ascending=False).head(12)
        top["pt_disp"] = tr_terms(top["pt_norm"])

        st.markdown("##### " + t("Efectos más notificados", "Most reported effects"))
        fig = px.bar(top.sort_values("casos"), x="casos", y="pt_disp",
                     orientation="h",
                     labels={"casos": t("Nº de notificaciones", "Nº of reports"),
                             "pt_disp": ""})
        fig.update_traces(marker_color=BLUE)
        mostrar(eje_paises_grande(estilo_plotly(fig, 440)), key="expl_top")

        # Tabla acompañante. Construyo la frase "N veces más de lo esperado" en
        # una columna nueva y luego renombro todo a etiquetas legibles.
        tabla = top.copy()
        tabla[t("Se notifica", "Reported")] = (
            tabla["veces"].round(0).astype(int).astype(str)
            + t(" veces más de lo esperado", "× more than expected"))
        tabla = tabla[["pt_disp", "casos",
                       t("Se notifica", "Reported")]].rename(columns={
            "pt_disp": t("Efecto adverso", "Adverse effect"),
            "casos": t("Notificaciones", "Reports")})
        st.dataframe(tabla, use_container_width=True, hide_index=True)
        st.caption(t("«Veces más de lo esperado» compara la frecuencia del efecto "
                     "en esta familia frente al resto de la base.",
                     "'× more than expected' compares the effect's frequency in "
                     "this family versus the rest of the database."))
    st.divider()

    # Si la familia tiene serie temporal propia, pinto su evolución. Finasterida
    # no la tiene (serie=None), así que este bloque se salta para ella.
    serie = fam.get("serie")
    fam_t = cargar("serie_temporal_familias")
    if serie and fam_t is not None and serie in fam_t.columns:
        st.markdown("##### " + t("Evolución de la notificación",
                                 "Reporting evolution"))
        fam_t = fam_t.sort_values("trimestre")
        fig = px.area(fam_t, x="trimestre", y=serie,
                      labels={"trimestre": "", serie: t("Notificaciones", "Reports")})
        fig.update_traces(line_color=BLUE, fillcolor="rgba(79,155,232,0.25)")
        mostrar(estilo_plotly(fig, 360), key="expl_serie")

# ZONA 3 — ANÁLISIS TÉCNICO
def panel_senales():
    st.subheader(t("Señales", "Signals"))
    intro(t("Detección de desproporcionalidad (PRR/ROR) sobre el conjunto "
            "global. Ajusta filtros y orden de relevancia.",
            "Disproportionality detection (PRR/ROR) over the full global set."))
    senales = cargar("senales_prr_ror")
    if senales is None:
        aviso_tabla("senales_prr_ror", "prr_ror.py")
        return

    # Panel de filtros dentro de un expander abierto. Cada control (slider,
    # selectbox, checkbox, text_input) devuelve directamente su valor actual.
    # como el script se reejecuta al tocarlos, las variables ya traen la
    # selección del usuario sin necesidad de callbacks.
    with st.expander(t("Filtros", "Filters"), expanded=True):
        c1, c2, c3 = st.columns(3)
        min_casos = c1.slider(t("Casos mínimos", "Minimum cases"), 3, 500, 50, 1)
        orden = c2.selectbox(t("Ordenar por", "Sort by"),
                             [t("Respaldo (nº de casos)", "Support (nº of cases)"),
                              t("Intensidad (PRR)", "Intensity (PRR)")])
        solo = c3.checkbox(t("Solo señales confirmadas", "Confirmed signals only"),
                           value=True)
        c4, c5, c6 = st.columns(3)
        ocultar = c4.checkbox(t("Ocultar señales triviales",
                                "Hide trivial signals"), value=True)
        qf = c5.text_input(t("Buscar fármaco", "Search drug"))
        qr = c6.text_input(t("Buscar reacción", "Search reaction"))

    # Aplico los filtros uno a uno sobre una copia. Recupero los casos reales
    # igual que antes (quitando el 0.5 de Haldane-Anscombe).
    df = senales.copy()
    df["casos_reales"] = (df["a"] - 0.5).round().astype(int)
    df = df[df["casos_reales"] >= min_casos]
    if solo:
        df = df[df["es_senal"]]
    if ocultar:
        # Con poco fondo estadístico detrás, exijo un mínimo en las
        # otras casillas de la 2x2 para que la señal tenga cuerpo.
        df = df[(df["c"] >= 100) & ((df["a"] + df["b"]) >= 200)]
    if qf.strip():
        df = df[df["drugname_norm"].str.contains(qf.strip().lower(), na=False)]
    if qr.strip():
        df = df[df["pt_norm"].str.contains(qr.strip().lower(), na=False)]

    # Métricas que reaccionan a los filtros: se recalculan en cada rerun.
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("Combinaciones", "Combinations"), f"{len(df):,}")
    m2.metric(t("Señales confirmadas", "Confirmed signals"),
              f"{int(df['es_senal'].sum()):,}")
    m3.metric(t("PRR máximo", "Max PRR"),
              f"{df['prr'].max():,.0f}" if len(df) else "—")
    m4.metric(t("Casos totales", "Total cases"),
              f"{int(df['casos_reales'].sum()):,}" if len(df) else "—")

    if not len(df):
        st.info(t("Ninguna combinación cumple los filtros.",
                  "No combination matches the filters."))
        return

    # La columna por la que ordeno depende del selectbox de arriba.
    col_orden = "casos_reales" if orden.startswith(("Respaldo", "Support")) else "prr"
    st.markdown("")
    g1, g2 = st.columns(2, gap="large")
    with g1:
        # Ranking Top 15. Construyo una etiqueta "fármaco - reacción" recortada
        # para que quepa en el eje sin desbordarse.
        st.markdown("##### " + t("Top 15", "Top 15"))
        top = df.nlargest(15, col_orden).copy()
        top["etiqueta"] = (top["drugname_norm"].str.slice(0, 16) + " · "
                           + tr_terms(top["pt_norm"]).str.slice(0, 22))
        etq = t("Casos", "Cases") if col_orden == "casos_reales" else "PRR"
        fig = px.bar(top.sort_values(col_orden), x=col_orden, y="etiqueta",
                     orientation="h", labels={col_orden: etq, "etiqueta": ""})
        fig.update_traces(marker_color=BLUE)
        mostrar(estilo_plotly(fig, 440), key="tec_top")
    with g2:
        # Mapa de densidad PRR vs casos. Son decenas de miles de puntos, una
        # nube normal sería ilegible, así que uso un heatmap. Paso ambos ejes
        # a log (por eso las etiquetas van a mano abajo) para poder leer la
        # distribución, que si no se amontona toda en la esquina.
        st.markdown("##### " + t("Densidad de señales (PRR frente a casos)",
                                 "Signal density (PRR vs cases)"))
        sc = df[(df["prr"] > 0) & (df["casos_reales"] > 0)].copy()
        sc["lx"] = np.log10(sc["casos_reales"])
        sc["ly"] = np.log10(sc["prr"])
        fig = px.density_heatmap(
            sc, x="lx", y="ly", nbinsx=34, nbinsy=34,
            color_continuous_scale=["#11151d", BLUE_SOFT, BLUE, "#9EC9F0"],
            labels={"lx": t("Casos", "Cases"), "ly": "PRR"})
        fig = estilo_plotly(fig, 440)
        # Devuelvo las marcas de los ejes a la escala real (1, 10, 100…) aunque
        # por dentro esté en log.
        fig.update_xaxes(tickvals=[0, 1, 2, 3, 4, 5],
                         ticktext=["1", "10", "100", "1K", "10K", "100K"])
        fig.update_yaxes(tickvals=[0, 1, 2, 3], ticktext=["1", "10", "100", "1K"])
        mostrar(fig, key="tec_dens")
        st.caption(t("Zonas claras = mayor concentración de señales.",
                     "Lighter areas = higher concentration of signals."))

    # Tabla de detalle con todas las métricas (PRR, ROR, IC95, chi²) y su CSV.
    st.divider()
    st.markdown("##### " + t("Detalle de señales", "Signal detail"))
    df = df.copy()
    df["reac_disp"] = tr_terms(df["pt_norm"])
    tabla = df.sort_values(col_orden, ascending=False)[[
        "drugname_norm", "reac_disp", "casos_reales", "prr", "ror",
        "ror_ic_inf", "ror_ic_sup", "chi2"]].rename(columns={
        "drugname_norm": t("Fármaco", "Drug"), "reac_disp": t("Reacción", "Reaction"),
        "casos_reales": t("Casos", "Cases"), "prr": "PRR", "ror": "ROR",
        "ror_ic_inf": t("IC95 inf.", "95%CI low"),
        "ror_ic_sup": t("IC95 sup.", "95%CI high"), "chi2": "Chi²"})
    # Redondeo a 2 decimales solo las columnas numéricas de métricas.
    for c in ["PRR", "ROR", t("IC95 inf.", "95%CI low"),
              t("IC95 sup.", "95%CI high"), "Chi²"]:
        tabla[c] = tabla[c].round(2)
    st.dataframe(tabla, use_container_width=True, height=440, hide_index=True)
    boton_csv(tabla, "pharmasignal_senales.csv")


def panel_geografico():
    st.subheader(t("Geográfico", "Geographic"))
    intro(t("Perfil por país, divergencia de España, nivel de renta y "
            "concentración geográfica.",
            "Country profile, Spain divergence, income level and concentration."))
    perfil = cargar("geo_perfil_paises")
    if perfil is None:
        aviso_tabla("geo_perfil_paises", "analisis_geografico.py")
        return

    # Métricas de concentración. El HHI (índice de Herfindahl) es la suma de las
    # cuotas al cuadrado: cerca de 1 = muy concentrado en pocos países, cerca de
    # 0 = muy repartido. También saco la cuota del top-5 y el peso de España.
    total = int(perfil["reportes"].sum())
    perfil = con_nombre_pais(perfil)
    perfil["cuota"] = perfil["reportes"] / total
    hhi = float((perfil["cuota"] ** 2).sum())
    top5 = perfil.nlargest(5, "reportes")["reportes"].sum() / total * 100
    peso_es = (perfil.loc[perfil["reporter_country"] == "ES", "reportes"].sum()
               / total * 100)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("Países notificadores", "Reporting countries"),
              f"{perfil['reporter_country'].nunique():,}")
    m2.metric(t("Índice Herfindahl", "Herfindahl index"), f"{hhi:.4f}")
    m3.metric(t("Cuota top-5", "Top-5 share"), f"{top5:.1f}%")
    m4.metric(t("Peso de España", "Spain's share"), f"{peso_es:.2f}%")
    st.divider()

    st.markdown("##### " + t("Volumen de notificación por país",
                             "Report volume by country"))
    mostrar(fig_mapa(perfil), key="geo_mapa")
    st.divider()

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("##### " + t("Top 15 por volumen", "Top 15 by volume"))
        top = perfil.nlargest(15, "reportes")
        fig = px.bar(top.sort_values("reportes"), x="reportes", y="pais",
                     orientation="h",
                     labels={"reportes": t("Reportes", "Reports"), "pais": ""})
        fig.update_traces(marker_color=BLUE)
        mostrar(eje_paises_grande(estilo_plotly(fig, 460)), key="geo_vol")
    with c2:
        # % de desenlaces mortales por país, pero solo para países con al menos
        # 5.000 reportes: con pocos reportes el porcentaje se dispara y engaña.
        # Lo uso como aproximación a la cultura de notificación (unos países
        # solo notifican lo grave, otros notifican de todo).
        st.markdown("##### " + t("Desenlaces mortales (≥5.000 reportes)",
                                 "Fatal outcomes (≥5,000 reports)"))
        if "pct_muertes" in perfil.columns:
            mort = perfil[perfil["reportes"] >= 5000].nlargest(15, "pct_muertes")
            fig = px.bar(mort.sort_values("pct_muertes"), x="pct_muertes",
                         y="pais", orientation="h",
                         labels={"pct_muertes": t("% muertes", "% deaths"),
                                 "pais": ""})
            fig.update_traces(marker_color=NAVY)
            mostrar(eje_paises_grande(estilo_plotly(fig, 460)), key="geo_mort")

    # Divergencia de España, en dos pestañas (fármacos / reacciones) usando la
    # función panel_divergencia de arriba.
    st.divider()
    st.markdown("##### " + t("Divergencia de España frente al patrón global",
                             "Spain vs global pattern divergence"))
    tab_far, tab_rea = st.tabs([t("Fármacos", "Drugs"),
                                t("Reacciones", "Reactions")])
    with tab_far:
        panel_divergencia(cargar("geo_divergencia_farmacos"),
                          "drugname_norm", "farmacos")
    with tab_rea:
        panel_divergencia(cargar("geo_divergencia_reacciones"),
                          "pt_norm", "reacciones")

    st.divider()
    c3, c4 = st.columns(2, gap="large")
    with c3:
        st.markdown("##### " + t("Peso relativo de GLP-1 por país",
                                 "GLP-1 relative share by country"))
        glp1 = cargar("geo_glp1_paises")
        if glp1 is None:
            aviso_tabla("geo_glp1_paises", "analisis_geografico.py")
        else:
            glp1 = con_nombre_pais(glp1).nlargest(15, "pct_glp1")
            fig = px.bar(glp1.sort_values("pct_glp1"), x="pct_glp1", y="pais",
                         orientation="h",
                         labels={"pct_glp1": t("% reportes GLP-1", "% GLP-1 reports"),
                                 "pais": ""})
            fig.update_traces(marker_color=BLUE)
            mostrar(eje_paises_grande(estilo_plotly(fig, 460)), key="geo_glp1")
    with c4:
        # Evolución del peso de España por trimestre. Marco 2025Q2 con una línea
        # roja y la anotación "ES a EU" que es el hallazgo de que a partir de 2025Q3
        # FAERS recodifica España dentro del bloque EU y se pierde el detalle
        # nacional. Es un hallazgo del proyecto, por eso lo señalo en el gráfico.
        st.markdown("##### " + t("Peso de España por trimestre",
                                 "Spain's share by quarter"))
        evo = cargar("geo_evolucion_espana")
        if evo is None:
            aviso_tabla("geo_evolucion_espana", "analisis_geografico.py")
        else:
            evo = evo.sort_values("trimestre")
            fig = px.line(evo, x="trimestre", y="pct_es", markers=True,
                          labels={"trimestre": "",
                                  "pct_es": t("% del total", "% of total")})
            fig.update_traces(line_color=BLUE)
            fig = estilo_plotly(fig, 460)
            if (evo["trimestre"] == "2025q2").any():
                fig.add_vline(x="2025q2", line_dash="dash", line_color=NEG)
                fig.add_annotation(x="2025q2", y=evo["pct_es"].max(),
                                   text="ES→EU", showarrow=False,
                                   font=dict(color=NEG, size=11), yshift=10)
            mostrar(fig, key="geo_evo")
            st.caption(t("Desde 2025Q3 FAERS agrega España bajo el código EU: se "
                         "pierde la trazabilidad nacional.",
                         "From 2025Q3 FAERS aggregates Spain under EU: national "
                         "traceability is lost."))

    # Perfil por nivel de renta. Fuerzo el orden ALTA - MEDIA - NO_CLASIFICADO con
    # una categórica ordenada, para que las barras no salgan en orden alfabético.
    st.divider()
    st.markdown("##### " + t("Perfil por nivel de renta", "Income-level profile"))
    renta = cargar("geo_perfil_renta")
    if renta is None:
        aviso_tabla("geo_perfil_renta", "analisis_geografico.py")
    else:
        renta = renta.copy()
        renta["nivel_renta"] = pd.Categorical(
            renta["nivel_renta"], categories=["ALTA", "MEDIA", "NO_CLASIFICADO"],
            ordered=True)
        renta = renta.sort_values("nivel_renta")
        r1, r2 = st.columns([3, 2], gap="large")   # 3:2 → gráfico más ancho que tabla
        with r1:
            # melt pasa de formato ancho (una columna por indicador) a largo
            # (una fila por indicador), que es lo que px.bar necesita para
            # agrupar las barras por color.
            grav = renta.melt(
                id_vars="nivel_renta",
                value_vars=[c for c in ["pct_muertes", "pct_hospitalizacion"]
                            if c in renta.columns],
                var_name="indicador", value_name="pct")
            grav["indicador"] = grav["indicador"].map(
                {"pct_muertes": t("% muertes", "% deaths"),
                 "pct_hospitalizacion": t("% hospitalización", "% hospitalisation")})
            fig = px.bar(grav, x="nivel_renta", y="pct", color="indicador",
                         barmode="group",
                         color_discrete_map={t("% muertes", "% deaths"): NEG,
                                             t("% hospitalización", "% hospitalisation"): BLUE},
                         labels={"nivel_renta": "",
                                 "pct": t("% sobre reportes", "% of reports"),
                                 "indicador": ""})
            mostrar(estilo_plotly(fig, 380), key="geo_renta")
        with r2:
            # Solo muestro las columnas que existan, por si la tabla no trae
            # todas (defensivo ante cambios en el pipeline).
            cols = [c for c in ["nivel_renta", "reportes", "edad_media",
                                "pct_mujeres", "pct_muertes"] if c in renta.columns]
            st.dataframe(renta[cols], use_container_width=True, hide_index=True)

    # Señales exclusivas de España. NOTA: esta parte tiene poca potencia (muy
    # pocos casos por señal)
    st.divider()
    st.markdown("##### " + t("Señales exclusivas de España",
                             "Spain-exclusive signals"))
    esp = cargar("geo_senales_espana")
    if esp is None:
        aviso_tabla("geo_senales_espana", "analisis_geografico.py")
    else:
        exc = esp.copy()
        # Me quedo con lo que es señal en España pero no a nivel global
        if "es_senal_es" in exc and "es_senal_global" in exc:
            exc = exc[exc["es_senal_es"] & (~exc["es_senal_global"])]
        exc = exc.sort_values("prr_es", ascending=False).head(25)
        if "pt_norm" in exc.columns:
            exc["pt_norm"] = tr_terms(exc["pt_norm"])
        colss = [c for c in ["drugname_norm", "pt_norm", "casos_es",
                             "casos_global", "prr_es", "prr_global", "chi2_es"]
                 if c in exc.columns]
        tabla = exc[colss].rename(columns={
            "drugname_norm": t("Fármaco", "Drug"),
            "pt_norm": t("Reacción", "Reaction"),
            "casos_es": t("Casos ES", "ES cases"),
            "casos_global": t("Casos global", "Global cases"),
            "prr_es": "PRR ES", "prr_global": t("PRR global", "Global PRR"),
            "chi2_es": "Chi² ES"})
        for c in ["PRR ES", t("PRR global", "Global PRR"), "Chi² ES"]:
            if c in tabla:
                tabla[c] = tabla[c].round(2)
        st.dataframe(tabla, use_container_width=True, height=380, hide_index=True)
        boton_csv(tabla, "pharmasignal_senales_espana.csv")


def panel_temporal():
    st.subheader(t("Temporal", "Temporal"))
    intro(t("Evolución trimestral de la notificación por familias de fármacos.",
            "Quarterly reporting evolution by drug family."))
    fam = cargar("serie_temporal_familias")
    if fam is None:
        aviso_tabla("serie_temporal_familias", "analisis_temporal.py")
        return
    fam = fam.sort_values("trimestre")

    m1, m2, m3 = st.columns(3)
    m1.metric(t("Trimestres", "Quarters"), f"{fam['trimestre'].nunique()}")
    if "reportes_glp1" in fam:
        m2.metric(t("Reportes GLP-1", "GLP-1 reports"),
                  f"{int(fam['reportes_glp1'].sum()):,}")
    if "reportes_covid" in fam:
        m3.metric(t("Reportes COVID", "COVID reports"),
                  f"{int(fam['reportes_covid'].sum()):,}")
    st.divider()

    # Aquí uso graph_objects (go) en vez de px porque quiero superponer dos
    # líneas (GLP-1 y COVID) con control total sobre cada traza. Con go se
    # construye la figura vacía.
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("##### " + t("Por trimestre (absolutos)",
                                 "Per quarter (absolute)"))
        fig = go.Figure()
        if "reportes_glp1" in fam:
            fig.add_trace(go.Scatter(x=fam["trimestre"], y=fam["reportes_glp1"],
                          name="GLP-1", mode="lines+markers",
                          line=dict(color=BLUE, width=2.5)))
        if "reportes_covid" in fam:
            fig.add_trace(go.Scatter(x=fam["trimestre"], y=fam["reportes_covid"],
                          name="COVID-19", mode="lines+markers",
                          line=dict(color=NEG, width=2.5)))
        mostrar(estilo_plotly(fig, 420), key="temp_abs")
    with c2:
        # Misma idea pero en % del total: útil para comparar el peso relativo
        # sin que GLP-1, mucho más voluminoso, aplaste a COVID.
        st.markdown("##### " + t("Peso relativo (%)", "Relative share (%)"))
        fig = go.Figure()
        if "pct_glp1" in fam:
            fig.add_trace(go.Scatter(x=fam["trimestre"], y=fam["pct_glp1"],
                          name="GLP-1", mode="lines+markers",
                          line=dict(color=BLUE, width=2.5)))
        if "pct_covid" in fam:
            fig.add_trace(go.Scatter(x=fam["trimestre"], y=fam["pct_covid"],
                          name="COVID-19", mode="lines+markers",
                          line=dict(color=NEG, width=2.5)))
        fig = estilo_plotly(fig, 420)
        fig.update_yaxes(title=t("% del total", "% of total"))
        mostrar(fig, key="temp_pct")
    st.divider()

    # Desglose de GLP-1 por fármaco como áreas apiladas. pivot_table pasa de
    # formato largo (una fila por trimestre y fármaco) a ancho (una columna por
    # fármaco), que es lo que px.area entiende para apilar.
    st.markdown("##### " + t("Desglose GLP-1 por fármaco",
                             "GLP-1 breakdown by drug"))
    pf = cargar("serie_temporal_glp1_farmacos")
    if pf is None:
        aviso_tabla("serie_temporal_glp1_farmacos", "analisis_temporal.py")
    else:
        piv = pf.pivot_table(index="trimestre", columns="drugname_norm",
                             values="reportes", aggfunc="sum",
                             fill_value=0).sort_index()
        fig = px.area(piv, labels={"value": t("Reportes", "Reports"),
                                   "trimestre": "", "drugname_norm": t("Fármaco", "Drug")})
        mostrar(estilo_plotly(fig, 440), key="temp_glp1")
    st.divider()

    # Hueco reservado para la Entrega 3: el Isolation Forest correrá sobre estas
    # mismas series. Lo dejo señalizado para que se vea que la
    # infraestructura ya está lista aunque el modelo aún no esté.
    st.markdown("##### " + t("Detección de anomalías — Isolation Forest",
                             "Anomaly detection — Isolation Forest"))
    st.info(t("Previsto para la Entrega 3. Sobre estas series se aplicará un "
              "modelo de detección de anomalías. La infraestructura ya está lista.",
              "Planned for Deliverable 3. An anomaly-detection model will run "
              "on these series. The data infrastructure is already in place."))


# ZONA 4 — CREAR GRÁFICA
# Catálogo de tablas que el usuario puede elegir para graficar libremente.
# La tupla es (nombre_es, nombre_en) para mostrar en el selector según idioma.
TABLAS = {
    "senales_prr_ror": ("Señales PRR/ROR (global)", "PRR/ROR signals (global)"),
    "geo_perfil_paises": ("Perfil por país", "Country profile"),
    "geo_divergencia_farmacos": ("Divergencia de fármacos (ES)", "Drug divergence (ES)"),
    "geo_divergencia_reacciones": ("Divergencia de reacciones (ES)", "Reaction divergence (ES)"),
    "geo_senales_espana": ("Señales de España", "Spain signals"),
    "geo_perfil_renta": ("Perfil por nivel de renta", "Income-level profile"),
    "geo_glp1_paises": ("GLP-1 por país", "GLP-1 by country"),
    "geo_evolucion_espana": ("Evolución de España", "Spain evolution"),
    "serie_temporal_familias": ("Series temporales (familias)", "Time series (families)"),
    "serie_temporal_glp1_farmacos": ("Series GLP-1 por fármaco", "GLP-1 series by drug"),
}


@st.cache_data(show_spinner=False)
def _preparar(tabla, tipo, x, y, color, agg, topn):
    # Prepara los datos antes de graficar: agrega, ordena.
    # Está cacheada por argumentos: si el usuario repite la misma combinación,
    # no recalcula. La clave de rendimiento está en los topes de más abajo, que
    # evitan mandar cientos de miles de puntos al navegador.
    df = cargar(tabla)
    if df is None:
        return None, None
    d = df
    gb = [x] + ([color] if color else [])   # columnas por las que agrupar
    ycol = y
    # Agregación (suma/media/recuento) solo tiene sentido en barras/líneas/área.
    if agg and tipo in ("bar", "line", "area"):
        if agg == "count":
            d = d.groupby(gb, as_index=False).size().rename(columns={"size": "recuento"})
            ycol = "recuento"
        else:
            d = d.groupby(gb, as_index=False)[y].agg(agg)
    # Topes por tipo de gráfica para que el render sea rápido:
    if tipo == "bar" and ycol:
        d = d.sort_values(ycol, ascending=False).head(topn)   # solo el top-N
    elif tipo in ("line", "area"):
        # Si hay demasiadas categorías en el eje X, me quedo con las 400 de
        # mayor peso para optimizar
        if ycol and d[x].nunique() > 400:
            top_x = d.groupby(x)[ycol].sum().nlargest(400).index
            d = d[d[x].isin(top_x)]
        d = d.sort_values(x)
    elif tipo == "scatter" and len(d) > 5000:
        d = d.sample(5000, random_state=0)
    elif tipo == "hist" and len(d) > 50000:
        d = d.sample(50000, random_state=0)
    return d, ycol


def grafica_auto(df, kp):
    # Elige sola una gráfica razonable según qué columnas tenga la tabla:
    # si hay trimestre = línea temporal, si hay país = barras por país, si no,
    # barras de la primera categórica contra la primera numérica. Todo dentro de
    # try/except porque puede fallar con tablas raras.
    num = df.select_dtypes("number").columns.tolist()
    try:
        if "trimestre" in df.columns and num:
            fig = px.line(df.sort_values("trimestre"), x="trimestre", y=num[0],
                          markers=True, labels={"trimestre": ""})
            fig.update_traces(line_color=BLUE)
        elif "reporter_country" in df.columns and num:
            d = con_nombre_pais(df).nlargest(15, num[0])
            fig = px.bar(d.sort_values(num[0]), x=num[0], y="pais",
                         orientation="h", labels={"pais": ""})
            fig.update_traces(marker_color=BLUE)
            eje_paises_grande(fig)
        else:
            cat = [c for c in df.columns if c not in num]
            xcol = cat[0] if cat else df.columns[0]
            ycol = num[0] if num else df.columns[-1]
            d = df.nlargest(15, ycol) if num else df.head(15)
            fig = px.bar(d.sort_values(ycol) if num else d, x=ycol, y=xcol,
                         orientation="h", labels={xcol: ""})
            fig.update_traces(marker_color=BLUE)
        mostrar(estilo_plotly(fig, 440), key=kp)
    except Exception as e:
        # Si algo falla, aviso en vez de romper la página entera.
        st.info(t("No se pudo generar una gráfica automática.",
                  "Could not auto-generate a chart.") + f" ({e})")


def constructor(df, tabla, kp):
    # El constructor manual: el usuario elige tipo, ejes, color, agregación y
    # nº máximo de elementos. Los diccionarios traducen la etiqueta visible al
    # valor interno de Plotly/pandas.
    tipos = {t("Barras", "Bar"): "bar", t("Líneas", "Line"): "line",
             t("Dispersión", "Scatter"): "scatter", t("Área", "Area"): "area",
             t("Histograma", "Histogram"): "hist"}
    aggs = {t("Suma", "Sum"): "sum", t("Media", "Mean"): "mean",
            t("Recuento", "Count"): "count", t("Ninguna", "None"): None}
    cols_all = list(df.columns)
    # Para el eje Y ofrezco solo columnas numéricas
    num_cols = df.select_dtypes("number").columns.tolist() or cols_all

    # 'kp' es un prefijo de key: como esta función se usa en varios sitios
    c1, c2, c3 = st.columns(3)
    tipo = tipos[c1.selectbox(t("Tipo de gráfica", "Chart type"),
                              list(tipos), key=kp + "tipo")]
    x = c2.selectbox(t("Eje X", "X axis"), cols_all, key=kp + "x")
    # El histograma no lleva eje Y (cuenta frecuencias), por eso ahí y=None.
    y = None if tipo == "hist" else c3.selectbox(
        t("Eje Y", "Y axis"), num_cols, key=kp + "y")

    c4, c5, c6 = st.columns(3)
    color_lbl = c4.selectbox(t("Separar por color (opcional)",
                               "Split by color (optional)"),
                             [t("(ninguno)", "(none)")] + cols_all, key=kp + "col")
    color = None if color_lbl in (t("(ninguno)", "(none)"),) else color_lbl
    agg = aggs[c5.selectbox(t("Agregación", "Aggregation"), list(aggs),
                            key=kp + "agg")]
    topn = c6.slider(t("Máx. elementos", "Max items"), 5, 100, 20, key=kp + "topn")

    # ph es el hueco para la capa de "cargando": la pinto, preparo los datos,
    # y la vacío justo antes de mostrar el resultado.
    ph = st.empty()
    try:
        overlay_cargando(ph, t("Generando gráfica…", "Building chart…"))
        d, ycol = _preparar(tabla, tipo, x, y, color, agg, topn)
        if d is None or not len(d):
            ph.empty()
            st.info(t("Sin datos para esa combinación.", "No data for that combination."))
            return
        seq = COLORWAY
        # Construyo la figura según el tipo elegido.
        if tipo == "bar":
            fig = px.bar(d, x=x, y=ycol, color=color, barmode="group",
                         color_discrete_sequence=seq)
        elif tipo == "line":
            fig = px.line(d, x=x, y=ycol, color=color, render_mode="webgl",
                          color_discrete_sequence=seq)
        elif tipo == "area":
            fig = px.area(d, x=x, y=ycol, color=color, color_discrete_sequence=seq)
        elif tipo == "scatter":
            fig = px.scatter(d, x=x, y=ycol, color=color, opacity=0.6,
                             render_mode="webgl", color_discrete_sequence=seq)
        else:
            fig = px.histogram(d, x=x, color=color, color_discrete_sequence=seq)
        # Si no hay separación por color, fuerzo el azul original
        if color is None:
            if tipo == "line":
                fig.update_traces(line_color=BLUE)
            else:
                fig.update_traces(marker_color=BLUE)
        ph.empty()
        mostrar(estilo_plotly(fig, 460), key=kp + "fig")
        st.caption(t(f"Mostrando {len(d):,} elementos (acotado para render rápido).",
                     f"Showing {len(d):,} items (capped for fast rendering)."))
        # Ofrezco descarga de la gráfica (HTML) y de los datos ya filtrados (CSV).
        cc1, cc2 = st.columns(2)
        with cc1:
            boton_html(fig, f"pharmasignal_{kp}.html")
        with cc2:
            boton_csv(d, f"pharmasignal_{kp}.csv")
    except Exception as e:
        # Combinaciones imposibles (p. ej. Y no numérico) caen aquí con un aviso
        # claro en vez de romper.
        ph.empty()
        st.error(t("Esa combinación no es válida. Prueba otros ejes o agregación.",
                   "That combination is not valid. Try other axes or aggregation.")
                 + f" ({e})")


def _selector_tabla(kp):
    # Selector de tabla reutilizable. format_func decide el texto visible
    etq = st.selectbox(t("Conjunto de datos", "Dataset"), list(TABLAS),
                       format_func=lambda k: TABLAS[k][0] if L == "es" else TABLAS[k][1],
                       key=kp + "sel")
    return etq, cargar(etq)


def crear_listos():
    # Modo fácil: eliges tabla y se representa de forma automática, más
    # una previsualización de filas y su descarga. Cero configuración.
    st.subheader(t("Conjuntos listos", "Ready-made sets"))
    intro(t("Cada conjunto curado con una gráfica automática y descarga directa.",
            "Each curated set with an automatic chart and direct download."))
    etq, df = _selector_tabla("listos_")
    if df is None:
        aviso_tabla(etq, t("el script correspondiente", "the corresponding script"))
        return
    st.caption(f"{len(df):,} " + t("filas", "rows") +
               f" · {len(df.columns)} " + t("columnas", "columns"))
    grafica_auto(df, "listos_auto")
    n = st.slider(t("Filas a previsualizar", "Rows to preview"),
                  10, min(1000, len(df)), min(100, len(df)), 10)
    st.dataframe(df.head(n), use_container_width=True, height=380)
    boton_csv(df, f"pharmasignal_{etq}.csv")


def crear_constructor():
    # Modo avanzado: eliges tabla y te doy el constructor completo.
    st.subheader(t("Constructor", "Builder"))
    intro(t("Combina los datos a tu gusto: tipo, ejes, color y agregación. "
            "Exporta en PNG (icono de cámara), CSV o HTML.",
            "Combine the data as you like: type, axes, color and aggregation. "
            "Export as PNG (camera icon), CSV or HTML."))
    etq, df = _selector_tabla("constr_")
    if df is None:
        aviso_tabla(etq, t("el script correspondiente", "the corresponding script"))
        return
    constructor(df, etq, "cst_")


# ENRUTADO
# Según la zona guardada en session_state, llamo a la
# función de la vista correspondiente. Esto se ejecuta en cada rerun, después de
# haber definido todas las funciones de arriba, así que aquí es donde de verdad
# se pinta la página.
if zona == "inicio":
    vista_inicio()
elif zona == "explorar":
    vista_explorar(sub or "glp1")
elif zona == "tecnico":
    # Diccionario que mapea el subapartado a su función, .get con panel_geografico
    # de respaldo.
    {"geo": panel_geografico, "senales": panel_senales,
     "temporal": panel_temporal}.get(sub, panel_geografico)()
else:
    # Zona crear: listos o constructor.
    (crear_listos if sub == "listos" else crear_constructor)()

# Pie del sidebar, se pinta siempre al final independientemente de la zona.
st.sidebar.divider()
st.sidebar.caption("PharmaSignal · TFB · FAERS 2020–2025")