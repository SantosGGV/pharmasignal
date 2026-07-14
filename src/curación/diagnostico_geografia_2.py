"""
diagnostico_geografia_2.py

Segunda fase del diagnóstico ES→EU.
Comprueba si el campo occr_country (país de ocurrencia del evento)
conserva la codificación por país cuando reporter_country
ha sido recodificado a EU en 2025Q3-Q4.
1
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Diagnóstico-Geografía-2") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

demo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_curado")

# Vemos qué contiene occr_country en los reportes con reporter_country = EU
# durante los trimestres afectados por la recodificación
print("\nDistribución de occr_country en reportes EU de 2025q3-q4:")
demo.filter(col("trimestre").isin("2025q3", "2025q4")) \
    .filter(col("reporter_country") == "EU") \
    .groupBy("occr_country") \
    .count() \
    .orderBy(col("count").desc()) \
    .show(25, truncate=False)

# Comprobamos también si occr_country mantiene ES en esos trimestres
es_en_occr = demo.filter(col("trimestre").isin("2025q3", "2025q4")) \
    .filter(col("occr_country") == "ES") \
    .count()

print(f"\nReportes con occr_country = ES en 2025q3-q4: {es_en_occr:,}")

# Para contraste, vemos la relación en un trimestre anterior a la recodificación
print("\nDistribución de occr_country en reportes ES de 2025q2 (control):")
demo.filter(col("trimestre") == "2025q2") \
    .filter(col("reporter_country") == "ES") \
    .groupBy("occr_country") \
    .count() \
    .orderBy(col("count").desc()) \
    .show(10, truncate=False)

spark.stop()