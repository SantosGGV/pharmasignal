"""
curar_geografia.py

Curación de la dimensión geográfica de FAERS.

Contexto de hallazgo en los datos:
En la exploración de los datos he identificado una recodificación geográfica
estructural en FAERS concretamente a partir del tercer trimestre de 2025.
Los códigos de país de los estados miembros de la Unión Europea son sustituidos por el
código "EU", eliminando su trazabilidad nacional.

Esta verificación se ha realizado mediante las dos vías de acceso a FAERS:
- Fichero ASCII: el código "ES" desaparece en 2025Q3 y 2025Q4.
- API OpenFDA: la última notificación con occurcountry = "ES" es del 30 de junio de 2025
cerrando así el último día de 2025Q2, mientras que el código "EU" permanece activo en marzo de 2026.

Conclusión: la recodificación claramente afecta a la fuente de datos completa y no es resoluble
mediante vías de acceso alternativas. Constituye una limitación estructural de FAERS, no un problema
de calidad del datos subsanable en la fase de curación.

Se aplican las siguientes reglas:
1. Clasificación del nivel de trazabilidad geográfica de cada reporte:
- NACIONAL: el código de país identifica el estado en concreto.
- SUPRANACIONAL: el código agrupa varios países (EU).
- NO_ESPECIFICADO: sin información geográfica utilizable.

2. Marcado del periodo analizable para el análisis geográfico de España:
2020Q1-2025Q2 (22 trimestres en total). Los trimestres 2025Q3 y 2025Q4 quedan excluidos del análisis nacional por
imposibilidad de la fuente.

3. Generación de las métricas que cuantifican el alcance del hallazgo, destinado a documentar la limitación en la
memoria del proyecto.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, lit
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Curación-Geografía") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Trimestres afectados por la recodificación geográfica
TRIMESTRES_RECODIFICADOS = ["2025q3", "2025q4"]

# Códigos que agrupan varios países y no permiten trazabilidad nacional
CODIGOS_SUPRANACIONALES = ["EU"]

# Códigos sin información geográfica utilizable
CODIGOS_NO_ESPECIFICADOS = ["COUNTRY NOT SPECIFIED", "A1"]

demo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_curado")
total = demo.count()
print(f"\nRegistros DEMO curado: {total:,}")

# Regla 1. Clasificación del nivel de trazabilidad geográfica
demo_geo = demo.withColumn(
    "nivel_geografico",
    when(col("reporter_country").isin(CODIGOS_SUPRANACIONALES),
         "SUPRANACIONAL")
    .when(col("reporter_country").isin(CODIGOS_NO_ESPECIFICADOS),
          "NO_ESPECIFICADO")
    .when(col("reporter_country").isNull(), "NO_ESPECIFICADO")
    .otherwise("NACIONAL")
)

# Regla 2. Marcado del periodo válido para el análisis geográfico nacional
# Los trimestres recodificados quedan exlcuidos del análisis de España.
demo_geo = demo_geo.withColumn(
    "geo_analizable",
    when(col("trimestre").isin(TRIMESTRES_RECODIFICADOS), lit(False))
    .otherwise(lit(True))
)

# Regla 3. Métricas del hallazgo

print("\nDistribución por nivel de trazabilidad geográfica:")
demo_geo.groupBy("nivel_geografico").count() \
    .orderBy(col("count").desc()) \
    .show(truncate=False)

# Reportes afectados por la recodificación
afectados = demo_geo.filter(
    col("trimestre").isin(TRIMESTRES_RECODIFICADOS) &
    (col("reporter_country") == "EU")
).count()

print(f"\nReportes bajo código EU en los trimestres recodificados: "
      f"{afectados:,}")

# Estimación de los reportes españoles perdidos
# Se calcula la media trimestral de reportes ES en los 4 trimestres
# previos a la recodificación y se extrapola a los 2 trimestres perdidos
trimestres_previos = ["2024q3", "2024q4", "2025q1", "2025q2"]
es_previos = demo_geo.filter(
    col("trimestre").isin(trimestres_previos) &
    (col("reporter_country") == "ES")
).count()

media_trimestral_es = es_previos / len(trimestres_previos)
estimacion_perdidos = int(media_trimestral_es * len(TRIMESTRES_RECODIFICADOS))

print(f"\nMedia trimestral de reportes ES (4 trimestres previos): "
      f"{media_trimestral_es:,.0f}")
print(f"Estimación de reportes españoles no trazables en 2025Q3-Q4: "
      f"~{estimacion_perdidos:,}")

# Periodo analizable
analizables = demo_geo.filter(col("geo_analizable") == True).count()
no_analizables = total - analizables

print(f"\nReportes en el periodo geográficamente analizable "
      f"(2020Q1–2025Q2): {analizables:,}")
print(f"Reportes excluidos del análisis geográfico nacional: "
      f"{no_analizables:,}")

# Total de reportes españoles utilizables en el análisis
es_total = demo_geo.filter(
    (col("reporter_country") == "ES") & (col("geo_analizable") == True)
).count()

print(f"\nTotal de reportes de España analizables: {es_total:,}")


# Guardamos DEMO con la dimensión geográfica curada
ruta_salida = f"{CURATED_PATH}/demo_geo"
demo_geo.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(ruta_salida)

print(f"\nDEMO con geografía curada guardado en: {ruta_salida}")
print("\n=== SCHEMA DEMO GEO ===")
demo_geo.printSchema()

spark.stop()














