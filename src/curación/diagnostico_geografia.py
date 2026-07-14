"""
diagnostico_geografia.py

Diagnóstico del hallazgo ES→EU en FAERS.
Analiza la evolución del código de país España a lo largo
de los 24 trimestres para cuantificar el alcance del cambio
de codificación detectado a partir de 2025Q3.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Diagnóstico-Geografía") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

demo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_curado")

# Evolución de ES y EU por trimestre
print("\nEvolución de los códigos ES y EU por trimestre:")
demo.filter(col("reporter_country").isin("ES", "EU")) \
    .groupBy("trimestre", "reporter_country") \
    .count() \
    .orderBy("trimestre", "reporter_country") \
    .show(60, truncate=False)

# Totales
total_es = demo.filter(col("reporter_country") == "ES").count()
total_eu = demo.filter(col("reporter_country") == "EU").count()

print(f"\nTotal reportes con código ES: {total_es:,}")
print(f"Total reportes con código EU: {total_eu:,}")

# Top 15 países para contexto
print("\nTop 15 países notificadores:")
demo.groupBy("reporter_country").count() \
    .orderBy(col("count").desc()) \
    .show(15, truncate=False)

spark.stop()