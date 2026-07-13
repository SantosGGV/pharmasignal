"""
curar_reac.py

Curación de la tabla REAC de FAERS.
Reglas aplicadas:

1. Alineación con DEMO curado:
En este caso se retienen únicamente los registros cuyo primaryid existe en la tabla DEMO
previamente curada, eliminando las reacciones de reportes duplicados.

2. Normalización del término MedDRA (pt):
Los términos de reacción adversa siguen la terminología MedDRA y en FAERS ya vienen
relativamente estandarizados, pero presentan ciertas variantes de mayúsculas, espacios
y puntuación que se normaliza.

3. Eliminiación de registros sin término de reacción:
Los registros con pt nulo o vacío se descartan ya que no aportan información
analítica utilizable.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, trim, lower, upper, regexp_replace, when
)
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Curación-REAC") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Cargamos REAC desde Delta Lake
reac = spark.read.format("delta").load(f"{CURATED_PATH}/reac")
total_inicial = reac.count()
print(f"\nRegistros iniciales REAC: {total_inicial:,}")

# Cargamos DEMO curado para alinear por primaryid
demo_curado = spark.read.format("delta") \
    .load(f"{CURATED_PATH}/demo_curado")
primaryids_validos = demo_curado.select("primaryid").distinct()

# Regla 1. Alineación con DEMO curado
reac_alineado = reac.join(primaryids_validos, on="primaryid", how="inner")
total_alineado = reac_alineado.count()
print(f"Tras alineación con DEMO curado: {total_alineado:,} "
      f"({total_inicial - total_alineado:,} registros eliminados)")

# Regla 2. Normalización del término MedDRA
# Como se mencionaba al principio, los términos MedDRA en FAERS vienen en inglés y
# relativamente estandarizados, pero pueden tener variantes de mayúsculas y espacios.
# Normalizamos a minúsculas con espacios limpios para facilitar los joins
# en el cálculo de PRR/ROR
reac_norm = reac_alineado \
    .withColumn("pt_norm",
        trim(lower(
            regexp_replace(col("pt"), r'\s+', ' ')
        ))
    )

# Regla 3. Eliminación de registros sin término de reacción
sin_pt = reac_norm.filter(
    col("pt").isNull() | (trim(col("pt")) == "")
).count()

reac_limpio = reac_norm.filter(
    col("pt_norm").isNotNull() & (col("pt_norm") != "")
)

print(f"\nRegistros sin término MedDRA eliminados: {sin_pt:,}")

total_final = reac_limpio.count()
print(f"\nRegistros finales REAC curado: {total_final:,}")
print(f"Reducción total respecto al original: "
      f"{total_inicial - total_final:,} registros")

# Términos MedDRA únicos tras normalización
terminos_unicos = reac_limpio.select("pt_norm").distinct().count()
print(f"\nTérminos MedDRA únicos: {terminos_unicos:,}")

# Top 20 reacciones más notificadas
print("\nTop 20 reacciones adversas más notificadas:")
reac_limpio.groupBy("pt_norm").count() \
    .orderBy(col("count").desc()) \
    .show(20, truncate=False)

# Guardamos REAC curado en Delta Lake
ruta_salida = f"{CURATED_PATH}/reac_curado"
reac_limpio.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(ruta_salida)

print(f"\nREAC curado guardado en: {ruta_salida}")
print("\n=== SCHEMA REAC CURADO ===")
reac_limpio.printSchema()

spark.stop()

































