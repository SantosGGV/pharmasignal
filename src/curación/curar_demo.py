"""
curar_demo.py

Curación de la tabla DEMO de FAERS
Se aplican las siguientes reglas de curación:

1. Deduplicación: FAERS permite múltiples versiones del mismo caso.
Se conserva únicamente la versión más reciente de cada caseid para evitar
de tal manera el doble conteo de reportes.

2. Normalización de la edad: el campo age_cod indica la unidad de medida
(YR= años, MON=meses, DEC=décadas, WK=semanas, DY=días). Se convierte todo
a años y se filtran los valores fuera del rango 0-120.

3. Normalización de fechas: los campos de fecha vienen como enteros
(ej: 20200110). Se convierten a tipo fecha real.

4. Estandarización de campos de texto: sex y reporter_country se normalizan a MAYUS
y se eliminan espacios.

"""

from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    col, max as spark_max, when, trim, upper,
    to_date, regexp_replace
)
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Curación-DEMO") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Cargamos DEMO desde Delta Lake
demo = spark.read.format("delta").load(f"{CURATED_PATH}/demo")
total_inicial = demo.count()
print(f"\nRegistros iniciales DEMO: {total_inicial:,}")

# Regla 1 - Deduplicación por caseversion
# FAERS puede contener varias versiones del mismo reporte (caseid).
# Nos quedamos solo con la versión más reciente de cada caso.
ventana = Window.partitionBy("caseid")
demo_dedup = demo.withColumn("max_version", spark_max("caseversion").over(ventana)) \
                 .filter(col("caseversion") == col("max_version")) \
                 .drop("max_version")

total_dedup = demo_dedup.count()
print(f"Tras deduplicación: {total_dedup:,} ({total_inicial - total_dedup:,} duplicados eliminados)")

# Regla 2. Normalización de edad a años
# Convertimos todas las unidades a años para poder filtrar y analizar.
# Unidades: YR (años), MON (meses), DEC (décadas), WK (semanas), DY (días)
demo_edad = demo_dedup.withColumn(
    "age_years",
    when(col("age_cod") == "YR",  col("age").cast("double"))
    .when(col("age_cod") == "DEC", col("age").cast("double") * 10)
    .when(col("age_cod") == "MON", col("age").cast("double") / 12)
    .when(col("age_cod") == "WK",  col("age").cast("double") / 52)
    .when(col("age_cod") == "DY",  col("age").cast("double") / 365)
    .otherwise(None)
)
























