"""
ingesta_faers.py

Pipeline de ingesta completa de los datos FAERS 2020-2025.
Leerá los 24 trimestres de las 7 tablas ASCII de FAERS y escribe
cada una consolidada en formato Delta Lake para su posterior curación.

Las 7 tablas de FAERS son:
- DEMO: datos demográficos del paciente (tabla maestra)
- DRUG: fármacos implicados en el evento adverso
- REAC: reacciones adversas notificadas (terminología MedDRA)
- OUTC: desenlaces clínicos del evento
- INDI: indicaciones terapéuticas de los fármacos
- THER: información de la terapia (dosis, fechas)
- RPSR: fuente de la notificación

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit
from delta import configure_spark_with_delta_pip
import os
import glob

builder = SparkSession.builder \
    .appName("PharmaSignal-Ingesta") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

RAW_PATH = os.path.expanduser("~/pharmasignal/data/raw")
CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Definimos las 7 tablas con su nombre y patrón de fichero
TABLAS_FAERS = [
    ("demo", "DEMO*.txt"),
    ("drug", "DRUG*.txt"),
    ("reac", "REAC*.txt"),
    ("outc", "OUTC*.txt"),
    ("indi", "INDI*.txt"),
    ("ther", "THER*.txt"),
    ("rpsr", "RPSR*.txt"),
]

def ingestar_tabla(nombre_tabla, patron_fichero):
    """
    Leerá una tabla FAERS de todos los trimestres disponibles,
    añade una columna 'trimestre' para trazabilidad temporal
    y devolverá un DataFrame consolidado.
    """
    ficheros = sorted(glob.glob(
        f"{RAW_PATH}/faers_ascii_*/ASCII/{patron_fichero}"
    ))

    print(f"\n{'='*50}")
    print(f"INGESTA: {nombre_tabla.upper()} — {len(ficheros)} trimestres")
    print(f"{'='*50}")

    if not ficheros:
        print(f"  ERROR: no se encontraron ficheros para {nombre_tabla}")
        return None

    dfs = []
    total_filas = 0

    for fichero in ficheros:
        # Extraemos el identificador del trimestre del nombre de la carpeta
        trimestre = fichero.split("/")[-3].replace("faers_ascii_", "")

        df = spark.read \
            .option("header", "true") \
            .option("sep", "$") \
            .csv(fichero)

        # Añadimos columna trimestre para poder filtrar temporalmente después
        df = df.withColumn("trimestre", lit(trimestre))
        filas = df.count()
        total_filas += filas
        dfs.append(df)
        print(f"  {trimestre}: {filas:,} filas")

    # Consolidamos todos los trimestres en un único DataFrame
    # unionByName permite que las tablas con columnas distintas entre trimestres
    # se unan correctamente rellenando con null las columnas que falten
    consolidado = dfs[0]
    for df in dfs[1:]:
        consolidado = consolidado.unionByName(df, allowMissingColumns=True)

    print(f"\n  Total {nombre_tabla.upper()}: {total_filas:,} filas")
    return consolidado

def guardar_tabla(df, nombre_tabla):
    """
    Persistirá el DataFrame consolidado en formato Delta Lake.
    El modo 'overwrite' nos permite reejecutar el pipeline
    desde cero obteniendo siempre los mismos resultados
    """
    ruta = f"{CURATED_PATH}/{nombre_tabla}"
    df.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .save(ruta)
    print(f"Guardado en: {ruta}")


# Procesamos las 7 tablas en orden
for nombre, patron in TABLAS_FAERS:
    df = ingestar_tabla(nombre, patron)
    if df is not None:
        guardar_tabla(df, nombre)

print("\n" + "="*50)
print("INGESTA COMPLETA — todas las tablas procesadas")
print("="*50)

spark.stop()


























