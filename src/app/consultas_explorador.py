"""
consultas_explorador.py

Capa de acceso a datos del constructor de gráficas.

El constructor plantea una frase de tres piezas: qué mostrar, sobre qué entidad
y bajo qué desglose. Cada combinación válida de esas tres piezas se resuelve
contra una tabla materializada distinta. Este módulo concentra eso, de modo que la vista solo se ocupa de representar el resultado
y no necesita conocer ni los nombres de las tablas ni los de sus columnas.

"""

import os

import pandas as pd
from deltalake import DeltaTable

CURATED = os.path.expanduser("~/pharmasignal/data/curated")

# Nombres normalizados que devuelve toda consulta. La vista siempre encuentra
# las mismas columnas, lo que permite que una única función de representación
# sirva para las trece combinaciones disponibles.
COL_CATEGORIA = "categoria"
COL_DESGLOSE = "desglose"
COL_VALOR = "valor"
COL_PORCENTAJE = "porcentaje"

# Códigos de desenlace de FAERS. Se traducen aquí porque en la tabla se
# almacenan tal como los publica la FDA y en la interfaz deben poder leerse.
DESENLACES = {
    "DE": "Muerte",
    "LT": "Riesgo vital",
    "HO": "Hospitalización",
    "DS": "Discapacidad",
    "CA": "Anomalía congénita",
    "RI": "Intervención requerida",
    "OT": "Otro",
}

# Umbrales del precálculo. No filtran la búsqueda: se emplean para advertir al
# usuario cuando la entidad consultada queda por debajo y su lectura pierde
# fiabilidad.
MIN_REPORTES_FARMACO = 5000
MIN_CASOS_REACCION = 1000

# Combinaciones disponibles. La interfaz consulta esta estructura para no
# ofrecer desgloses que no tienen tabla detrás y devolverían un resultado vacío.
MATRIZ = {
    "efectos_adversos": {"entidad": "farmaco", "desgloses": ["total", "trimestre", "pais"]},
    "farmacos": {"entidad": "reaccion", "desgloses": ["total", "trimestre", "pais"]},
    "indicaciones": {"entidad": "farmaco", "desgloses": ["total", "trimestre"]},
    "gravedad": {"entidad": "farmaco", "desgloses": ["total", "trimestre"]},
    "volumen": {"entidad": "ambas", "desgloses": ["trimestre", "pais"]},
}

# Motivo de las combinaciones ausentes, para mostrarlo en la interfaz en lugar
# de limitarse a ocultar la opción.
MOTIVO_NO_DISPONIBLE = {
    ("indicaciones", "pais"): "El cruce de indicación y país no se ha materializado: la "
                             "indicación falta en el 38 % de los registros y el reparto "
                             "por país dejaría de ser interpretable.",
    ("gravedad", "pais"): "El cruce de desenlace y país no se ha materializado. La "
                          "comparación geográfica de gravedad se ofrece en la vista de "
                          "análisis geográfico.",
    ("volumen", "total"): "El volumen total de una entidad se muestra en el buscador de "
                          "la portada. Aquí interesa su evolución o su reparto.",
}


def _leer(nombre):
    #Lee una tabla Delta materializada y la devuelve como DataFrame de pandas.
    ruta = f"{CURATED}/{nombre}"
    if not os.path.isdir(ruta):
        raise FileNotFoundError(
            f"La tabla {nombre} no está disponible. Ejecuta el precálculo del "
            "explorador y recarga.")
    return DeltaTable(ruta).to_pandas()


# CATÁLOGOS

def catalogo_farmacos():
    #Catálogo completo de fármacos con su volumen de notificaciones.
    df = _leer("expl_catalogo_farmacos")
    return df.sort_values("reportes", ascending=False).reset_index(drop=True)


def catalogo_reacciones():
    """Catálogo completo de reacciones con su volumen de casos."""
    df = _leer("expl_catalogo_reacciones")
    return df.sort_values("casos", ascending=False).reset_index(drop=True)


def identificar_entidad(termino, cat_farmacos, cat_reacciones):
    #Determina si un término corresponde a un fármaco o a una reacción.
    t = str(termino).strip().lower()

    coincide = cat_farmacos[cat_farmacos["drugname_norm"] == t]
    if not coincide.empty:
        vol = int(coincide.iloc[0]["reportes"])
        return "farmaco", vol, vol >= MIN_REPORTES_FARMACO

    coincide = cat_reacciones[cat_reacciones["pt_norm"] == t]
    if not coincide.empty:
        vol = int(coincide.iloc[0]["casos"])
        return "reaccion", vol, vol >= MIN_CASOS_REACCION

    return None, 0, False


def sugerir(termino, cat_farmacos, cat_reacciones, limite=8):
    #Devuelve términos de ambos catálogos que contienen el texto introducido.
    t = str(termino).strip().lower()
    if len(t) < 3:
        return []

    f = cat_farmacos[cat_farmacos["drugname_norm"].str.contains(
        t, regex=False, na=False)].head(limite)
    r = cat_reacciones[cat_reacciones["pt_norm"].str.contains(
        t, regex=False, na=False)].head(limite)

    sugerencias = [(n, "farmaco", int(v)) for n, v in
                   zip(f["drugname_norm"], f["reportes"])]
    sugerencias += [(n, "reaccion", int(v)) for n, v in
                    zip(r["pt_norm"], r["casos"])]

    sugerencias.sort(key=lambda x: x[2], reverse=True)
    return sugerencias[:limite]


# NORMALIZACIÓN DEL RESULTADO

def _normalizar(df, categoria, desglose, valor, porcentaje=None):
    #Renombra las columnas de una tabla al esquema común de la vista.
    columnas = {categoria: COL_CATEGORIA, valor: COL_VALOR}
    if desglose is not None:
        columnas[desglose] = COL_DESGLOSE
    if porcentaje is not None:
        columnas[porcentaje] = COL_PORCENTAJE

    salida = df.rename(columns=columnas)
    conservar = [c for c in
                 [COL_CATEGORIA, COL_DESGLOSE, COL_VALOR, COL_PORCENTAJE]
                 if c in salida.columns]
    return salida[conservar].reset_index(drop=True)


def _a_total(df, categoria, valor):
    #Colapsa una tabla desglosada por trimestre en el total del periodo.
    return df.groupby(categoria, as_index=False)[valor].sum()


# CONSULTAS
def efectos_adversos(farmaco, desglose, top=10):
    """Reacciones más notificadas para un fármaco.

    Las tablas ordenan por frecuencia, no por desproporción."""
    if desglose == "trimestre":
        df = _leer("expl_farmaco_reaccion_trimestre")
        df = df[df["drugname_norm"] == farmaco]
        return _normalizar(df, "pt_norm", "trimestre", "casos", "pct_farmaco_trim")

    if desglose == "pais":
        df = _leer("expl_farmaco_reaccion_pais")
        df = df[df["drugname_norm"] == farmaco]
        return _normalizar(df, "pt_norm", "reporter_country", "casos", "pct_pais")

    df = _leer("expl_farmaco_reaccion_trimestre")
    df = df[df["drugname_norm"] == farmaco]
    df = _a_total(df, "pt_norm", "casos").nlargest(top, "casos")
    return _normalizar(df, "pt_norm", None, "casos")


def farmacos_de_reaccion(reaccion, desglose, top=10):
    """Fármacos más notificados junto a una reacción determinada."""
    if desglose == "trimestre":
        df = _leer("expl_reaccion_farmaco_trimestre")
        df = df[df["pt_norm"] == reaccion]
        return _normalizar(df, "drugname_norm", "trimestre", "casos",
                           "pct_reaccion_trim")

    if desglose == "pais":
        df = _leer("expl_reaccion_farmaco_pais")
        df = df[df["pt_norm"] == reaccion]
        return _normalizar(df, "drugname_norm", "reporter_country", "casos",
                           "pct_pais")

    df = _leer("expl_reaccion_farmaco_trimestre")
    df = df[df["pt_norm"] == reaccion]
    df = _a_total(df, "drugname_norm", "casos").nlargest(top, "casos")
    return _normalizar(df, "drugname_norm", None, "casos")


def indicaciones(farmaco, desglose, top=10):
    """Indicaciones registradas para un fármaco.

    Es la consulta que hace visible un cambio de uso a lo largo del tiempo.
    """
    if desglose == "trimestre":
        df = _leer("expl_farmaco_indicacion_trimestre")
        df = df[df["drugname_norm"] == farmaco]
        return _normalizar(df, "indi_pt_norm", "trimestre", "reportes",
                           "pct_farmaco_trim")

    df = _leer("expl_farmaco_indicacion")
    df = df[df["drugname_norm"] == farmaco].nlargest(top, "reportes")
    return _normalizar(df, "indi_pt_norm", None, "reportes")


def gravedad(farmaco, desglose):
    """Desenlaces registrados en las notificaciones de un fármaco.

    Los porcentajes de esta consulta suman más de cien, una misma notificación
    puede registrar varios desenlaces simultáneos
    """
    if desglose == "trimestre":
        df = _leer("expl_farmaco_gravedad_trimestre")
        df = df[df["drugname_norm"] == farmaco].copy()
        df["outc_cod_norm"] = df["outc_cod_norm"].map(DESENLACES).fillna(
            df["outc_cod_norm"])
        return _normalizar(df, "outc_cod_norm", "trimestre", "reportes",
                           "pct_farmaco_trim")

    df = _leer("expl_farmaco_gravedad")
    df = df[df["drugname_norm"] == farmaco].copy()
    df["outc_cod_norm"] = df["outc_cod_norm"].map(DESENLACES).fillna(
        df["outc_cod_norm"])
    return _normalizar(df, "outc_cod_norm", None, "reportes", "pct_farmaco")


def volumen(entidad, tipo, desglose):
    """Evolución o distribución del número de notificaciones.

    Es la única consulta que admite indistintamente un fármaco o una reacción,
    porque el recuento de notificaciones es una magnitud común a ambos.
    """
    if tipo == "farmaco":
        tabla = ("expl_farmaco_trimestre" if desglose == "trimestre"
                 else "expl_farmaco_pais")
        df = _leer(tabla)
        df = df[df["drugname_norm"] == entidad]
        categoria, columna_valor = "drugname_norm", "reportes"
    else:
        tabla = ("expl_reaccion_trimestre" if desglose == "trimestre"
                 else "expl_reaccion_pais")
        df = _leer(tabla)
        df = df[df["pt_norm"] == entidad]
        categoria, columna_valor = "pt_norm", "casos"

    if desglose == "trimestre":
        return _normalizar(df, categoria, "trimestre", columna_valor)
    return _normalizar(df, categoria, "reporter_country", columna_valor,
                       "pct_pais")


def consultar(que, entidad, tipo_entidad, desglose, top=10):
    """Punto de entrada único del constructor.

    La vista invoca siempre esta función y no las anteriores
    """
    if que not in MATRIZ:
        raise ValueError(f"Consulta no reconocida: {que}")

    if desglose not in MATRIZ[que]["desgloses"]:
        raise ValueError(MOTIVO_NO_DISPONIBLE.get(
            (que, desglose), "Esa combinación no está disponible."))

    if que == "efectos_adversos":
        return efectos_adversos(entidad, desglose, top)
    if que == "farmacos":
        return farmacos_de_reaccion(entidad, desglose, top)
    if que == "indicaciones":
        return indicaciones(entidad, desglose, top)
    if que == "gravedad":
        return gravedad(entidad, desglose)
    return volumen(entidad, tipo_entidad, desglose)