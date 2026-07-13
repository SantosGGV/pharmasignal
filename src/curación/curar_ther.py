"""
curar_ther.py

Curación de la tabla THER de FAERS.
Contiene la información de la terapia: fechas de inicio y fin del tratamiento, y duración.

Esta información permite calcular el tiempo transcurrido entre el inicio del tratamiento y la aparición
de la reacción adversa, esto es un datos muy relevante para poder valorar la asocicación.

Reglas aplicadas:
1. Alineación con DEMO curado por primaryid
2. Conversión de fecha de inicio y fin a tipo fecha real, tolerando formatos incompletos con try_to_date.
3. Calculo de la duración del tratamiento en días.
4. Filtro de duraciones negativas o absurdas.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, expr, datediff, when
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Curación-THER") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Cargamos THER desde Delta Lake
ther = spark.read.format("delta").load(f"{CURATED_PATH}/ther")
total_inicial = ther.count()
print(f"\nRegistros iniciales THER: {total_inicial:,}")

# Cargamos DEMO curado para alinear por primaryid
demo_curado = spark.read.format("delta") \
    .load(f"{CURATED_PATH}/demo_curado")
primaryids_validos = demo_curado.select("primaryid").distinct()

# Regla 1. Alineación con DEMO curado
ther_alineado = ther.join(primaryids_validos, on="primaryid", how="inner")
total_alineado = ther_alineado.count()
print(f"Tras alineación con DEMO curado: {total_alineado:,} "
      f"({total_inicial - total_alineado:,} registros eliminados)")

# Regla 2. Conversión de las fechas de inicio y de fin
# start_dt y end_dt vienen como string en formato yyyyMMdd
# con posibles formatos incompletos que try_to_date tolera.
ther_fechas = ther_alineado \
    .withColumn("start_dt_parsed",
        expr("try_to_date(start_dt, 'yyyyMMdd')")) \
    .withColumn("end_dt_parsed",
        expr("try_to_date(end_dt, 'yyyyMMdd')"))

# Regla 3. Cálculo de duración del tratamiento en días
ther_duracion = ther_fechas.withColumn(
    "duracion_dias",
    datediff(col("end_dt_parsed"), col("start_dt_parsed"))
)

# Regla 4. Filtro de duraciones inválidas
# Se marcan como null las duraciones negativas, considero como fecha negativa
# aquellas fechas cuya fecha fin sea anterior a la fecha inicio y las superiores a 20 años
# que indican errores de registro.
ther_limpio = ther_duracion.withColumn(
    "duracion_dias",
    when(
        (col("duracion_dias") >= 0) & (col("duracion_dias") <= 7300),
        col("duracion_dias")
    ).otherwise(None)
)

# Métricas de calidad de las fechas
con_inicio = ther_limpio.filter(col("start_dt_parsed").isNotNull()).count()
con_fin = ther_limpio.filter(col("end_dt_parsed").isNotNull()).count()
con_duracion = ther_limpio.filter(col("duracion_dias").isNotNull()).count()

print(f"\nCalidad de fechas de terapia:")
print(f"  Con fecha de inicio válida: {con_inicio:,}")
print(f"  Con fecha de fin válida: {con_fin:,}")
print(f"  Con duración calculable: {con_duracion:,}")

total_final = ther_limpio.count()
print(f"\nRegistros finales THER curado: {total_final:,}")
print(f"Reducción total respecto al original: "
      f"{total_inicial - total_final:,} registros")

# Guardamos THER curado en Delta Lake
ruta_salida = f"{CURATED_PATH}/ther_curado"
ther_limpio.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(ruta_salida)

print(f"\nTHER curado guardado en: {ruta_salida}")
print("\n=== SCHEMA THER CURADO ===")
ther_limpio.printSchema()

spark.stop()


























