"""
prr_ror.py

Sección de detección estadística de señales de farmacovigilancia mediante
las medidas de desproporción PRR (Proportional Reporting Ratio) y
ROR (Reporting Odds Ratio)

Fundamento de la metodología usada
Ambas medidas se construyen sobre una tabla de contingencia 2x2
que cruza la presencia del fármaco con la presencia de una reacción ante este

            Reacción R          No reacción R
Fármaco D       a                     b
Otros fármacos  c                     d

Donde:
a = reportes que contienen un fármaco D y la reacción R
b = reportes que contienen el fármaco D pero no la reacción R
c = reportes que contienen la reacción R pero no el fármaco D
d = reportes que no contienen ni el fármaco D ni la reacción R

PRR = [a / (a+b)] / [c / (c+d)]
ROR = (a * d) / (b * c)

El PRR compara la proporción de la reacción R entre los reportes
del fármaco D frente a la proporción de esa misma reacción en el resto
de la BBDD. El ROR expresa la misma relación en forma de odds.

Criterio tomado para la señal
Se considera que existe una señal estadística cuando se cumplen de forma simultanea:
- PRR >= 2
- a >= 3
- Chi-cuadrado >= 4

Advertencia metodológica
Una señal estadística es una hipótesis de trabajo, ni mucho menos una confirmación
de causalidad. Los datos de notificación espontánea presentan sesgos conocidos y no
proceden de estudios controlados. Los resultados requieren interpretación por criterio experto.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, countDistinct, lit, sqrt, log, exp, broadcast
)
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-PRR-ROR") \
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

# Umbrales de señal según el criterio marcado por Evans et al. (2001)
UMBRAL_PRR = 2.0
MIN_CASOS = 3
UMBRAL_CHI2 = 4.0

print("\nCargando datos curados...")

drug = spark.read.format("delta").load(f"{CURATED_PATH}/drug_curado")
reac = spark.read.format("delta").load(f"{CURATED_PATH}/reac_curado")

# Trabajamos únicamente con el fármaco sospechoso primario (PS),
# que es el que la notificación señala como causa probable del evento.
# Incluir fármacos concomitantes introduciría ruido en la señal.
drug_ps = drug.filter(col("rol") == "PS") \
    .select("primaryid", "drugname_norm") \
    .distinct()

reac_pt = reac.select("primaryid", "pt_norm").distinct()

print("Construyendo pares fármaco-reacción...")

# Cada par fármaco-reacción representa una combinación observada
# en un reporte concreto. Se eliminan duplicados dentro del mismo
# reporte para no inflar el conteo.
pares = drug_ps.join(reac_pt, on="primaryid", how="inner") \
    .select("primaryid", "drugname_norm", "pt_norm") \
    .distinct()

pares.cache()

# N = número total de reportes en la base analítica
N = pares.select("primaryid").distinct().count()
print(f"\nTotal de reportes en la base analítica: {N:,}")

total_pares = pares.count()
print(f"Total de pares fármaco-reacción únicos: {total_pares:,}")

print("\nCalculando marginales...")

# a = reportes con el fármaco D y la reacción R
conteo_a = pares.groupBy("drugname_norm", "pt_norm") \
    .agg(countDistinct("primaryid").alias("a"))

# n_farmaco = total de reportes que contienen el fármaco D  (= a + b)
n_farmaco = pares.groupBy("drugname_norm") \
    .agg(countDistinct("primaryid").alias("n_farmaco"))

# n_reaccion = total de reportes que contienen la reacción R  (= a + c)
n_reaccion = pares.groupBy("pt_norm") \
    .agg(countDistinct("primaryid").alias("n_reaccion"))

print("Construyendo la tabla de contingencia 2x2...")

# Unimos los marginales al conteo de la celda 'a' y derivamos
# el resto de celdas de la tabla de contingencia.
contingencia = conteo_a \
    .join(broadcast(n_farmaco), on="drugname_norm", how="inner") \
    .join(broadcast(n_reaccion), on="pt_norm", how="inner") \
    .withColumn("b", col("n_farmaco") - col("a")) \
    .withColumn("c", col("n_reaccion") - col("a"))

# Filtramos las combinaciones que no alcanzan el mínimo de casos.
# Con menos de 3 casos la estimación es demasiado inestable
# para considerarse una señal.
contingencia = contingencia.filter(col("a") >= MIN_CASOS)

# Corrección de continuidad
# Las celdas b o c podrían ser cero cuando un fármaco solo se asocia
# a una reacción, o una reacción solo aparece con un fármaco. En esos
# casos el ROR es indefinido. La corrección realizada consiste en sumar 0,5
# a las cuatro celdas, lo que permite estabilizar la estimación sin alterar de
# una forma apreciable los resultados con conteos elevados.
contingencia = contingencia \
    .withColumn("a", col("a").cast("double") + lit(0.5)) \
    .withColumn("b", col("b").cast("double") + lit(0.5)) \
    .withColumn("c", col("c").cast("double") + lit(0.5)) \
    .withColumn("d",
        lit(float(N)) - col("a") - col("b") - col("c") + lit(0.5)
    )

print("Calculando PRR, ROR e intervalos de confianza...")

# PRR = [a / (a+b)] / [c / (c+d)]
senales = contingencia \
    .withColumn("prr",
        (col("a") / (col("a") + col("b"))) /
        (col("c") / (col("c") + col("d")))
    )

# ROR = (a * d) / (b * c)
senales = senales.withColumn("ror",
    (col("a") * col("d")) / (col("b") * col("c"))
)

# Error estándar del logaritmo del ROR:
senales = senales.withColumn("se_ln_ror",
    sqrt(
        (lit(1.0) / col("a")) + (lit(1.0) / col("b")) +
        (lit(1.0) / col("c")) + (lit(1.0) / col("d"))
    )
)

# Intervalo de confianza al 95% del ROR:
senales = senales \
    .withColumn("ror_ic_inf",
        exp(log(col("ror")) - lit(1.96) * col("se_ln_ror"))) \
    .withColumn("ror_ic_sup",
        exp(log(col("ror")) + lit(1.96) * col("se_ln_ror")))

# Chi-cuadrado de la tabla 2x2:
senales = senales.withColumn("chi2",
    (lit(float(N)) *
        ((col("a") * col("d")) - (col("b") * col("c"))) *
        ((col("a") * col("d")) - (col("b") * col("c")))
    ) / (
        (col("a") + col("b")) * (col("c") + col("d")) *
        (col("a") + col("c")) * (col("b") + col("d"))
    )
)

# Criterio de señal:
# PRR >= 2 AND a >= 3 AND chi2 >= 4
# Adicionalmente se marca si el límite inferior del IC95 del ROR supera 1.
senales = senales \
    .withColumn("es_senal",
        (col("prr") >= UMBRAL_PRR) &
        (col("a") >= MIN_CASOS) &
        (col("chi2") >= UMBRAL_CHI2)
    ) \
    .withColumn("ror_significativo", col("ror_ic_inf") > lit(1.0))

senales.cache()

total_combinaciones = senales.count()
total_senales = senales.filter(col("es_senal")).count()
total_ror_sig = senales.filter(col("ror_significativo")).count()
ambos = senales.filter(col("es_senal") & col("ror_significativo")).count()

print("\n")
print("RESULTADOS DE LA DETECCIÓN DE SEÑALES")
print("\n")
print(f"Combinaciones fármaco-reacción evaluadas (a>={MIN_CASOS}): "
      f"{total_combinaciones:,}")
print(f"Señales según criterio PRR (PRR>={UMBRAL_PRR}, chi2>={UMBRAL_CHI2}): "
      f"{total_senales:,}")
print(f"Combinaciones con IC95 inferior del ROR > 1: {total_ror_sig:,}")
print(f"Señales confirmadas por ambos criterios: {ambos:,}")

print("\n")
print("TOP 25 SEÑALES POR PRR (mínimo 50 casos)")
print("\n")

# CORRECCION!
# Filtramos ademas con un farmaco concreto. El filtro actual de estas combinaciones
# producen valores de PRR desproporcionados por construcción.
# CORRECCION!
# Se exige un mínimo de 200 reportes totales del fármaco.
# El PRR compara la proporción de una reacción dentro del fármaco
# frente a la proporción en el resto de la base. Cuando un fármaco
# tiene muy pocos reportes y casi todos corresponden a la misma reacción,
# esa proporción se aproxima a 1 y el PRR se dispara sin que ello implique
# una mayor relevancia.
senales.filter(
        col("es_senal") &
        (col("a") >= 50) &
        (col("c") >= 100) &
        ((col("a") + col("b")) >= 200)
    ) \
    .select(
        "drugname_norm", "pt_norm",
        col("a").cast("int").alias("casos"),
        col("prr").cast("decimal(10,2)").alias("PRR"),
        col("ror").cast("decimal(10,2)").alias("ROR"),
        col("ror_ic_inf").cast("decimal(10,2)").alias("IC95_inf"),
        col("ror_ic_sup").cast("decimal(10,2)").alias("IC95_sup"),
        col("chi2").cast("decimal(12,1)").alias("Chi2")
    ) \
    .orderBy(col("PRR").desc()) \
    .show(25, truncate=False)

print("\n")
print("SEÑALES GLP-1 (semaglutide, ozempic, wegovy, mounjaro)")
print("\n")

GLP1 = ["semaglutide", "ozempic", "wegovy", "mounjaro",
        "tirzepatide", "saxenda", "liraglutide", "rybelsus"]

senales.filter(
        col("drugname_norm").isin(GLP1) &
        col("es_senal") &
        (col("a") >= 20)
    ) \
    .select(
        "drugname_norm", "pt_norm",
        col("a").cast("int").alias("casos"),
        col("prr").cast("decimal(10,2)").alias("PRR"),
        col("ror").cast("decimal(10,2)").alias("ROR")
    ) \
    .orderBy(col("PRR").desc()) \
    .show(25, truncate=False)

# Guardamos el ranking completo de señales en Delta Lake
ruta_salida = f"{CURATED_PATH}/senales_prr_ror"
senales.select(
        "drugname_norm", "pt_norm",
        "a", "b", "c", "d",
        "prr", "ror", "ror_ic_inf", "ror_ic_sup", "chi2",
        "es_senal", "ror_significativo"
    ) \
    .write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(ruta_salida)

print(f"\nRanking de señales guardado en: {ruta_salida}")

spark.stop()


