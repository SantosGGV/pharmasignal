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

"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, countDistinct, when, lit, sum as spark_sum
from delta import configure_spark_with_delta_pip
import os

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

# Familia GLP-1
# Añadimos tanto los principios activos (semaglutide,
# tirzepatide, liraglutide...) como sus nombres comerciales (ozempic,
# mounjaro, wegovy...). Esto es necesario porque la normalización de
# drugname realizada en la curación NO unifica marca y principio activo.
FAMILIA_GLP1 = [
    "semaglutide", "ozempic", "wegovy", "rybelsus",
    "tirzepatide", "mounjaro", "zepbound",
    "liraglutide", "saxenda", "victoza",
    "dulaglutide", "trulicity", "exenatide",
]

# Familia COVID-19: antivirales específicos y fármacos que se usaron de forma masiva durante la pandemia
FAMILIA_COVID = [
    "paxlovid", "nirmatrelvir", "nirmatrelvir\\ritonavir",
    "remdesivir", "veklury", "molnupiravir", "lagevrio",
    "hydroxychloroquine", "chloroquine",
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
serie_glp1 = drug_trim.filter(col("drugname_norm").isin(FAMILIA_GLP1)) \
    .groupBy("trimestre") \
    .agg(countDistinct("primaryid").alias("reportes_glp1")) \
    .orderBy("trimestre")

serie_glp1.show(24, truncate=False)

# Serie A3. Familia COVID-19 por trimestre
# Misma lógica que para la serie GLP-1 pero en este caso aplicada a los fármacos COVID-19.
# En este caso claramente se espera un patrón distinto habiendo un pico concentrado en el periodo 2020-2022

print("\n")
print("SERIE TEMPORAL - FAMILIA COVID-19")
print("\n")

serie_covid = drug_trim.filter(col("drugname_norm").isin(FAMILIA_COVID)) \
    .groupBy("trimestre") \
    .agg(countDistinct("primaryid").alias("reportes_covid")) \
    .orderBy("trimestre")

serie_covid.show(24, truncate=False)

# Serie A4. Fármacos GLP-1 individuales por trimestre
# Desglosa la familia GLP-1 en sus fármacos concretos, para observar qué
# principios activos o marcas impulsan el crecimiento de la familia y en
# qué momento entra cada uno.

print("\n")
print("SERIE TEMPORAL - FÁRMACOS GLP-1 INDIVIDUALES")
print("\n")

# Aquí agrupamos por trimestre y por fármaco, de modo de que cada fila es la cuenta de un fármaco
# concreto en un trimestre concreto.
serie_por_farmaco = drug_trim.filter(col("drugname_norm").isin(FAMILIA_GLP1)) \
    .groupBy("trimestre", "drugname_norm") \
    .agg(countDistinct("primaryid").alias("reportes")) \
    .orderBy("trimestre", "drugname_norm")

print("\nMuestra (primeros trimestres):")
serie_por_farmaco.show(30, truncate=False)

# Consolidación. Tabla única de series para el frontend
# Unimos las tres series principales (total, GLP-1, COVID-19) en una sola tabla con una columna por serie.
# Así el frontend puede leer una única tabla
print("\n")
print("CONSOLIDANDO SERIES PARA EL FRONTEND")
print("\n")

# left_join sobre la serie total: conservamos todos los trimestre aunque en alguno
# no hubiera reportes de una familia (quedaría como NULL).
series_consolidadas = serie_total \
    .join(serie_glp1, on="trimestre", how="left") \
    .join(serie_covid, on="trimestre", how="left") \
    .fillna(0) \
    .orderBy("trimestre")

# Peso relativo de cada familia sobre el total del trimestre. Expresar la serie en porcentaje, permite
# distringuir un crecimiento de la familia de un simple aumento del volumen global de notificaciones. Por ejemplo,
# digamos que si los GLP-1 crecen en % y no solo en número absoluto, es que ganan peso dentro del sistema.
series_consolidadas = series_consolidadas \
    .withColumn("pct_glp1",
                (col("reportes_glp1") / col("reportes")) * 100) \
    .withColumn("pct_covid",
                (col("reportes_covid") / col("reportes")) * 100)

print("\nSeries consolidadas:")
series_consolidadas.show(24, truncate=False)

# Persistimos las salida en Delta Lake para que el frontend Streamlit las consuma directamente sin recalcular el análisis en cada carga
# - serie_temporal_familias: las tres series juntas + porcentajes.
# - serie_temporal_glp1_farmacos: desglose por fármaco individual.
# mode overwrite permite que el proceso sea reejecutable
series_consolidadas.write.format("delta").mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(f"{CURATED_PATH}/serie_temporal_familias")

serie_por_farmaco.write.format("delta").mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(f"{CURATED_PATH}/serie_temporal_glp1_farmacos")

print("\nSeries temporales guardadas en Delta Lake.")

spark.stop()













