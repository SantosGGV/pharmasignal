"""
analisis_explorador.py

Agregaciones de apoyo para el explorador interactivo del frontend.

El constructor de gráficas permite al usuario introducir un fármaco o una
reacción y elegir qué quiere ver sobre ellos. Esas consultas no pueden
resolverse al vuelo sobre las tablas curadas, que suman decenas de millones de
filas, de modo que aquí se materializan las agregaciones necesarias.

Cada tabla resultante es pequeña porque se agrega y se filtra por umbrales de
volumen. El criterio es el mismo que rige el resto del proyecto, por debajo de
cierto número de notificaciones las series y las distribuciones geográficas
dejan de ser interpretables.

Umbrales aplicados:
  - Fármacos: 5.000 notificaciones
  - Reacciones: 1.000 casos
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, countDistinct, lit, avg, when, broadcast,
    round as spark_round, sum as spark_sum, coalesce
)
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Explorador") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.shuffle.partitions", "200") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Umbrales de volumen. Se definen como constantes para que la decisión quede
# explícita y sea fácil de ajustar.
MIN_REPORTES_FARMACO = 5000
MIN_CASOS_REACCION = 1000

# La indicación "product used for unknown indication" representa el 38 % de los
# registros de la tabla INDI. No aporta información y desplazaría a todas las
# demás en cualquier ranking, así que se excluye de las agregaciones. Se informa
# en el frontend de esta exclusión.
INDICACION_DESCONOCIDA = "product used for unknown indication"

print("\nCargando datos curados...")

demo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_curado")
demo_geo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_geo")
drug = spark.read.format("delta").load(f"{CURATED_PATH}/drug_curado")
reac = spark.read.format("delta").load(f"{CURATED_PATH}/reac_curado")
outc = spark.read.format("delta").load(f"{CURATED_PATH}/outc_curado")
indi = spark.read.format("delta").load(f"{CURATED_PATH}/indi_curado")

# Solo el fármaco sospechoso primario, igual que en el resto de análisis, es el
# que la notificación señala como causa probable del evento.
drug_ps = drug.filter(col("rol") == "PS") \
    .select("primaryid", "drugname_norm").distinct().cache()

reac_pt = reac.select("primaryid", "pt_norm").distinct().cache()

demo_trim = demo.select("primaryid", "trimestre").distinct().cache()

# Para la dimensión geográfica se emplea demo_geo, que ya incorpora la
# clasificación de trazabilidad se excluye los trimestres afectados por la
# recodificación de país y los reportes sin país identificable.
demo_pais = demo_geo.filter(
    (col("geo_analizable") == True) &
    (col("nivel_geografico") == "NACIONAL")
).select("primaryid", "reporter_country").distinct().cache()

# Catálogos de entidades que superan el umbral. Se calculan una vez y se
# reutilizan como filtro en todas las agregaciones posteriores.
print("\nConstruyendo catálogos de entidades...")

farmacos_vol = drug_ps.groupBy("drugname_norm") \
    .agg(countDistinct("primaryid").alias("reportes"))

farmacos = farmacos_vol.filter(col("reportes") >= MIN_REPORTES_FARMACO) \
    .select("drugname_norm").cache()

reacciones_vol = reac_pt.groupBy("pt_norm") \
    .agg(countDistinct("primaryid").alias("casos"))

reacciones = reacciones_vol.filter(col("casos") >= MIN_CASOS_REACCION) \
    .select("pt_norm").cache()

n_farmacos = farmacos.count()
n_reacciones = reacciones.count()
print(f"Fármacos con al menos {MIN_REPORTES_FARMACO:,} notificaciones: {n_farmacos:,}")
print(f"Reacciones con al menos {MIN_CASOS_REACCION:,} casos: {n_reacciones:,}")

salidas = {}

# Catálogos. El frontend los usa para sugerir términos mientras el usuario
# escribe y para advertir cuando la entidad buscada no alcanza el umbral.
salidas["expl_catalogo_farmacos"] = farmacos_vol.orderBy(col("reportes").desc())
salidas["expl_catalogo_reacciones"] = reacciones_vol.orderBy(col("casos").desc())

# Agregación 1. Fármaco por trimestre
# Permite responder a "cómo evoluciona la notificación de este fármaco".
print("\n")
print("AGREGACIÓN 1 — FÁRMACO POR TRIMESTRE")
print("\n")

farmaco_trimestre = drug_ps \
    .join(broadcast(farmacos), on="drugname_norm", how="inner") \
    .join(demo_trim, on="primaryid", how="inner") \
    .groupBy("drugname_norm", "trimestre") \
    .agg(countDistinct("primaryid").alias("reportes")) \
    .orderBy("drugname_norm", "trimestre")

salidas["expl_farmaco_trimestre"] = farmaco_trimestre
print(f"Filas generadas: {farmaco_trimestre.count():,}")
farmaco_trimestre.show(5, truncate=False)

# Agregación 2. Fármaco por país
# Además del recuento se calcula el peso del fármaco sobre el total de
# notificaciones de cada país. Es la medida que interesa ya que el volumen absoluto
# está dominado por Estados Unidos, que aporta en torno al 70 % del total, de
# modo que un ranking por número de reportes reproduce siempre el mismo orden.
# El peso relativo, en cambio, indica dónde tiene ese fármaco una presencia
# mayor de la que le correspondería.
print("\n")
print("AGREGACIÓN 2 — FÁRMACO POR PAÍS")
print("\n")

total_pais = demo_pais.groupBy("reporter_country") \
    .agg(countDistinct("primaryid").alias("total_pais"))

farmaco_pais = drug_ps \
    .join(broadcast(farmacos), on="drugname_norm", how="inner") \
    .join(demo_pais, on="primaryid", how="inner") \
    .groupBy("drugname_norm", "reporter_country") \
    .agg(countDistinct("primaryid").alias("reportes")) \
    .join(broadcast(total_pais), on="reporter_country", how="inner") \
    .withColumn("pct_pais",
                spark_round((col("reportes") / col("total_pais")) * 100, 4)) \
    .orderBy("drugname_norm", col("reportes").desc())

salidas["expl_farmaco_pais"] = farmaco_pais
print(f"Filas generadas: {farmaco_pais.count():,}")
farmaco_pais.show(5, truncate=False)

# Agregación 3. Fármaco por indicación
# Responde a "para qué se receta este fármaco según los notificadores".
print("\n")
print("AGREGACIÓN 3 — FÁRMACO POR INDICACIÓN")
print("\n")

indi_pt = indi.filter(col("indi_pt_norm") != lit(INDICACION_DESCONOCIDA)) \
    .select("primaryid", "indi_pt_norm").distinct()

farmaco_indicacion = drug_ps \
    .join(broadcast(farmacos), on="drugname_norm", how="inner") \
    .join(indi_pt, on="primaryid", how="inner") \
    .groupBy("drugname_norm", "indi_pt_norm") \
    .agg(countDistinct("primaryid").alias("reportes")) \
    .filter(col("reportes") >= 10) \
    .orderBy("drugname_norm", col("reportes").desc())

salidas["expl_farmaco_indicacion"] = farmaco_indicacion
print(f"Filas generadas: {farmaco_indicacion.count():,}")
farmaco_indicacion.show(5, truncate=False)

# Agregación 4. Fármaco por gravedad del desenlace
# Se calcula tanto el recuento como el porcentaje sobre el total de reportes del
# fármaco, que es lo que permite comparar entre fármacos de volumen distinto.
print("\n")
print("AGREGACIÓN 4 — FÁRMACO POR GRAVEDAD")
print("\n")

outc_norm = outc.select("primaryid", "outc_cod_norm").distinct()

total_farmaco = drug_ps.join(broadcast(farmacos), on="drugname_norm", how="inner") \
    .groupBy("drugname_norm") \
    .agg(countDistinct("primaryid").alias("total_farmaco"))

farmaco_gravedad = drug_ps \
    .join(broadcast(farmacos), on="drugname_norm", how="inner") \
    .join(outc_norm, on="primaryid", how="inner") \
    .groupBy("drugname_norm", "outc_cod_norm") \
    .agg(countDistinct("primaryid").alias("reportes")) \
    .join(broadcast(total_farmaco), on="drugname_norm", how="inner") \
    .withColumn("pct_farmaco",
                spark_round((col("reportes") / col("total_farmaco")) * 100, 2)) \
    .orderBy("drugname_norm", col("reportes").desc())

salidas["expl_farmaco_gravedad"] = farmaco_gravedad
print(f"Filas generadas: {farmaco_gravedad.count():,}")
farmaco_gravedad.show(5, truncate=False)

# Agregación 5. Reacción por trimestre
print("\n")
print("AGREGACIÓN 5 — REACCIÓN POR TRIMESTRE")
print("\n")

reaccion_trimestre = reac_pt \
    .join(broadcast(reacciones), on="pt_norm", how="inner") \
    .join(demo_trim, on="primaryid", how="inner") \
    .groupBy("pt_norm", "trimestre") \
    .agg(countDistinct("primaryid").alias("casos")) \
    .orderBy("pt_norm", "trimestre")

salidas["expl_reaccion_trimestre"] = reaccion_trimestre
print(f"Filas generadas: {reaccion_trimestre.count():,}")
reaccion_trimestre.show(5, truncate=False)

# Agregación 6. Reacción por país
# Mismo criterio que en la agregación 2: junto al recuento se calcula el peso
# sobre el total de notificaciones del país.
print("\n")
print("AGREGACIÓN 6 — REACCIÓN POR PAÍS")
print("\n")

reaccion_pais = reac_pt \
    .join(broadcast(reacciones), on="pt_norm", how="inner") \
    .join(demo_pais, on="primaryid", how="inner") \
    .groupBy("pt_norm", "reporter_country") \
    .agg(countDistinct("primaryid").alias("casos")) \
    .join(broadcast(total_pais), on="reporter_country", how="inner") \
    .withColumn("pct_pais",
                spark_round((col("casos") / col("total_pais")) * 100, 4)) \
    .orderBy("pt_norm", col("casos").desc())

salidas["expl_reaccion_pais"] = reaccion_pais
print(f"Filas generadas: {reaccion_pais.count():,}")
reaccion_pais.show(5, truncate=False)

# Persistencia
# mode overwrite hace el proceso reejecutable y overwriteSchema admite cambios
# de esquema entre ejecuciones, igual que en el resto del pipeline.
print("\n")
print("GUARDANDO RESULTADOS EN DELTA LAKE")
print("\n")

for nombre, df in salidas.items():
    ruta = f"{CURATED_PATH}/{nombre}"
    df.write.format("delta").mode("overwrite") \
        .option("overwriteSchema", "true").save(ruta)
    print(f"  {nombre}")

print("\nAgregaciones del explorador completadas.")

spark.stop()