"""
curar_outc.py

Curación de la tabla OUTC de FAERS.
Contiene los desenlaces clínicos de cada reporte.

Códigos reportados de desenlaces en FAERS:
- DE: Death (muerte)
- LT: Life-Threatening (riesgo vital)
- HO: Hospitalization (hospitalización)
- DS: Disability (discapacidad)
- CA: Congenital Anomaly (anomalía congénita)
- RI: Required Intervention (intervención médica requerida)
- OT: Other (otro)

Reglas aplicadas:
1. Alineación con DEMO curado por primaryid.
2. Normalización del código de desenlace a mayúsculas.
3. Eliminación de registros con outc_cod nulo o desconocido.
4. Generación de métricas de gravedad por desenlace.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim, upper
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Curación-OUTC") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Cargamos OUTC desde Delta Lake
outc = spark.read.format("delta").load(f"{CURATED_PATH}/outc")
total_inicial = outc.count()
print(f"\nRegistros iniciales OUTC: {total_inicial:,}")

# Cargamos DEMO curado para alinear por primaryid
demo_curado = spark.read.format("delta") \
    .load(f"{CURATED_PATH}/demo_curado")
primaryids_validos = demo_curado.select("primaryid").distinct()

# Regla 1. Alineación con DEMO curado
outc_alineado = outc.join(primaryids_validos, on="primaryid", how="inner")
total_alineado = outc_alineado.count()
print(f"Tras alineación con DEMO curado: {total_alineado:,} "
      f"({total_inicial - total_alineado:,} registros eliminados)")

# Regla 2. Normalización del código desenlace
outc_norm = outc_alineado.withColumn(
    "outc_cod_norm", upper(trim(col("outc_cod")))
)

# Regla 3. Eliminación de registros sin código de desenlace
sin_outc = outc_norm.filter(
    col("outc_cod").isNull() | (trim(col("outc_cod")) == "")
).count()

outc_limpio = outc_norm.filter(
    col("outc_cod_norm").isNotNull() & (col("outc_cod_norm") != "")
)

print(f"\nRegistros sin código de desenlace eliminados: {sin_outc:,}")

total_final = outc_limpio.count()
print(f"\nRegistros finales OUTC curado: {total_final:,}")
print(f"Reducción total respecto al original: "
      f"{total_inicial - total_final:,} registros")


# Regla 4. Distribución por tipo de desenlace
print("\nDistribución por código de desenlace:")
outc_limpio.groupBy("outc_cod_norm").count() \
    .orderBy(col("count").desc()) \
    .show(truncate=False)

# Guardamos OUTC curado en Delta Lake
ruta_salida = f"{CURATED_PATH}/outc_curado"
outc_limpio.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(ruta_salida)

print(f"\nOUTC curado guardado en: {ruta_salida}")
print("\n=== SCHEMA OUTC CURADO ===")
outc_limpio.printSchema()

spark.stop()








