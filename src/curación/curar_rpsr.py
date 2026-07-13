"""
curar_rpsr.py

Curación de la tabla RPSR de FAERS.
Contiene la fuente de la notificación del evento adverso.

Se identifican los siguientes códigos de fuente en FAERS:
- FGN: Foreign (notificación procedente del extranjero)
- SDY: Study (estudio)
- LIT: Literature (literatura científica)
- CSM: Consumer (consumidor/paciente)
- HP: Health Professional (profesional sanitario)
- UF: User Facility (centro sanitario)
- CR: Company Representative (representante de la compañía)
- DT: Distributor (distribuidor)
- OTH: Other (otro)

La fuente de notificación es muy importante concretamente para este proyecto
ya que condiciona la calidad del reporte. Las notificaciones de profesionales sanitarios
suelen tener una mayor calidad que la de los consumidores.

Reglas aplicadas:
1. Alineación con DEMO curado con primaryid
2. Normalización del código de la fuente a mayúsculas
3. Distribución por tipo de fuente.

"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim, upper
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Curación-RPSR") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Cargamos RPSR desde Delta Lake
rpsr = spark.read.format("delta").load(f"{CURATED_PATH}/rpsr")
total_inicial = rpsr.count()
print(f"\nRegistros iniciales RPSR: {total_inicial:,}")

# Cargamos DEMO curado para alinear por primaryid
demo_curado = spark.read.format("delta") \
    .load(f"{CURATED_PATH}/demo_curado")
primaryids_validos = demo_curado.select("primaryid").distinct()

# Regla 1. Alineación con DEMO curado
rpsr_alineado = rpsr.join(primaryids_validos, on="primaryid", how="inner")
total_alineado = rpsr_alineado.count()
print(f"Tras alineación con DEMO curado: {total_alineado:,} "
      f"({total_inicial - total_alineado:,} registros eliminados)")

# Regla 2. Normalización del código de la fuente
rpsr_norm = rpsr_alineado.withColumn(
    "rpsr_cod_norm", upper(trim(col("rpsr_cod")))
)

# Regla 3. Eliminación de registros sin código de la fuente
sin_rpsr = rpsr_norm.filter(
    col("rpsr_cod").isNull() | (trim(col("rpsr_cod")) == "")
).count()

rpsr_limpio = rpsr_norm.filter(
    col("rpsr_cod_norm").isNotNull() & (col("rpsr_cod_norm") != "")
)

print(f"\nRegistros sin código de fuente eliminados: {sin_rpsr:,}")

total_final = rpsr_limpio.count()
print(f"\nRegistros finales RPSR curado: {total_final:,}")
print(f"Reducción total respecto al original: "
      f"{total_inicial - total_final:,} registros")

# Distribución por fuente de notificación
print("\nDistribución por fuente de notificación:")
rpsr_limpio.groupBy("rpsr_cod_norm").count() \
    .orderBy(col("count").desc()) \
    .show(truncate=False)

# Guardamos RPSR curado en Delta Lake
ruta_salida = f"{CURATED_PATH}/rpsr_curado"
rpsr_limpio.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(ruta_salida)

print(f"\nRPSR curado guardado en: {ruta_salida}")
print("\n=== SCHEMA RPSR CURADO ===")
rpsr_limpio.printSchema()

spark.stop()




















