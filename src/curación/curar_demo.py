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
    regexp_replace, expr, row_number
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
# Tras ejecutar la validación de la curación me topo con 144 primaryid duplicados
# Se modifica bloque deduplicación caseversion
# FAERS puede contener varias versiones del mismo reporte (caseid).
# Nos quedamos solo con la versión más reciente de cada caso.
# Si hay un empate en caseversion (el mismo reporte aparece en dos trimestres)
# Desempatamos por primaryid quedándonos con el mayor que corresponde
# a la carga más reciente.
ventana_dedup = Window.partitionBy("caseid").orderBy(
    col("caseversion_int").desc(),
    col("primaryid").cast("long").desc()
)

demo_dedup = demo \
    .withColumn("caseversion_int", col("caseversion").cast("integer")) \
    .withColumn("fila", row_number().over(ventana_dedup)) \
    .filter(col("fila") == 1) \
    .drop("fila", "caseversion_int")

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

# Regla 3. Filtro de edades fuera de rango 0-120 años
con_edad = demo_edad.filter(col("age_years").isNotNull())
edad_valida = demo_edad.filter(
    col("age_years").isNotNull() &
    (col("age_years") >= 0) &
    (col("age_years") <= 120)
)
sin_edad = demo_edad.filter(col("age_years").isNull()).count()
fuera_rango = con_edad.count() - edad_valida.count()

print(f"\nCalidad de edad:")
print(f"  Sin edad informada: {sin_edad:,}")
print(f"  Con edad fuera de rango (0-120): {fuera_rango:,} — marcados como nulos")

# Los registros fuera de rango se mantienen pero con age_years = null
demo_edad_limpia = demo_edad.withColumn(
    "age_years",
    when(
        (col("age_years") >= 0) & (col("age_years") <= 120),
        col("age_years")
    ).otherwise(None)
)

# Regla 4. Normalización de campos de texto
# reporter_country, occr_country y sex se normalizan para evitar variantes.
# Se añade modificación a sex, se mapea a valores estándar M/F para evitar variantes como "MALE", "FEMALE", "1", "2",
# que aparecen en trimestres antiguos de FAERS.
demo_texto = demo_edad_limpia \
    .withColumn("reporter_country", upper(trim(col("reporter_country")))) \
    .withColumn("occr_country",     upper(trim(col("occr_country")))) \
    .withColumn("sex",
        when(upper(trim(col("sex"))).isin("M", "MALE", "1"), "M")
        .when(upper(trim(col("sex"))).isin("F", "FEMALE", "2"), "F")
        .otherwise(None)
    )

# Regla 5. Conversión de fechas
# Los campos de fecha vienen como string tipo "20200110",
# tambien parciales con solo año+mes (200210) o solo año (2008).
# try_to_date devuelve NULL en vez de lanzar error para formatos no válidos.
# En event_dt se eliminan primero los valores duplicados separados por coma.
demo_fechas = demo_texto \
    .withColumn("fda_dt_parsed",
        expr("try_to_date(fda_dt, 'yyyyMMdd')")) \
    .withColumn("event_dt_parsed",
        expr("try_to_date(regexp_replace(event_dt, ',.*', ''), 'yyyyMMdd')"))

total_final = demo_fechas.count()
print(f"\nRegistros finales DEMO curado: {total_final:,}")
print(f"Reducción total respecto al original: "
      f"{total_inicial - total_final:,} registros")

# Guardamos DEMO curado en Delta Lake
ruta_salida = f"{CURATED_PATH}/demo_curado"
demo_fechas.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(ruta_salida)

print(f"\nDEMO curado guardado en: {ruta_salida}")
print("\n=== SCHEMA DEMO CURADO ===")
demo_fechas.printSchema()

spark.stop()
























