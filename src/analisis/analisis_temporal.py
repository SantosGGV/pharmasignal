"""
analisis_temporal.py

Fichero en el que se construyen las series temporales de notificación de FAERS.

En este apartado se agrega el número de notificaciones por trimestre para los fármacos de mayor
interés del periodo estudiado. Las series resultantes nutrirán la vista del frontend y constituyen
la base sobre la que, en una fase posterior, se aplicarán la detección de anomalías.

Eje de este análisis:
Eje A: se trata la evolución del volumen de notificaciones por fármaco a lo largo de los 24 trimestres que planteamos en el proyecto.

Fármacos analizados:
Principalmente trataremos dos grupos de especial relevancia que marcan la tendencia del periodo 2020-2025, esto son:
- GLP-1: fármacos para diabetes y obesidad cuyo uso creció de forma exponencial en este periodo (Ozempic, Wegovy, etc.)
- COVID-19: antivirales y tratamientos asociados a la pandemos.
  Los fármacos COVID se tratan en dos series separadas, ver el comentario de la serie A3.
- Respiratorias: antivirales de gripe y monoclonales frente al VRS, que sirven de
  contrapunto a las series COVID. Ver el comentario de la serie A3b.

"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, countDistinct, when, lit, sum as spark_sum
from delta import configure_spark_with_delta_pip
import os

# Las listas de fármacos viven ahora en familias.py, que es la fuente única para
# todos los módulos de análisis. Antes estaban duplicadas aquí y en
# analisis_geografico.py, con el riesgo de tocar una y olvidar la otra, y de que
# las cifras geográficas y temporales dejaran de ser comparables entre sí.
from familias import (GLP1, COVID_ANTIVIRAL, COVID_REPURPOSED,
                      GRIPE_ANTIVIRAL, VSR_MONOCLONAL)

# Construcción de la sesión Spark con soporte Delta Lake
# local[*] usa todos los núcleos del equipo sin necesidad de cluster externo.
# driver.memory 16g este módulo agrega las tablas curadas por lo que se requiere de un driver holgado.
# shuffle.partitions 200 el groupBy por trimestre provoca un shuffle, por lo que 200 particiones es un valor equilibrado para este volumen.
# Las dos últimas configuraciones activan la extensión de Delta Lake en Spark SQL
builder = SparkSession.builder \
    .appName("PharmaSignal-Análisis-Temporal") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.shuffle.partitions", "200") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

# configure_spark_with_delta_pip descarga y registra los JAR de Delta Lake
# solamente la primera vez que se ejecuta, posteriormente quedan cacheados.
spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

# Ruta donde residen las tablas curadas en formato Delta Lake.
CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Se trata del órden cronológico de los 24 trimestres. Aunque el nombre de trimestre por defecto
# ya ordena bien alfabéticamente, se mantiene esta lista como referencia.
ORDEN_TRIMESTRES = [
    "2020q1", "2020q2", "2020q3", "2020q4",
    "2021q1", "2021q2", "2021q3", "2021q4",
    "2022q1", "2022q2", "2022q3", "2022q4",
    "2023q1", "2023q2", "2023q3", "2023q4",
    "2024q1", "2024q2", "2024q3", "2024q4",
    "2025q1", "2025q2", "2025q3", "2025q4",
]

print("\nCargando datos curados...")

# DEMO curado aporta la relación reporte -> trimestre
# DRUG curado aporta la relación reporte -> fármaco.
demo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_curado")
drug = spark.read.format("delta").load(f"{CURATED_PATH}/drug_curado")

# Nos quedamos solo con el fármaco sospechoso primario, ya que es el fármaco que la
# notificación señala como causa probable del evento.
drug_ps = drug.filter(col("rol") == "PS") \
    .select("primaryid", "drugname_norm").distinct()

# Proyección reporte -> trimestre.
demo_trim = demo.select("primaryid", "trimestre").distinct()

# Unimos fármaco y trimestre por primaryid.
drug_trim = drug_ps.join(demo_trim, on="primaryid", how="inner")

# Serie A1. Volumen total de notificaciones por trimestre
# Esta es la serie de referencia que comprueba cuantos reportes unicos hay en cada trimestre.
# Sirve para calcular el peso relativo de cada familia de fármacos y como línea para detectar anomalías globales

print("\n")
print("SERIE TEMPORAL - VOLUMEN TOTAL POR TRIMESTRE")
print("\n")

# countDistinct sobre primaryid nos garantiza que cada reporte cuenta una sola
# vez aunque tuviera varias filas. Y, ordenamos por trimestre para que la
# serie salga cronológicamente.
serie_total = demo.groupBy("trimestre") \
    .agg(countDistinct("primaryid").alias("reportes")) \
    .orderBy("trimestre")

serie_total.show(24, truncate=False)

# Serie A2. Familia GLP-1 por trimestre
# Cuenta los reportes cuyo fármaco sospechoso primario pertenece a la familia GLP-1,
# trimestre a trimestre.
print("\n")
print("SERIE TEMPORAL - FAMILIA GLP-1")
print("\n")

# isin filtra los reportes cuyo fármaco está en la lista GLP-1
# countDistinct evita contar dos veces un reporte que tuviera, por ejemplo,
# Ozempic y Wegovy a la vez
serie_glp1 = drug_trim.filter(col("drugname_norm").isin(GLP1)) \
    .groupBy("trimestre") \
    .agg(countDistinct("primaryid").alias("reportes_glp1")) \
    .orderBy("trimestre")

serie_glp1.show(24, truncate=False)

# Serie A3. COVID-19 por trimestre

print("\n")
print("SERIE TEMPORAL - COVID-19 (A) ANTIVIRALES")
print("\n")

serie_covid_antiviral = drug_trim.filter(col("drugname_norm").isin(COVID_ANTIVIRAL)) \
    .groupBy("trimestre") \
    .agg(countDistinct("primaryid").alias("reportes_covid_antiviral")) \
    .orderBy("trimestre")

serie_covid_antiviral.show(24, truncate=False)

print("\n")
print("SERIE TEMPORAL - COVID-19 (B) FÁRMACOS REUTILIZADOS EN LA PANDEMIA")
print("\n")

serie_covid_repurposed = drug_trim.filter(col("drugname_norm").isin(COVID_REPURPOSED)) \
    .groupBy("trimestre") \
    .agg(countDistinct("primaryid").alias("reportes_covid_repurposed")) \
    .orderBy("trimestre")

serie_covid_repurposed.show(24, truncate=False)

# Serie A3b. Familia respiratoria, gripe y VRS
# La incorporo para tener un contrapunto a las series COVID. La de gripe es
# especialmente interesante porque durante 2020 y 2021 la circulación del virus
# de la gripe cayó a mínimos históricos por las medidas contra la pandemia, así
# que se espera un hundimiento de la serie justo cuando las de COVID despegan.
# La de VRS mezcla un producto antiguo (palivizumab, autorizado en 1998) con uno
# que aparece a mitad del periodo analizado (nirsevimab, autorizado en 2023), de
# modo que la aparición desde cero es en sí misma una anomalía con fecha externa
# verificable, útil para validar el detector.

print("\n")
print("SERIE TEMPORAL - GRIPE (ANTIVIRALES ESPECÍFICOS)")
print("\n")

serie_gripe = drug_trim.filter(col("drugname_norm").isin(GRIPE_ANTIVIRAL)) \
    .groupBy("trimestre") \
    .agg(countDistinct("primaryid").alias("reportes_gripe")) \
    .orderBy("trimestre")

serie_gripe.show(24, truncate=False)

print("\n")
print("SERIE TEMPORAL - VRS (ANTICUERPOS MONOCLONALES)")
print("\n")

serie_vsr = drug_trim.filter(col("drugname_norm").isin(VSR_MONOCLONAL)) \
    .groupBy("trimestre") \
    .agg(countDistinct("primaryid").alias("reportes_vsr")) \
    .orderBy("trimestre")

serie_vsr.show(24, truncate=False)

# Serie A4. Fármacos GLP-1 individuales por trimestre
# Desglosa la familia GLP-1 en sus fármacos concretos, para observar qué
# principios activos o marcas impulsan el crecimiento de la familia y en
# qué momento entra cada uno.

print("\n")
print("SERIE TEMPORAL - FÁRMACOS GLP-1 INDIVIDUALES")
print("\n")

# Aquí agrupamos por trimestre y por fármaco, de modo de que cada fila es la cuenta de un fármaco
# concreto en un trimestre concreto.
serie_por_farmaco = drug_trim.filter(col("drugname_norm").isin(GLP1)) \
    .groupBy("trimestre", "drugname_norm") \
    .agg(countDistinct("primaryid").alias("reportes")) \
    .orderBy("trimestre", "drugname_norm")

print("\nMuestra (primeros trimestres):")
serie_por_farmaco.show(30, truncate=False)

# Consolidación. Tabla única de series para el frontend
# Unimos las seis series (total, GLP-1, COVID antivirales, COVID reutilizados, gripe y VRS) en una sola tabla con una columna por serie.
# Así el frontend puede leer una única tabla
print("\n")
print("CONSOLIDANDO SERIES PARA EL FRONTEND")
print("\n")

# left_join sobre la serie total: conservamos todos los trimestre aunque en alguno
# no hubiera reportes de una familia (quedaría como NULL).
series_consolidadas = serie_total \
    .join(serie_glp1, on="trimestre", how="left") \
    .join(serie_covid_antiviral, on="trimestre", how="left") \
    .join(serie_covid_repurposed, on="trimestre", how="left") \
    .join(serie_gripe, on="trimestre", how="left") \
    .join(serie_vsr, on="trimestre", how="left") \
    .fillna(0) \
    .orderBy("trimestre")

# Peso relativo de cada familia sobre el total del trimestre. Expresar la serie en porcentaje, permite
# distringuir un crecimiento de la familia de un simple aumento del volumen global de notificaciones. Por ejemplo,
# digamos que si los GLP-1 crecen en % y no solo en número absoluto, es que ganan peso dentro del sistema.
series_consolidadas = series_consolidadas \
    .withColumn("pct_glp1",
                (col("reportes_glp1") / col("reportes")) * 100) \
    .withColumn("pct_covid_antiviral",
                (col("reportes_covid_antiviral") / col("reportes")) * 100) \
    .withColumn("pct_covid_repurposed",
                (col("reportes_covid_repurposed") / col("reportes")) * 100) \
    .withColumn("pct_gripe",
                (col("reportes_gripe") / col("reportes")) * 100) \
    .withColumn("pct_vsr",
                (col("reportes_vsr") / col("reportes")) * 100)

print("\nSeries consolidadas:")
series_consolidadas.show(24, truncate=False)

# Totales del periodo. Los saco por pantalla para poder cuadrarlos contra la línea
# base guardada antes del recálculo (data/BASELINE_S1_2026-07-29.json) y construir
# con ellos la tabla de regresión de la memoria.
print("\n")
print("TOTALES DEL PERIODO (para la tabla de regresión)")
print("\n")
series_consolidadas.agg(
    spark_sum("reportes_glp1").alias("total_glp1"),
    spark_sum("reportes_covid_antiviral").alias("total_covid_antiviral"),
    spark_sum("reportes_covid_repurposed").alias("total_covid_repurposed"),
    spark_sum("reportes_gripe").alias("total_gripe"),
    spark_sum("reportes_vsr").alias("total_vsr"),
).show(truncate=False)

print("Fármacos GLP-1 distintos con al menos un reporte:")
serie_por_farmaco.select("drugname_norm").distinct().orderBy("drugname_norm") \
    .show(30, truncate=False)

# Persistimos las salida en Delta Lake para que el frontend Streamlit las consuma directamente sin recalcular el análisis en cada carga
# - serie_temporal_familias: las seis series juntas + porcentajes.
# - serie_temporal_glp1_farmacos: desglose por fármaco individual.
# mode overwrite permite que el proceso sea reejecutable
# overwriteSchema es imprescindible en esta ejecución porque el esquema cambia:
# se añaden las cuatro columnas nuevas de las series de gripe y VRS.
series_consolidadas.write.format("delta").mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(f"{CURATED_PATH}/serie_temporal_familias")

serie_por_farmaco.write.format("delta").mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(f"{CURATED_PATH}/serie_temporal_glp1_farmacos")

print("\nSeries temporales guardadas en Delta Lake.")

spark.stop()