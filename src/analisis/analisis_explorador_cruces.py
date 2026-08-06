"""
analisis_explorador_cruces.py

Segunda pasada de agregaciones para el explorador interactivo.

La primera pasada (analisis_explorador.py) materializa cruces de una entidad
contra una dimensión: un fármaco por trimestre, una reacción por país. Con esas
tablas el constructor resuelve las consultas de volumen, pero no las que
combinan dos entidades, los efectos adversos de un fármaco desglosados por
trimestre, o los fármacos asociados a una reacción desglosados por país. Ese es el cruce aporta valor al explorador.

El cruce fármaco × reacción es la operación cara del pipeline, son decenas de
millones de filas y se necesita cuatro veces. Por eso se materializa una única
vez como tabla intermedia en disco y las agregaciones posteriores la releen, en
lugar de dejar que Spark reconstruya el join cada vez.

Acotación aplicada:
  - Solo entidades que superan los umbrales de la primera pasada
  - Los N pares más frecuentes de cada entidad, no todos los pares posibles
  - Solo países con volumen suficiente para que un porcentaje sea interpretable

Tablas generadas:
  expl_farmaco_reaccion_trimestre-efectos adversos de X por trimestre
  expl_farmaco_reaccion_pais-efectos adversos de X por país
  expl_reaccion_farmaco_trimestre-fármacos asociados a Y por trimestre
  expl_reaccion_farmaco_pais-fármacos asociados a Y por país
  expl_farmaco_indicacion_trimestre-indicaciones de X por trimestre
  expl_farmaco_gravedad_trimestre-desenlaces de X por trimestre
"""

from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    col, countDistinct, count, lit, broadcast, row_number,
    round as spark_round
)
from delta import configure_spark_with_delta_pip
import os
import shutil

builder = SparkSession.builder \
    .appName("PharmaSignal-ExploradorCruces") \
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

# Umbrales de entidad. Idénticos a los de la primera pasada, si una entidad no
# entra en los catálogos del explorador, tampoco debe aparecer en los cruces.
MIN_REPORTES_FARMACO = 5000
MIN_CASOS_REACCION = 1000

# Acotación de los pares. Sin este límite el cruce fármaco × reacción produce
# millones de combinaciones
TOP_REACCIONES_POR_FARMACO = 15
TOP_FARMACOS_POR_REACCION = 15
TOP_INDICACIONES_POR_FARMACO = 10

# Umbral de volumen por país. Se emplea un umbral y no un ranking de los N
# primeros
MIN_REPORTES_PAIS = 10000

# Indicación sin contenido informativo, excluida igual que en la primera pasada.
INDICACION_DESCONOCIDA = "product used for unknown indication"

# Tabla intermedia del cruce fármaco × reacción. No forma parte de la capa
# curada, se escribe para evitar recomputar el join y se elimina al terminar.
RUTA_CRUCE = f"{CURATED_PATH}/_tmp_expl_cruce"

print("\nCargando datos curados...")

demo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_curado")
demo_geo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_geo")
drug = spark.read.format("delta").load(f"{CURATED_PATH}/drug_curado")
reac = spark.read.format("delta").load(f"{CURATED_PATH}/reac_curado")
outc = spark.read.format("delta").load(f"{CURATED_PATH}/outc_curado")
indi = spark.read.format("delta").load(f"{CURATED_PATH}/indi_curado")

# Mismas finalidad que en la primera pasada, para que las cifras de las dos
# familias de tablas sean consistentes entre sí.
drug_ps = drug.filter(col("rol") == "PS") \
    .select("primaryid", "drugname_norm").distinct().cache()

reac_pt = reac.select("primaryid", "pt_norm").distinct().cache()

demo_trim = demo.select("primaryid", "trimestre").distinct().cache()

demo_pais = demo_geo.filter(
    (col("geo_analizable") == True) &
    (col("nivel_geografico") == "NACIONAL")
).select("primaryid", "reporter_country").distinct().cache()

print("\nConstruyendo catálogos de entidades...")

farmacos = drug_ps.groupBy("drugname_norm") \
    .agg(countDistinct("primaryid").alias("reportes")) \
    .filter(col("reportes") >= MIN_REPORTES_FARMACO) \
    .select("drugname_norm").cache()

reacciones = reac_pt.groupBy("pt_norm") \
    .agg(countDistinct("primaryid").alias("casos")) \
    .filter(col("casos") >= MIN_CASOS_REACCION) \
    .select("pt_norm").cache()

n_farmacos = farmacos.count()
n_reacciones = reacciones.count()
print(f"Fármacos con al menos {MIN_REPORTES_FARMACO:,} notificaciones: {n_farmacos:,}")
print(f"Reacciones con al menos {MIN_CASOS_REACCION:,} casos: {n_reacciones:,}")

# Países que superan el umbral de volumen
total_pais = demo_pais.groupBy("reporter_country") \
    .agg(countDistinct("primaryid").alias("total_pais"))

paises = total_pais.filter(col("total_pais") >= MIN_REPORTES_PAIS).cache()

n_paises = paises.count()
print(f"Países con al menos {MIN_REPORTES_PAIS:,} notificaciones: {n_paises:,}")

# Comprobación explícita de que España queda dentro. Es el país
# sobre el que se articulan ciertas conclusiones del trabajo
if paises.filter(col("reporter_country") == "ES").count() == 0:
    raise RuntimeError(
        f"España queda fuera del umbral de {MIN_REPORTES_PAIS:,} notificaciones. "
        "Revisar el umbral antes de continuar."
    )
print("España incluida en la acotación por país: sí")

salidas = {}


def top_por(df, particion, columna_orden, n):
    """Conserva las n filas de mayor valor dentro de cada partición.

    Se emplea para quedarse con los pares más frecuentes
    """
    ventana = Window.partitionBy(particion).orderBy(
        col(columna_orden).desc(), col(df.columns[1]).asc()
    )
    return df.withColumn("_rk", row_number().over(ventana)) \
             .filter(col("_rk") <= n) \
             .drop("_rk")


# Cruce fármaco × reacción
# Es la operación más costosa del script. Se materializa en disco con las dos
# dimensiones ya incorporadas, el trimestre por unión interna, porque toda
# notificación lo tiene, y el país por unión externa por la izquierda, porque
# solo lo tienen las notificaciones geográficamente analizables. Las filas sin
# país se conservan para que las agregaciones temporales no pierdan volumen.
print("\n")
print("CRUCE INTERMEDIO — FÁRMACO × REACCIÓN")
print("\n")

cruce = drug_ps \
    .join(broadcast(farmacos), on="drugname_norm", how="inner") \
    .join(reac_pt, on="primaryid", how="inner") \
    .join(broadcast(reacciones), on="pt_norm", how="inner") \
    .join(demo_trim, on="primaryid", how="inner") \
    .join(demo_pais, on="primaryid", how="left") \
    .select("primaryid", "drugname_norm", "pt_norm", "trimestre", "reporter_country")

cruce.write.format("delta").mode("overwrite") \
    .option("overwriteSchema", "true").save(RUTA_CRUCE)

cruce = spark.read.format("delta").load(RUTA_CRUCE)
print(f"Filas del cruce: {cruce.count():,}")

# Recuento global de cada par.
pares = cruce.groupBy("drugname_norm", "pt_norm") \
    .agg(count(lit(1)).alias("casos_total"))

pares.cache()
print(f"Pares fármaco-reacción distintos: {pares.count():,}")

pares_por_farmaco = top_por(
    pares, "drugname_norm", "casos_total", TOP_REACCIONES_POR_FARMACO
).select("drugname_norm", "pt_norm").cache()

pares_por_reaccion = top_por(
    pares.select("pt_norm", "drugname_norm", "casos_total"),
    "pt_norm", "casos_total", TOP_FARMACOS_POR_REACCION
).select("drugname_norm", "pt_norm").cache()

print(f"Pares conservados por fármaco: {pares_por_farmaco.count():,}")
print(f"Pares conservados por reacción: {pares_por_reaccion.count():,}")

# Agregación 7. Efectos adversos de un fármaco por trimestre
# Responde a cómo evoluciona el perfil de reacciones notificadas de un fármaco.
# Junto al recuento se calcula el peso de la reacción sobre el total de casos
# del fármaco en ese trimestre
print("\n")
print("AGREGACIÓN 7 — EFECTOS ADVERSOS DE UN FÁRMACO POR TRIMESTRE")
print("\n")

total_farmaco_trim = cruce.groupBy("drugname_norm", "trimestre") \
    .agg(countDistinct("primaryid").alias("total_farmaco_trim"))

farmaco_reaccion_trimestre = cruce \
    .join(broadcast(pares_por_farmaco), on=["drugname_norm", "pt_norm"], how="inner") \
    .groupBy("drugname_norm", "pt_norm", "trimestre") \
    .agg(count(lit(1)).alias("casos")) \
    .join(total_farmaco_trim, on=["drugname_norm", "trimestre"], how="inner") \
    .withColumn("pct_farmaco_trim",
                spark_round((col("casos") / col("total_farmaco_trim")) * 100, 2)) \
    .orderBy("drugname_norm", "trimestre", col("casos").desc())

salidas["expl_farmaco_reaccion_trimestre"] = farmaco_reaccion_trimestre
print(f"Filas generadas: {farmaco_reaccion_trimestre.count():,}")
farmaco_reaccion_trimestre.show(5, truncate=False)

# Agregación 8. Efectos adversos de un fármaco por país
# El porcentaje se calcula sobre el total de notificaciones del país, no sobre
# el total del fármaco
print("\n")
print("AGREGACIÓN 8 — EFECTOS ADVERSOS DE UN FÁRMACO POR PAÍS")
print("\n")

farmaco_reaccion_pais = cruce \
    .filter(col("reporter_country").isNotNull()) \
    .join(broadcast(pares_por_farmaco), on=["drugname_norm", "pt_norm"], how="inner") \
    .join(broadcast(paises), on="reporter_country", how="inner") \
    .groupBy("drugname_norm", "pt_norm", "reporter_country", "total_pais") \
    .agg(count(lit(1)).alias("casos")) \
    .withColumn("pct_pais",
                spark_round((col("casos") / col("total_pais")) * 100, 4)) \
    .orderBy("drugname_norm", "pt_norm", col("casos").desc())

salidas["expl_farmaco_reaccion_pais"] = farmaco_reaccion_pais
print(f"Filas generadas: {farmaco_reaccion_pais.count():,}")
farmaco_reaccion_pais.show(5, truncate=False)

# Agregación 9. Fármacos asociados a una reacción por trimestre
# Es la consulta inversa a la 7 y la que permite preguntar qué fármacos están
# detrás de un efecto adverso concreto y cómo cambia esa composición.
print("\n")
print("AGREGACIÓN 9 — FÁRMACOS ASOCIADOS A UNA REACCIÓN POR TRIMESTRE")
print("\n")

total_reaccion_trim = cruce.groupBy("pt_norm", "trimestre") \
    .agg(countDistinct("primaryid").alias("total_reaccion_trim"))

reaccion_farmaco_trimestre = cruce \
    .join(broadcast(pares_por_reaccion), on=["drugname_norm", "pt_norm"], how="inner") \
    .groupBy("pt_norm", "drugname_norm", "trimestre") \
    .agg(count(lit(1)).alias("casos")) \
    .join(total_reaccion_trim, on=["pt_norm", "trimestre"], how="inner") \
    .withColumn("pct_reaccion_trim",
                spark_round((col("casos") / col("total_reaccion_trim")) * 100, 2)) \
    .orderBy("pt_norm", "trimestre", col("casos").desc())

salidas["expl_reaccion_farmaco_trimestre"] = reaccion_farmaco_trimestre
print(f"Filas generadas: {reaccion_farmaco_trimestre.count():,}")
reaccion_farmaco_trimestre.show(5, truncate=False)

# Agregación 10. Fármacos asociados a una reacción por país
# Sostiene la lectura geográfica del explorador: qué fármacos concentran un
# efecto adverso determinado y si esa composición difiere entre países.
print("\n")
print("AGREGACIÓN 10 — FÁRMACOS ASOCIADOS A UNA REACCIÓN POR PAÍS")
print("\n")

reaccion_farmaco_pais = cruce \
    .filter(col("reporter_country").isNotNull()) \
    .join(broadcast(pares_por_reaccion), on=["drugname_norm", "pt_norm"], how="inner") \
    .join(broadcast(paises), on="reporter_country", how="inner") \
    .groupBy("pt_norm", "drugname_norm", "reporter_country", "total_pais") \
    .agg(count(lit(1)).alias("casos")) \
    .withColumn("pct_pais",
                spark_round((col("casos") / col("total_pais")) * 100, 4)) \
    .orderBy("pt_norm", "drugname_norm", col("casos").desc())

salidas["expl_reaccion_farmaco_pais"] = reaccion_farmaco_pais
print(f"Filas generadas: {reaccion_farmaco_pais.count():,}")
reaccion_farmaco_pais.show(5, truncate=False)

# Agregación 11. Indicaciones de un fármaco por trimestre
# Es la consulta que hace visible un cambio en el uso de un fármaco a lo largo
# del tiempo.
print("\n")
print("AGREGACIÓN 11 — INDICACIONES DE UN FÁRMACO POR TRIMESTRE")
print("\n")

indi_pt = indi.filter(col("indi_pt_norm") != lit(INDICACION_DESCONOCIDA)) \
    .select("primaryid", "indi_pt_norm").distinct()

farmaco_indi = drug_ps \
    .join(broadcast(farmacos), on="drugname_norm", how="inner") \
    .join(indi_pt, on="primaryid", how="inner") \
    .join(demo_trim, on="primaryid", how="inner") \
    .select("primaryid", "drugname_norm", "indi_pt_norm", "trimestre").cache()

pares_indi = farmaco_indi.groupBy("drugname_norm", "indi_pt_norm") \
    .agg(countDistinct("primaryid").alias("reportes_total"))

top_indi = top_por(
    pares_indi, "drugname_norm", "reportes_total", TOP_INDICACIONES_POR_FARMACO
).select("drugname_norm", "indi_pt_norm")

total_indi_trim = farmaco_indi.groupBy("drugname_norm", "trimestre") \
    .agg(countDistinct("primaryid").alias("total_farmaco_trim"))

farmaco_indicacion_trimestre = farmaco_indi \
    .join(broadcast(top_indi), on=["drugname_norm", "indi_pt_norm"], how="inner") \
    .groupBy("drugname_norm", "indi_pt_norm", "trimestre") \
    .agg(countDistinct("primaryid").alias("reportes")) \
    .join(total_indi_trim, on=["drugname_norm", "trimestre"], how="inner") \
    .withColumn("pct_farmaco_trim",
                spark_round((col("reportes") / col("total_farmaco_trim")) * 100, 2)) \
    .orderBy("drugname_norm", "trimestre", col("reportes").desc())

salidas["expl_farmaco_indicacion_trimestre"] = farmaco_indicacion_trimestre
print(f"Filas generadas: {farmaco_indicacion_trimestre.count():,}")
farmaco_indicacion_trimestre.show(5, truncate=False)

# Agregación 12. Desenlaces de un fármaco por trimestre
# Completa la agregación 4 de la primera pasada con la dimensión temporal. Los
# porcentajes de esta tabla suman más de cien, una misma notificación puede
# registrar varios desenlaces simultáneos, por ejemplo hospitalización y
# amenaza vital. El frontend debe advertirlo junto a la representación.
print("\n")
print("AGREGACIÓN 12 — DESENLACES DE UN FÁRMACO POR TRIMESTRE")
print("\n")

outc_norm = outc.select("primaryid", "outc_cod_norm").distinct()

farmaco_base_trim = drug_ps \
    .join(broadcast(farmacos), on="drugname_norm", how="inner") \
    .join(demo_trim, on="primaryid", how="inner") \
    .select("primaryid", "drugname_norm", "trimestre").cache()

total_base_trim = farmaco_base_trim.groupBy("drugname_norm", "trimestre") \
    .agg(countDistinct("primaryid").alias("total_farmaco_trim"))

farmaco_gravedad_trimestre = farmaco_base_trim \
    .join(outc_norm, on="primaryid", how="inner") \
    .groupBy("drugname_norm", "outc_cod_norm", "trimestre") \
    .agg(countDistinct("primaryid").alias("reportes")) \
    .join(total_base_trim, on=["drugname_norm", "trimestre"], how="inner") \
    .withColumn("pct_farmaco_trim",
                spark_round((col("reportes") / col("total_farmaco_trim")) * 100, 2)) \
    .orderBy("drugname_norm", "trimestre", col("reportes").desc())

salidas["expl_farmaco_gravedad_trimestre"] = farmaco_gravedad_trimestre
print(f"Filas generadas: {farmaco_gravedad_trimestre.count():,}")
farmaco_gravedad_trimestre.show(5, truncate=False)

# Persistencia
print("\n")
print("GUARDANDO RESULTADOS EN DELTA LAKE")
print("\n")

for nombre, df in salidas.items():
    ruta = f"{CURATED_PATH}/{nombre}"
    df.write.format("delta").mode("overwrite") \
        .option("overwriteSchema", "true").save(ruta)
    print(f"  {nombre}")

print("\nEliminando tabla intermedia...")
shutil.rmtree(RUTA_CRUCE, ignore_errors=True)

print("\nAgregaciones de cruces del explorador completadas.")

spark.stop()