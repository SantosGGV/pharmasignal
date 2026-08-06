"""
streamlit_app.py

Frontend de PharmaSignal.

Navegación ordenada en sección - subapartados)
Bilingüe ES/EN.
Datos de país y traducción de términos se cargan desde ficheros externos
en data/diccionarios/ (paises.txt, terminos_es.txt), sin nada incrustado en el
código.
Los resultados se leen desde Delta Lake.
"""
# NOTA SOBRE STREAMLIT (importante para entender como funciona el código):
# Streamlit no funciona como una web normal. Cada vez que se toca un
# botón, un slider o cambias de idioma, vuelve a ejecutar este fichero entero, de
# arriba a abajo, como si lo lanzaras de cero. Por eso hay que tener cuidado con
# releer datos pesados de ahí el cacheo constante.

import os

import numpy as np
import pandas as pd
import plotly.express as px          # px = atajos rápidos para gráficas típicas
import plotly.graph_objects as go    # go = para cuando px se queda corto
import streamlit as st
from deltalake import DeltaTable     # lee tablas Delta sin necesidad de Spark

# Capa de acceso a datos del constructor. Concentra la correspondencia entre lo
# que pide el usuario y la tabla precalculada que lo resuelve, de modo que aquí
# solo queda la representación.
import consultas_explorador as ce

# CONFIGURACIÓN GLOBAL
# Se usa "~" para generar rutas globales independientemente desde el usuario que se ejecute
CURATED = os.path.expanduser("~/pharmasignal/data/curated")
DICC_DIR = os.path.expanduser("~/pharmasignal/data/diccionarios")

# Paleta de colores de la app
BLUE = "#4F9BE8"
NAVY = "#2E75B6"
BLUE_SOFT = "#2E5E8C"
INK = "#E6EAF0"        # color del texto principal
SOFT = "#8A97A8"       # texto secundario
GRID = "#262D3A"       # líneas de la rejilla de las gráficas
POS = "#4F9BE8"        # azul para "a favor" / sobrerrepresentado
NEG = "#E8746E"        # rojo para "en contra" / infrarrepresentado
BG = "#0E1117"         # fondo oscuro
COLORWAY = ["#4F9BE8", "#E8746E", "#7FB3E8", "#2E75B6", "#9EC9F0",
            "#C0894D", "#6FCF97", "#B07FE8"]   # ciclo de colores para series

# set_page_config tiene que ser lo primero de Streamlit que se ejecuta
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
        .frase { font-size:1.15rem; line-height:1.9; color:#8A97A8;
                 margin:6px 0 16px 0; }
        .frase b { color:#4F9BE8; font-weight:600;
                   border-bottom:1px dashed #2E5E8C; }
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
                       "exenatide", "byetta", "bydureon", "bydureon bcise",
                       "lixisenatide", "lyxumia", "adlyxin"]},

    "covid": {"label": "COVID-19 (Paxlovid, Remdesivir…)",
              "serie": "reportes_covid_antiviral",
              "drugs": ["paxlovid", "nirmatrelvir", "nirmatrelvir\\ritonavir",
                        "remdesivir", "veklury", "molnupiravir", "lagevrio",
                        "sotrovimab", "bebtelovimab", "bamlanivimab",
                        "etesevimab", "bamlanivimab\\etesevimab",
                        "casirivimab", "imdevimab", "casirivimab\\imdevimab",
                        "regen-cov", "regen?cov", "tixagevimab", "cilgavimab",
                        "evusheld"]},
    "fina": {"label": "Finasterida (Propecia, Proscar)", "serie": None,
             "drugs": ["finasteride", "propecia", "proscar"]},
}

# Códigos de desenlace de FAERS traducidos.
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
        return None
    try:
        return DeltaTable(ruta).to_pandas()   # Delta → DataFrame de pandas
    except Exception:
        return None                      # si algo falla, prefiero None a que falle


def cargar_diccionario_txt(nombre):
    """Lee 'en|es' desde un .txt. SIN caché: recoge tus ediciones al recargar."""
    # La quiero sin caché a propósito: así, mientras voy ampliando el diccionario
    # a mano, basta con recargar la página para ver los términos nuevos, sin
    # tener que limpiar la caché de Streamlit.
    # NOTA: antes había DOS definiciones de esta función, una cacheada y otra no.
    # Python se quedaba siempre con la última, así que la primera era código
    # muerto. He borrado la cacheada y he dejado solo esta, que es la que valía.
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
                continue
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
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG, key=key)


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


def fig_mapa(perfil, col="reportes", log=True, escala=None, titulo=None,
             min_reportes=0):
    # Mapa mundial. Necesita el código ISO3, así que primero mapeo
    # desde el ISO2 y descarto los países que no consiga traducir.
    # Por defecto se visualizaba el nombre del país completo, con esto
    # se logra visualizar "ES" en vez de "ESPAÑA". Para algunos países
    # con nombre extenso no llegaba a visualizarse.
    mapa = con_nombre_pais(perfil)
    if min_reportes:
        mapa = mapa[mapa["reportes"] >= min_reportes]
    mapa["iso3"] = mapa["reporter_country"].map(ISO2_A_ISO3)
    mapa = mapa.dropna(subset=["iso3", col])

    if log:
        # Coloreo por el logaritmo, no por el valor bruto: EE.UU. aplasta a
        # todos los demás y sin escala log el mapa saldría entero de un color.
        # El colorbar de abajo vuelve a poner las etiquetas en la escala real.
        mapa["_c"] = np.log10(mapa[col].clip(lower=1))
        barra = dict(title=t("Reportes", "Reports"),
                     tickvals=[1, 2, 3, 4, 5, 6],
                     ticktext=["10", "100", "1K", "10K", "100K", "1M"])
    else:
        # Para porcentajes no hace falta log, el rango ya es manejable.
        mapa["_c"] = mapa[col]
        barra = dict(title=titulo or col)

    fig = px.choropleth(
        mapa, locations="iso3", color="_c", hover_name="pais",
        hover_data={col: ":,.2f", "_c": False, "iso3": False},
        color_continuous_scale=escala or ["#16324F", "#2E75B6", "#7FB3E8"])
    fig.update_layout(
        height=460, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor=BG, font=dict(color=INK, size=13),
        hoverlabel=dict(bgcolor="#1A2332", bordercolor=BLUE,
                        font=dict(size=15, color=INK)),
        geo=dict(bgcolor=BG, showframe=False, showcoastlines=False,
                 showland=True, landcolor="#1A2332",
                 projection_type="natural earth"),
        coloraxis_colorbar=barra)
    return fig


@st.cache_data(show_spinner=False)
def buscar_farmaco(q: str):
    # Busca un fármaco por texto libre dentro de la tabla de señales.
    # Va cacheada por el texto buscado, así que si el usuario repite la misma
    # búsqueda no vuelve a recorrer las 868.093 filas.
    # Devuelvo los datos sin traducir a propósito. La traducción depende del
    # idioma, que es una variable global, y si la metiera aquí dentro la caché
    # guardaría el resultado en el idioma equivocado.
    senales = cargar("senales_prr_ror")
    if senales is None or not q.strip():
        return None
    q = q.strip().lower()
    # contains en vez de igualdad: el mismo fármaco aparece con muchas grafías
    # y el usuario no tiene por qué saber cuál escribir.
    # regex=False es deliberado: impide que lo que escriba el usuario se
    # interprete como una expresión regular.
    df = senales[senales["drugname_norm"].str.contains(q, na=False, regex=False)].copy()
    if not len(df):
        return df
    df["casos"] = (df["a"] - 0.5).round().astype(int)
    return df


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
# Cabecera principal de la página, otra vez con HTML a mano para tener el control del layout como mencionaba antes.
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
# Guardo en session_state una tupla (zona, subapartado) que dice dónde está el usuario.
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
                   width='stretch',
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
# Fijo abajo del menú, es el mensaje defensivo del proyecto, señal
# estadística no es lo mismo que causalidad. Que esté siempre visible.
st.sidebar.caption(t("Una señal estadística es una hipótesis de trabajo, no una "
                     "prueba de causalidad.",
                     "A statistical signal is a working hypothesis, not proof of "
                     "causality."))


# ZONA 1 — INICIO
# A partir de aquí cada zona es una función. No se ejecutan al definirse, abajo
# del todo, según la zona guardada en session_state, llamo a la que toque.
def vista_inicio():
    senales = cargar("senales_prr_ror")
    perfil = cargar("geo_perfil_paises")

    # Reservo el estado del buscador antes de nada. Lo necesito porque los
    # botones de ejemplo escriben aquí, y Streamlit no deja tocar el estado de
    # un widget una vez creado: si el text_input existiera ya, fallaría al pulsar.
    if "q_farmaco" not in st.session_state:
        st.session_state["q_farmaco"] = ""

    # BLOQUE 1: métricas del sistema y descripción, lo primero de la página.
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

    # BLOQUE 2: el mapa, a ancho completo.
    if perfil is not None:
        st.markdown("##### " + t("Dónde se notifica en el mundo",
                                 "Where reporting happens worldwide"))
        mostrar(fig_mapa(perfil), key="inicio_mapa")
        st.caption(t("Volumen de notificaciones por país (escala logarítmica).",
                     "Report volume by country (log scale)."))
    else:
        aviso_tabla("geo_perfil_paises", "analisis_geografico.py")

    st.divider()

    # BLOQUE 3: el buscador.
    st.markdown("##### " + t("¿Qué se ha notificado sobre un medicamento?",
                             "What has been reported about a medicine?"))
    intro(t("Escribe el nombre de un fármaco y verás qué efectos adversos se "
            "notifican junto a él con más frecuencia de lo esperado.",
            "Type a drug name to see which adverse effects are reported with it "
            "more often than expected."))

    # Reservo el hueco del input, pinto los botones (que
    # escriben en session_state) y creo el input al final. Si el text_input
    # existiera antes que los botones, Streamlit lanzaría excepción al pulsarlos.
    caja = st.container()

    st.caption(t("Prueba con:", "Try:"))
    # Fármacos conocidos por el público general. Van con el nombre tal cual
    # aparece en FAERS, que es en inglés o con la marca comercial: por eso
    # "ibuprofen" y no "ibuprofeno", "omeprazole" y no "omeprazol".
    ejemplos = ["ozempic", "ibuprofen", "omeprazole", "paracetamol", "metformin"]
    cols_ej = st.columns(len(ejemplos))
    for c, ej in zip(cols_ej, ejemplos):
        if c.button(ej.capitalize(), width='stretch', key="ej_" + ej):
            st.session_state["q_farmaco"] = ej

    with caja:
        q = st.text_input(
            t("Buscar medicamento", "Search medicine"),
            key="q_farmaco", label_visibility="collapsed",
            placeholder=t("Escribe un fármaco: ozempic, ibuprofen, metformin…",
                          "Type a drug: ozempic, ibuprofen, metformin…"))

    if senales is None:
        st.divider()
        aviso_tabla("senales_prr_ror", "prr_ror.py")
        return

    # BLOQUE 4: resultado de la búsqueda. Si el usuario no ha escrito nada, no
    # pinto nada aquí y la página termina en el aviso de causalidad.
    if q.strip():
        st.divider()
        res = buscar_farmaco(q)
        if res is None or not len(res):
            st.warning(t(f"No hay notificaciones para «{q}». Los nombres están "
                         "como aparecen en FAERS, normalmente en inglés o con la "
                         "marca comercial (por ejemplo *ibuprofen*, no "
                         "*ibuprofeno*).",
                         f"No reports found for «{q}». Names appear as in FAERS, "
                         "usually in English or as a brand name."))
        else:
            # Cuántas grafías distintas ha capturado la búsqueda.
            grafias = res["drugname_norm"].nunique()
            # a+b es el total de reportes que mencionan ese fármaco, y es
            # constante dentro de cada grafía. Por eso agrupo primero y luego
            # sumo, en vez de sumar la columna 'casos', que contaría cada reporte
            # tantas veces como reacciones tenga.
            reportes = int(res.groupby("drugname_norm")
                           .apply(lambda g: (g["a"] + g["b"]).max()).sum())
            confirmadas = res[res["es_senal"] & (res["casos"] >= 20)]

            st.markdown("##### " + t(f"Resultados para «{q}»",
                                     f"Results for «{q}»"))
            r1, r2, r3 = st.columns(3)
            r1.metric(t("Notificaciones del fármaco", "Reports for this drug"),
                      f"{reportes:,}")
            r2.metric(t("Efectos distintos", "Distinct effects"),
                      f"{res['pt_norm'].nunique():,}")
            r3.metric(t("Señales confirmadas", "Confirmed signals"),
                      f"{len(confirmadas):,}")

            if grafias > 1:
                st.caption(t(f"La búsqueda ha encontrado {grafias} formas de "
                             "escribir este fármaco en la base de datos y las "
                             "agrupa todas.",
                             f"The search found {grafias} spellings of this drug "
                             "in the database and groups them all."))

            if not len(confirmadas):
                st.info(t("Se han encontrado notificaciones, pero ninguna "
                          "combinación supera los criterios de señal con "
                          "respaldo suficiente.",
                          "Reports found, but no combination passes the signal "
                          "criteria with enough support."))
            else:
                # Agrupo por reacción sumando casos y quedándome con el PRR más
                # alto, igual que hago en la vista Explorar.
                agg = confirmadas.groupby("pt_norm").agg(
                    casos=("casos", "sum"), veces=("prr", "max")).reset_index()
                top = agg.sort_values("veces", ascending=False).head(12)
                top["pt_disp"] = tr_terms(top["pt_norm"])

                st.markdown("##### " + t("Efectos que más se desvían de lo esperado",
                                         "Effects deviating most from expected"))
                fig = px.bar(top.sort_values("veces"), x="veces", y="pt_disp",
                             orientation="h",
                             labels={"veces": t("Veces más de lo esperado",
                                                "× more than expected"),
                                     "pt_disp": ""},
                             custom_data=["casos"])
                fig.update_traces(
                    marker_color=BLUE,
                    hovertemplate="<b>%{y}</b><br>×%{x:.1f} "
                                  + t("más de lo esperado", "more than expected")
                                  + "<br>%{customdata[0]:,} "
                                  + t("notificaciones", "reports") + "<extra></extra>")
                mostrar(eje_paises_grande(estilo_plotly(fig, 460)), key="ini_busca")
                st.caption(t("Solo se muestran efectos que superan los criterios "
                             "estadísticos de señal y con al menos 20 casos "
                             "detrás. El número de veces compara la frecuencia "
                             "del efecto en este fármaco frente al resto de la "
                             "base de datos.",
                             "Only effects passing the statistical signal criteria "
                             "with at least 20 cases are shown."))
                boton_csv(top[["pt_norm", "casos", "veces"]],
                          f"pharmasignal_{q.strip().lower()}.csv")

    st.divider()

    st.info(t("**Importante:** que un efecto se notifique junto a un fármaco no "
              "prueba que el fármaco lo cause. Son hipótesis a investigar.",
              "**Important:** an effect being reported alongside a drug does not "
              "prove causation. These are hypotheses to investigate."))


# ZONA 2 — EXPLORAR (una vista por familia)
def vista_explorar(fam_id):
    # Vista  de una familia. .get con "glp1" de respaldo por si llega
    # un id raro, así nunca falla.
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

    # Filtro las señales a los fármacos de esta familia.
    sen = senales[senales["drugname_norm"].isin(fam["drugs"])].copy()
    sen["casos"] = (sen["a"] - 0.5).round().astype(int)
    # Me quedo solo con lo que es señal confirmada y con respaldo mínimo (>=20),
    # para no enseñar ruido en una vista pensada para usuarios no técnicos.
    sen = sen[sen["es_senal"] & (sen["casos"] >= 20)]

    if not len(sen):
        st.info(t("No hay señales con respaldo suficiente para esta familia.",
                  "No sufficiently supported signals for this family."))
    else:
        # Agrupo por reacción, sumo casos y me quedo con el PRR máximo como
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
        st.dataframe(tabla, width='stretch', hide_index=True)
        st.caption(t("«Veces más de lo esperado» compara la frecuencia del efecto "
                     "en esta familia frente al resto de la base.",
                     "'× more than expected' compares the effect's frequency in "
                     "this family versus the rest of the database."))
    st.divider()

    # Si la familia tiene serie temporal propia, pinto su evolución. Finasterida
    # no la tiene (serie=None), así que este bloque no se añade en este caso.
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
    # igual que antes
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

    # Métricas que reaccionan a los filtros, se recalculan en cada rerun.
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
    st.divider()

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
    mostrar(eje_paises_grande(estilo_plotly(fig, 460)), key="tec_top")

    # Descarga de los datos que cumplen los filtros
    exporta = df.copy()
    exporta["reac_disp"] = tr_terms(exporta["pt_norm"])
    exporta = exporta.sort_values(col_orden, ascending=False)[[
        "drugname_norm", "reac_disp", "casos_reales", "prr", "ror",
        "ror_ic_inf", "ror_ic_sup", "chi2"]].rename(columns={
        "drugname_norm": t("Fármaco", "Drug"), "reac_disp": t("Reacción", "Reaction"),
        "casos_reales": t("Casos", "Cases"), "prr": "PRR", "ror": "ROR",
        "ror_ic_inf": t("IC95 inf.", "95%CI low"),
        "ror_ic_sup": t("IC95 sup.", "95%CI high"), "chi2": "Chi²"})
    for c in ["PRR", "ROR", t("IC95 inf.", "95%CI low"),
              t("IC95 sup.", "95%CI high"), "Chi²"]:
        exporta[c] = exporta[c].round(2)
    boton_csv(exporta, "pharmasignal_senales.csv")
    st.caption(t(f"La descarga incluye las {len(exporta):,} combinaciones que "
                 "cumplen los filtros, con PRR, ROR, intervalo de confianza y "
                 "chi cuadrado.",
                 f"The download includes the {len(exporta):,} combinations "
                 "matching the filters, with PRR, ROR, confidence interval and "
                 "chi-square."))


def panel_geografico():
    st.subheader(t("Geográfico", "Geographic"))
    intro(t("Perfil por país, divergencia de España, nivel de renta y "
            "concentración geográfica.",
            "Country profile, Spain divergence, income level and concentration."))
    perfil = cargar("geo_perfil_paises")
    if perfil is None:
        aviso_tabla("geo_perfil_paises", "analisis_geografico.py")
        return

    # Métricas de concentración. Saco la cuota acumulada del top-5 y el peso de
    # España sobre el total
    # inmediata.
    total = int(perfil["reportes"].sum())
    perfil = con_nombre_pais(perfil)
    top5 = perfil.nlargest(5, "reportes")["reportes"].sum() / total * 100
    peso_es = (perfil.loc[perfil["reporter_country"] == "ES", "reportes"].sum()
               / total * 100)

    m1, m2, m3 = st.columns(3)
    m1.metric(t("Países notificadores", "Reporting countries"),
              f"{perfil['reporter_country'].nunique():,}")
    m2.metric(t("Cuota top-5", "Top-5 share"), f"{top5:.1f}%")
    m3.metric(t("Peso de España", "Spain's share"), f"{peso_es:.2f}%")
    st.divider()

    # Mapa de desenlaces mortales
    if "pct_muertes" in perfil.columns:
        st.markdown("##### " + t("Gravedad de lo que se notifica",
                                 "Severity of what gets reported"))
        mostrar(fig_mapa(perfil, col="pct_muertes", log=False,
                         escala=["#16324F", "#8B5A5A", "#E8746E"],
                         titulo="% " + t("muertes", "deaths"),
                         min_reportes=5000), key="geo_mapa_mort")
        st.caption(t("Porcentaje de notificaciones con desenlace mortal, solo en "
                     "países con al menos 5.000 reportes. Un porcentaje alto no "
                     "indica más riesgo, sino que en ese país se notifica "
                     "principalmente lo grave.",
                     "Share of reports with fatal outcome, countries with 5,000+ "
                     "reports only. A high share does not mean higher risk, but "
                     "that mainly severe cases get reported there."))
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
        # 5.000 reportes: con pocos reportes el porcentaje se dispara y engaña
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

    # Perfil por nivel de renta
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
            st.dataframe(renta[cols], width='stretch', hide_index=True)


def panel_temporal():
    st.subheader(t("Temporal", "Temporal"))
    intro(t("Evolución trimestral de la notificación por familias de fármacos.",
            "Quarterly reporting evolution by drug family."))
    fam = cargar("serie_temporal_familias")
    if fam is None:
        aviso_tabla("serie_temporal_familias", "analisis_temporal.py")
        return
    fam = fam.sort_values("trimestre")

    # Catálogo de las cinco series en un único sitio. Cada entrada lleva la
    # columna de valores absolutos, la de porcentaje, la etiqueta que se muestra
    # y el color
    SERIES = [
        ("reportes_glp1", "pct_glp1", "GLP-1", BLUE),
        ("reportes_covid_antiviral", "pct_covid_antiviral",
         t("COVID · antivirales", "COVID · antivirals"), NEG),
        ("reportes_covid_repurposed", "pct_covid_repurposed",
         t("COVID · reutilizados", "COVID · repurposed"), "#C0894D"),
        ("reportes_gripe", "pct_gripe", t("Gripe", "Influenza"), "#6FCF97"),
        ("reportes_vsr", "pct_vsr", "VRS", "#B07FE8"),
    ]
    disponibles = [s for s in SERIES if s[0] in fam.columns]

    # La familia COVID se calcula en dos series separadas (antivirales
    # específicos y fármacos reutilizados durante la pandemia), pero en la
    # métrica de cabecera las sumo para dar la cifra del conjunto
    cols_covid = [c for c in ("reportes_covid_antiviral",
                              "reportes_covid_repurposed") if c in fam.columns]
    total_covid = int(fam[cols_covid].sum().sum()) if cols_covid else 0

    m1, m2, m3 = st.columns(3)
    m1.metric(t("Trimestres", "Quarters"), f"{fam['trimestre'].nunique()}")
    if "reportes_glp1" in fam:
        m2.metric(t("Reportes GLP-1", "GLP-1 reports"),
                  f"{int(fam['reportes_glp1'].sum()):,}")
    if cols_covid:
        m3.metric(t("Reportes COVID (ambas series)", "COVID reports (both series)"),
                  f"{total_covid:,}")
    st.divider()

    # Vista general en graficos pequeños
    st.markdown("##### " + t("Evolución por familia",
                             "Evolution by family"))
    st.caption(t("Cada familia con su propia escala: lo que se compara es la "
                 "forma de la curva, no el volumen. VRS es el virus "
                 "respiratorio sincitial, principal causa de bronquiolitis en "
                 "lactantes.",
                 "Each family on its own scale: what is compared is the shape of "
                 "the curve, not the volume. RSV is respiratory syncytial virus, "
                 "the main cause of bronchiolitis in infants."))

    # Reparto las miniaturas en filas de tres. La última fila suele quedar
    # incompleta (con cinco familias son 3 + 2), así que en ese caso añado
    # columnas vacías a los lados para que las miniaturas queden centradas en
    # lugar de pegadas a la izquierda con un hueco a la derecha.
    for i in range(0, len(disponibles), 3):
        bloque = disponibles[i:i + 3]
        if len(bloque) == 3:
            cols = st.columns(3, gap="medium")
        elif len(bloque) == 2:
            # Dos columnas de relleno a los lados, con la mitad de ancho, para
            # que las dos miniaturas queden del mismo tamaño que las de arriba.
            _l, c1, c2, _r = st.columns([1, 2, 2, 1], gap="medium")
            cols = [c1, c2]
        else:
            _l, c1, _r = st.columns([1, 2, 1], gap="medium")
            cols = [c1]

        for col, (c_abs, _c_pct, etq, color) in zip(cols, bloque):
            with col:
                st.markdown(f"**{etq}**")
                fig = px.area(fam, x="trimestre", y=c_abs,
                              labels={"trimestre": "", c_abs: ""})
                # Plotly no tiene una función para pasar de hexadecimal a rgba,
                # así que construyo el relleno a mano.
                rgb = tuple(int(color.lstrip("#")[j:j + 2], 16) for j in (0, 2, 4))
                fig.update_traces(line_color=color,
                                  fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.22)")
                fig = estilo_plotly(fig, 240)
                # En miniatura no cabe el nombre de los 24 trimestres, así que
                # dejo solo uno de cada cuatro (uno por año).
                fig.update_xaxes(tickvals=fam["trimestre"].iloc[::4],
                                 tickfont=dict(size=9))
                fig.update_yaxes(tickfont=dict(size=9))
                fig.update_layout(margin=dict(l=4, r=4, t=4, b=4),
                                  showlegend=False)
                mostrar(fig, key="sm_" + c_abs)
                st.caption(f"{int(fam[c_abs].sum()):,} " +
                           t("reportes", "reports"))
    st.divider()

    # COMPARACIÓN DIRECTA DE LAS DOS FAMILIAS GRANDES
    # Solo enfrento GLP-1 y antivirales COVID porque son las únicas dos series
    # con volúmenes del mismo orden de magnitud. Las otras tres se ven en las
    # miniaturas de arriba, cada una con su escala.
    st.markdown("##### " + t("GLP-1 frente a antivirales COVID",
                             "GLP-1 vs COVID antivirals"))
    fig = go.Figure()
    for c_abs, _c_pct, etq, color in disponibles:
        if c_abs not in ("reportes_glp1", "reportes_covid_antiviral"):
            continue
        fig.add_trace(go.Scatter(x=fam["trimestre"], y=fam[c_abs],
                      name=etq, mode="lines+markers",
                      line=dict(color=color, width=2.5)))
    mostrar(estilo_plotly(fig, 420), key="temp_abs")
    st.caption(t("Las dos familias de mayor volumen, con dinámicas opuestas: "
                 "los antivirales COVID caen desde 2022 mientras los GLP-1 "
                 "crecen de forma sostenida.",
                 "The two largest families, with opposite dynamics: COVID "
                 "antivirals decline from 2022 while GLP-1 grow steadily."))
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
        st.caption(t(f"{piv.shape[1]} fármacos de la familia GLP-1 con al menos "
                     "un reporte en el periodo.",
                     f"{piv.shape[1]} GLP-1 family drugs with at least one "
                     "report in the period."))

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
    st.dataframe(df.head(n), width='stretch', height=380)
    boton_csv(df, f"pharmasignal_{etq}.csv")


# Constructor de Graficas
# Etiquetas de las piezas de la frase. Se traducen aquí y no en el módulo de
# consultas porque el idioma es cuestión de presentación.
QUE_OPCIONES = {
    "efectos_adversos": ("Efectos adversos", "Adverse effects"),
    "farmacos": ("Fármacos asociados", "Associated drugs"),
    "indicaciones": ("Motivo de administración", "Reason for administration"),
    "gravedad": ("Gravedad de los casos", "Case severity"),
    "volumen": ("Volumen de notificaciones", "Report volume"),
}

DESGLOSE_OPCIONES = {
    "total": ("el total del periodo", "the whole period"),
    "trimestre": ("trimestre", "quarter"),
    "pais": ("país", "country"),
}

# Consulta con la que arranca la vista. Se elige por ser reconocible y tener
# volumen suficiente para que la primera gráfica diga algo.
INICIAL = {"que": "efectos_adversos", "entidad": "ozempic",
           "tipo": "farmaco", "desglose": "trimestre"}


@st.cache_data(show_spinner=False)
def _catalogos():
    # Los dos catálogos completos: los 34.003 nombres de fármaco y las
    # reacciones con su volumen. Se leen una vez y se reutilizan en cada rerun.
    return ce.catalogo_farmacos(), ce.catalogo_reacciones()


@st.cache_data(show_spinner=False)
def _consulta_cacheada(que, entidad, tipo_entidad, desglose, top):
    # La caché queda definida por las cuatro piezas de la frase, de modo que
    # volver a una combinación ya vista es inmediato. El error se devuelve como
    # texto en lugar de propagarse, una excepción dentro de una función cacheada
    # invalida la entrada y obligaría a recalcular en cada rerun.
    try:
        return ce.consultar(que, entidad, tipo_entidad, desglose, top), None
    except Exception as e:
        return None, str(e)


@st.cache_data(show_spinner=False)
def _desproporcion(farmaco, top):
    #Reacciones de un fármaco ordenadas por desproporción, no por frecuencia.
    senales = cargar("senales_prr_ror")
    if senales is None:
        return None
    df = senales[senales["drugname_norm"] == farmaco].copy()
    if not len(df):
        return df
    df["casos"] = (df["a"] - 0.5).round().astype(int)
    df = df[df["es_senal"] & (df["casos"] >= 20)]
    if not len(df):
        return df
    agg = df.groupby("pt_norm").agg(
        casos=("casos", "sum"), veces=("prr", "max")).reset_index()
    return agg.nlargest(top, "veces")


def _buscador(cat_far, cat_rea):
    """Campo de búsqueda de la entidad sobre la que se consulta.

    Se emplea un campo de texto libre y no un desplegable con el catálogo
    completo se trata de un conjunto con más de treinta y seis mil entidades y una lista de ese tamaño
    resulta inmanejable, además de obligar al navegador a recibirla entera.

    El usuario escribe cualquier término y confirma. Si lo escrito coincide
    exactamente con una entidad del catálogo se aplica directamente, si no, se
    ofrecen las coincidencias parciales para elegir.
    """
    st.markdown("**" + t("Busca aquí el fármaco o la reacción adversa",
                         "Search here for the drug or adverse effect") + "**")

    q = st.text_input(
        t("Búsqueda", "Search"),
        key="cst_busqueda", label_visibility="collapsed",
        placeholder=t("Escribe y pulsa Intro: ozempic, finasteride, hepatitis…",
                      "Type and press Enter: ozempic, finasteride, hepatitis…"))

    q = (q or "").strip().lower()
    if len(q) < 3:
        return

    # Si lo escrito coincide con una entidad del catálogo se aplica sin pedir
    # confirmación, obligar a elegir de una lista de un solo elemento sería un
    # paso innecesario.
    tipo, _, _ = ce.identificar_entidad(q, cat_far, cat_rea)
    if tipo and q != st.session_state["cst_entidad"]:
        st.session_state["cst_entidad"] = q
        st.session_state["cst_tipo"] = tipo
        st.rerun()
    if tipo:
        return

    sugerencias = ce.sugerir(q, cat_far, cat_rea, limite=8)
    if not sugerencias:
        st.caption(t(f"Sin coincidencias para «{q}». Los nombres están como "
                     "aparecen en FAERS, normalmente en inglés o con la marca "
                     "comercial: *ibuprofen*, no *ibuprofeno*.",
                     f"No matches for «{q}». Names appear as in FAERS, usually "
                     "in English or as a brand name."))
        return

    # Las coincidencias se reparten en filas de cuatro para que no se compriman
    # cuando el término es genérico y devuelve muchas.
    st.caption(t("Coincidencias:", "Matches:"))
    for i in range(0, len(sugerencias), 4):
        cols = st.columns(4)
        for col, (nombre, tipo_s, vol) in zip(cols, sugerencias[i:i + 4]):
            if col.button(nombre[:26], width='stretch',
                          key=f"sug_{tipo_s}_{nombre}",
                          help=f"{vol:,} " + t("notificaciones", "reports")):
                st.session_state["cst_entidad"] = nombre
                st.session_state["cst_tipo"] = tipo_s
                st.rerun()


def _grafica_constructor(datos, desglose, que, top, modo, escala_log):
    """Representa el resultado de una consulta del constructor.

    Toda consulta devuelve el mismo esquema de columnas, lo que permite que una
    única función cubra las trece combinaciones disponibles.
    """
    d = datos.copy()

    # Reacciones e indicaciones se traducen. Los nombres de fármaco no, ya que son
    # denominaciones internacionales y así los reconoce el usuario, como
    # confirmó la evaluación con los perfiles de dominio.
    if que in ("efectos_adversos", "indicaciones"):
        d[ce.COL_CATEGORIA] = tr_terms(d[ce.COL_CATEGORIA])

    if desglose != "total":
        if desglose == "pais":
            d["_etq"] = d[ce.COL_DESGLOSE].map(nombre_pais).fillna(d[ce.COL_DESGLOSE])
        else:
            d["_etq"] = d[ce.COL_DESGLOSE]

    # Sin desglose la representación es un ranking horizontal, que es la forma
    # más legible cuando las etiquetas son términos médicos largos.
    if desglose == "total":
        d = d.nlargest(top, ce.COL_VALOR)
        fig = px.bar(d.sort_values(ce.COL_VALOR), x=ce.COL_VALOR,
                     y=ce.COL_CATEGORIA, orientation="h",
                     labels={ce.COL_VALOR: t("Notificaciones", "Reports"),
                             ce.COL_CATEGORIA: ""})
        fig.update_traces(marker_color=BLUE)
        return eje_paises_grande(estilo_plotly(fig, 460)), d

    # Con desglose por país se emplea el peso relativo sobre el total de cada
    # país y no el volumen absoluto. Como bien se sabe FAERS sobre Estados Unidos aporta en torno al 70 % de
    # las notificaciones, de modo que un ranking absoluto reproduce siempre el
    # mismo orden con independencia de lo que se consulte.
    if desglose == "pais":
        col_valor = ce.COL_PORCENTAJE if ce.COL_PORCENTAJE in d.columns else ce.COL_VALOR
        principales = (d.groupby(ce.COL_CATEGORIA)[ce.COL_VALOR]
                        .sum().nlargest(min(top, 6)).index)
        d = d[d[ce.COL_CATEGORIA].isin(principales)]
        d = d.nlargest(min(len(d), top * 4), col_valor)
        fig = px.bar(d.sort_values(col_valor), x=col_valor, y="_etq",
                     color=ce.COL_CATEGORIA, orientation="h",
                     color_discrete_sequence=COLORWAY,
                     labels={col_valor: t("% de las notificaciones del país",
                                          "% of the country's reports"),
                             "_etq": "", ce.COL_CATEGORIA: ""})
        return eje_paises_grande(estilo_plotly(fig, 500)), d

    # Desglose temporal. Se limita a las categorías de mayor peso, una serie con
    # quince líneas superpuestas resulta ilegible.
    principales = (d.groupby(ce.COL_CATEGORIA)[ce.COL_VALOR]
                    .sum().nlargest(min(top, 8)).index)
    d = d[d[ce.COL_CATEGORIA].isin(principales)].sort_values("_etq")

    # La lectura en porcentaje responde a una pregunta distinta de la lectura en
    # absolutos, un aumento de casos puede deberse solo a que ha crecido la
    # notificación del fármaco, mientras que un aumento de la proporción indica
    # un cambio real de perfil.
    col_valor = ce.COL_VALOR
    etiqueta_y = t("Notificaciones", "Reports")
    if modo == "pct" and ce.COL_PORCENTAJE in d.columns:
        col_valor = ce.COL_PORCENTAJE
        etiqueta_y = t("% del total del trimestre", "% of the quarter's total")

    if modo == "apilada":
        fig = px.area(d, x="_etq", y=col_valor, color=ce.COL_CATEGORIA,
                      color_discrete_sequence=COLORWAY,
                      labels={"_etq": "", col_valor: etiqueta_y,
                              ce.COL_CATEGORIA: ""})
    else:
        fig = px.line(d, x="_etq", y=col_valor, color=ce.COL_CATEGORIA,
                      markers=True, color_discrete_sequence=COLORWAY,
                      labels={"_etq": "", col_valor: etiqueta_y,
                              ce.COL_CATEGORIA: ""})

    fig = estilo_plotly(fig, 470)
    if escala_log:
        fig.update_yaxes(type="log")
    return fig, d


def crear_constructor():
    st.subheader(t("Constructor", "Builder"))
    intro(t("Elige qué quieres ver y sobre qué. La gráfica se genera sola.",
            "Choose what you want to see and about what. The chart builds "
            "itself."))

    cat_far, cat_rea = _catalogos()

    # Estado inicial. La vista arranca con una consulta ya resuelta para que la
    # primera pantalla muestre un resultado y no un formulario vacío.
    if "cst_que" not in st.session_state:
        st.session_state["cst_que"] = INICIAL["que"]
        st.session_state["cst_entidad"] = INICIAL["entidad"]
        st.session_state["cst_tipo"] = INICIAL["tipo"]
        st.session_state["cst_desglose"] = INICIAL["desglose"]

    entidad = st.session_state["cst_entidad"]
    tipo_entidad = st.session_state["cst_tipo"]

    # Las opciones se filtran, los efectos adversos se consultan sobre un fármaco y los fármacos asociados sobre una
    # reacción, de modo que ofrecer ambas a la vez llevaría a combinaciones sin
    # resultado. El ajuste se hace antes de pintar la frase para que esta
    # refleje siempre lo que se va a representar.
    compatibles = [k for k, v in ce.MATRIZ.items()
                   if v["entidad"] in (tipo_entidad, "ambas")]
    if st.session_state["cst_que"] not in compatibles:
        st.session_state["cst_que"] = compatibles[0]
    que = st.session_state["cst_que"]

    disponibles = ce.MATRIZ[que]["desgloses"]
    if st.session_state["cst_desglose"] not in disponibles:
        st.session_state["cst_desglose"] = disponibles[0]
    desglose = st.session_state["cst_desglose"]

    # Composición de la frase
    # Las tres piezas se presentan arriba para que el usuario sepa que esta construyendo
    i = 0 if L == "es" else 1
    st.markdown(
        f"<div class='frase'>{t('Mostrar', 'Show')} "
        f"<b>{QUE_OPCIONES[que][i]}</b> {t('de', 'of')} "
        f"<b>{entidad}</b> {t('visto por', 'broken down by')} "
        f"<b>{DESGLOSE_OPCIONES[desglose][i]}</b></div>",
        unsafe_allow_html=True)

    p1, p2 = st.columns(2, gap="large")

    with p1:
        etiquetas = [QUE_OPCIONES[k][i] for k in compatibles]
        sel = st.selectbox(t("Qué mostrar", "What to show"), etiquetas,
                           index=compatibles.index(que), key="cst_sel_que")
        if compatibles[etiquetas.index(sel)] != que:
            st.session_state["cst_que"] = compatibles[etiquetas.index(sel)]
            st.rerun()

    with p2:
        etq_desg = [DESGLOSE_OPCIONES[k][i] for k in disponibles]
        sel_d = st.selectbox(t("Visto por", "Broken down by"), etq_desg,
                             index=disponibles.index(desglose),
                             key="cst_sel_desglose")
        if disponibles[etq_desg.index(sel_d)] != desglose:
            st.session_state["cst_desglose"] = disponibles[etq_desg.index(sel_d)]
            st.rerun()

    # El buscador va debajo de los dos selectores porque cambiar la entidad es
    # la acción más frecuente y conviene tenerla a mano.
    _buscador(cat_far, cat_rea)

    # El umbral del precálculo no filtra la búsqueda, la entidad se consulta
    # igualmente y se informa de que su lectura es frágil, en lugar de negar su
    # existencia.
    _, volumen_ent, supera = ce.identificar_entidad(entidad, cat_far, cat_rea)
    if volumen_ent and not supera:
        st.warning(t(f"«{entidad}» acumula {volumen_ent:,} notificaciones, por "
                     "debajo del umbral de fiabilidad. Los resultados pueden no "
                     "ser representativos.",
                     f"«{entidad}» has {volumen_ent:,} reports, below the "
                     "reliability threshold. Results may not be representative."))

    with st.expander(t("Ajustes", "Settings"), expanded=False):
        a1, a2, a3 = st.columns(3)
        top = a1.slider(t("Nº de elementos", "Nº of items"), 3, 15, 8,
                        key="cst_top")
        if desglose == "trimestre":
            modos = {t("Líneas", "Lines"): "lineas",
                     t("Área apilada", "Stacked area"): "apilada",
                     t("Porcentaje", "Percentage"): "pct"}
            modo = modos[a2.selectbox(t("Representación", "Display"),
                                      list(modos), key="cst_modo")]
            escala_log = a3.checkbox(t("Escala logarítmica", "Log scale"),
                                     value=False, key="cst_log")
        else:
            modo, escala_log = "lineas", False

    st.divider()

    # Las tablas del explorador ordenan por frecuencia y encabezan siempre términos inespecíficos
    orden_desproporcion = False
    if que == "efectos_adversos" and desglose == "total":
        modo_orden = st.radio(
            t("Ordenar por", "Sort by"),
            [t("Más notificados", "Most reported"),
             t("Más de lo esperado", "More than expected")],
            horizontal=True, key="cst_orden", label_visibility="collapsed")
        orden_desproporcion = modo_orden in (t("Más de lo esperado",
                                               "More than expected"),)

    ph = st.empty()
    overlay_cargando(ph, t("Generando gráfica…", "Building chart…"))

    if orden_desproporcion:
        desp = _desproporcion(entidad, top)
        ph.empty()
        if desp is None or not len(desp):
            st.info(t("No hay combinaciones que superen los criterios de señal "
                      "con respaldo suficiente para este fármaco.",
                      "No combinations pass the signal criteria with enough "
                      "support for this drug."))
            return
        desp = desp.copy()
        desp["disp"] = tr_terms(desp["pt_norm"])
        fig = px.bar(desp.sort_values("veces"), x="veces", y="disp",
                     orientation="h", custom_data=["casos"],
                     labels={"veces": t("Veces más de lo esperado",
                                        "× more than expected"), "disp": ""})
        fig.update_traces(
            marker_color=BLUE,
            hovertemplate="<b>%{y}</b><br>×%{x:.1f} "
                          + t("más de lo esperado", "more than expected")
                          + "<br>%{customdata[0]:,} "
                          + t("notificaciones", "reports") + "<extra></extra>")
        fig = eje_paises_grande(estilo_plotly(fig, 460))
        salida = desp[["pt_norm", "casos", "veces"]]
        mostrar(fig, key=f"cst_{que}_{desglose}_desp")
        st.caption(t("Solo efectos que superan los criterios estadísticos de "
                     "señal y con al menos 20 casos detrás.",
                     "Only effects passing the statistical signal criteria with "
                     "at least 20 cases."))
    else:
        datos, error = _consulta_cacheada(que, entidad, tipo_entidad,
                                          desglose, top)
        ph.empty()
        if error:
            st.info(error)
            return
        if datos is None or not len(datos):
            st.info(t(f"No hay datos suficientes de «{entidad}» para esta consulta.",
                      f"Not enough data for «{entidad}» in this query."))
            return
        fig, salida = _grafica_constructor(datos, desglose, que, top,
                                           modo, escala_log)
        mostrar(fig, key=f"cst_{que}_{desglose}")

    # Advertencias propias de cada consulta. Van junto a la gráfica y no en la
    # documentación porque son necesarias para leerla correctamente.
    if que == "gravedad":
        st.caption(t("Los porcentajes suman más de cien: una misma notificación "
                     "puede registrar varios desenlaces, por ejemplo "
                     "hospitalización y riesgo vital.",
                     "Percentages add up to more than one hundred: a single "
                     "report may record several outcomes."))
    if que == "indicaciones":
        st.caption(t("Se excluye «indicación no especificada», que representa el "
                     "38 % de los registros y desplazaría al resto.",
                     "«Unknown indication» is excluded: it accounts for 38 % of "
                     "records and would displace all others."))
    if desglose == "pais":
        st.caption(t("Se representa el peso sobre el total de notificaciones de "
                     "cada país, no el volumen absoluto: Estados Unidos aporta "
                     "en torno al 70 % del total y dominaría cualquier ranking.",
                     "Share of each country's own total is shown, not absolute "
                     "volume: the United States accounts for around 70 % of all "
                     "reports."))

    # El nombre del fichero lleva la consulta completa, de modo que una carpeta
    # de descargas sigue siendo legible sin abrir los ficheros.
    slug = f"{que}_{entidad}_{desglose}".replace(" ", "_").replace("/", "-")
    e1, e2 = st.columns(2)
    with e1:
        boton_html(fig, f"pharmasignal_{slug}.html")
    with e2:
        boton_csv(salida, f"pharmasignal_{slug}.csv")
    st.info(t("**Importante:** que un efecto se notifique junto a un fármaco no "
              "prueba que el fármaco lo cause. Son hipótesis a investigar.",
              "**Important:** an effect being reported alongside a drug does not "
              "prove causation. These are hypotheses to investigate."))


# Enrutado
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