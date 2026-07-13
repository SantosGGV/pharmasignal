"""
curar_indi.py

Curación de la tabla INDI de FAERS.
Contiene las indicaciones terapéuticas para las que se administró
cada fármaco, codificadas en terminología MedDRA.

La indicación es muy relevante para el análisis ya que permite distinguir
entre reacciones adversas al uso aprobado del fármaco y las asociadas a usos
fuera de indicación.

Reglas aplicadas en esta curación:
1. Alineación con DEMO curado por el primaryid
2. Normalización del término MedDRA de indicación.
3. Eliminación de registros sin término de indicación.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim, lower, regexp_replace
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Curación-INDI") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Cargamos INDI desde Delta Lake
indi = spark.read.format("delta").load(f"{CURATED_PATH}/indi")
total_inicial = indi.count()
print(f"\nRegistros iniciales INDI: {total_inicial:,}")

# Cargamos DEMO curado para alinear por primaryid
demo_curado = spark.read.format("delta") \
    .load(f"{CURATED_PATH}/demo_curado")
primaryids_validos = demo_curado.select("primaryid").distinct()

# Regla 1. Alineación con DEMO curado
indi_alineado = indi.join(primaryids_validos, on="primaryid", how="inner")
total_alineado = indi_alineado.count()
print(f"Tras alineación con DEMO curado: {total_alineado:,} "
      f"({total_inicial - total_alineado:,} registros eliminados)")

# Regla 2. Normalización del término MedDRA de indicación
indi_norm = indi_alineado \
    .withColumn("indi_pt_norm",
        trim(lower(
            regexp_replace(col("indi_pt"), r'\s+', ' ')
        ))
    )

# Regla 3. Eliminación de registros sin término de indicación
sin_indi = indi_norm.filter(
    col("indi_pt").isNull() | (trim(col("indi_pt")) == "")
).count()

indi_limpio = indi_norm.filter(
    col("indi_pt_norm").isNotNull() & (col("indi_pt_norm") != "")
)

print(f"\nRegistros sin término de indicación eliminados: {sin_indi:,}")

total_final = indi_limpio.count()
print(f"\nRegistros finales INDI curado: {total_final:,}")
print(f"Reducción total respecto al original: "
      f"{total_inicial - total_final:,} registros")

# Indicaciones únicas tras normalización
indicaciones_unicas = indi_limpio.select("indi_pt_norm").distinct().count()
print(f"\nIndicaciones MedDRA únicas: {indicaciones_unicas:,}")

# Top 20 indicaciones más frecuentes
print("\nTop 20 indicaciones terapéuticas más frecuentes:")
indi_limpio.groupBy("indi_pt_norm").count() \
    .orderBy(col("count").desc()) \
    .show(20, truncate=False)

# Guardamos INDI curado en Delta Lake
ruta_salida = f"{CURATED_PATH}/indi_curado"
indi_limpio.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(ruta_salida)

print(f"\nINDI curado guardado en: {ruta_salida}")
print("\n=== SCHEMA INDI CURADO ===")
indi_limpio.printSchema()

spark.stop()





















