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

Todas las tablas se unen posteriormente por el campo ISR (primaryid),
que actúa como identificador único de cada notificación.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit
import os
import glob

spark = SparkSession.builder \
    .appName("PharmaSignal-Ingesta") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .getOrCreate()

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







