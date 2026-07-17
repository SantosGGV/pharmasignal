"""
analisis_geografico.py

Fichero dedicado a la explotación de la dimensión geográfica de FAERS.

Como bien sabemos el perfil de notificación de eventos adversos varía de forma significativa
entre países. Esta variabilidad rara vvez se analiza de forma comparada, pese a que puede revelar
señales relevantes a nivel local entre países que quedan diluidas en el patrón global.

Análisis realizados:
1. Perfil de notificación por país: volumen, demografía, gravedad y propensión a notificar desenlaces mortales.

2. Divergencia España frente al patrón global: fármacos y reacciones cuya frecuencia de notificación difiere
entre el patrón local español y el patrón global.

3. PRR restringido a España, contrastado con el PRR global, para identificar señales cuya intensidad es diferencial
en el patrón local español. Aquí distinguimos 3 categorías: señales exclusivas de España, señales amplificadas y señales atenuadas.

4. Comparativa por nivel de renta según la clasificación del Banco Mundial, se evalua si la gravedad notificada y el perfil
demográfico difieren entre países de renta alta y media.

5. Análisis de los fármacos GLP-1 por país, dado su papel central en el periodo actual.

6. Evolución temporal del peso relativo de España en el total de notificaciones a lo largo de los trimestres que se analizan (2020-2025)

7. Concentración geográfica de la notificación, como medida de la dependencia del sistema FAERS respecto a un número reducido de países
notificadores.

Fundamento del análisis de divergencia
Para cada fármaco o reacción se calcula el ratio entre su frecuencia relativa en España y su frecuencia relativa en el conjunto global:
ratio = (casos_ES / N_ES) / (casos_global / N_global)

Un ratio seuperior a 1 indica sobrerrepresentación en España respecto a lo esperado en el conjunto global, un ratio inferior a 1 se trataría
de infrarrepresentación. El ratio se acompaña de un intervalo de confianza al 95% construido sobre el error estándar, de modo que solo se consideran
divergencias estadísticamente sostenibles aquellas cuyo intervalo no incluye el valor 1.

Alvance temporal
El análisis geográfico nacional se restringe al periodo de 2020Q1-2025Q2. A partir de 2025Q3 FAERS sustituye los códigos de país
estados miembros de la unión europea por el código agregado "EU", eliminando la trazabilidad nacional. La limitación afecta a la fuente
completa como ya vimos en la curación y no es subsanable en la fase de curación.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, countDistinct, lit, avg, when, broadcast, sqrt, log, exp,
    round as spark_round, sum as spark_sum, coalesce
)
from delta import configure_spark_with_delta_pip
import os

# Construcción de la sesión Spark mediante soporte de Delta Lake.
# local[*] usa todos los núcleos disponibles en el equipo desde el que se ejecuta
# sin necesitar un cluster externo.
# shuffle.partitions se fija en 200 porque los joins de este análisis mueven grandes
# volúmenes entre particiones y el valor por defecto se queda corto (fue probado y se ajustó)

builder = SparkSession.builder \
    .appName("PharmaSignal-Análisis-Geográfico") \
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

# Umbrales del análisis. Se definen como constantes para que las decisiones
# queden explícitas y sean fáciles de ajustar y justificar.
MIN_CASOS_ES = 5          # mínimo de casos en España para evaluar una señal
MIN_CASOS_GLOBAL = 20     # mínimo de casos globales para comparar
MIN_CASOS_DIVERGENCIA = 30    # mínimo en España para el análisis de divergencia
MIN_GLOBAL_DIVERGENCIA = 150  # mínimo global para el análisis de divergencia

# Clasificación de países por nivel de renta según el Banco Mundial.
# Se emplea para el Análisis 4 en el que se compara por nivel de desarrollo.
# Solo se incluye los códigos ISO de país con presencial relevante en FAERS.
# El resto de países se clasifican en la categoría "NO_CLASIFICADO"
RENTA_ALTA = [
    "US", "CA", "GB", "JP", "FR", "DE", "IT", "ES", "AU", "NL",
    "SE", "CH", "BE", "AT", "DK", "NO", "FI", "IE", "PT", "GR",
    "KR", "IL", "NZ", "SG", "CZ", "PL", "HU", "SK", "SI", "EE",
    "HR", "LT", "LV", "CY", "MT", "LU", "IS", "AE", "SA", "QA",
]

RENTA_MEDIA = [
    "CN", "BR", "IN", "MX", "RU", "TR", "AR", "TH", "ZA", "CO",
    "MY", "ID", "PH", "VN", "EG", "PE", "CL", "RO", "BG", "UA",
    "MA", "DZ", "TN", "JO", "LB", "EC", "DO", "GT", "PY", "BO",
]

# Fármacos de la familia GLP-1. Eje clave en el periodo analizado.
# Se incluyen tanto los principios activos como podrían ser (semaglutide, tirzepatide...)
# como sus nombres comerciales (ozempic, mounjaro, etc) porque tras la normalización de
# drugname ambos coexisten en los datos y hay que capturar todas las formas.
GLP1 = [
    "semaglutide", "ozempic", "wegovy", "rybelsus",
    "tirzepatide", "mounjaro", "zepbound",
    "liraglutide", "saxenda", "victoza",
    "dulaglutide", "trulicity", "exenatide",
]

print("\nCargando datos curados...")

# Carga de las cuatro tablas curadas necesarias para el análisis geográfico.
# demo_geo incluye ya la clasificación de trazabilidad geográfica generada por el módulo
# curar_geografia.py
demo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_geo")
drug = spark.read.format("delta").load(f"{CURATED_PATH}/drug_curado")
reac = spark.read.format("delta").load(f"{CURATED_PATH}/reac_curado")
outc = spark.read.format("delta").load(f"{CURATED_PATH}/outc_curado")

# Restringimos el análisis al periodo con trazabilidad geográfica nacional,
# como vimos en la etapa de curación de los datos disponemos del código por país de la UE
# en el periodo desde 2020Q1-2025Q2. A partir de este periodo perdemos trazabilidad de este código
# y se agrupan todos los países con el código "EU"
# por lo que hay una recodificación ES→EU y junto conlos reportes sin país identificable.
# Se aplican dos filtros simultáneos:
# geo_analizable == True -> significa que se excluyen los trimestres 2025Q3-Q4 afectados por este cambio de codificación.
# nivel_geografico NACIONAL -> excluye los reportes con código EU y los países sin identificable.
# El resultado se cachea porque se reutiliza en los siete análisis posteriores. Cachear evita recalcular el filtro
# cada vez que un análisis lo consume.
demo_geo = demo.filter(
    (col("geo_analizable") == True) &
    (col("nivel_geografico") == "NACIONAL")
).cache()

total_analizable = demo_geo.count()
print(f"Reportes con trazabilidad geográfica nacional: {total_analizable:,}")

# Construcción de los indicadores de gravedad por reporte.
# OUTC contiene un registro por cada desenlace de cada reporte. Para cada tipo de desenlace
# relevante extraemos la lista primaryid distintos que lo presentan y le añadimos una columna indicadora
# con valor 1. Estas tablas se cruzarán después contra DEMO mediante left join.
# DE = Death
# HO = Hospitalization
# LT = Life-Threatening
muertes = outc.filter(col("outc_cod_norm") == "DE") \
    .select("primaryid").distinct() \
    .withColumn("es_muerte", lit(1))

hospitalizaciones = outc.filter(col("outc_cod_norm") == "HO") \
    .select("primaryid").distinct() \
    .withColumn("es_hospitalizacion", lit(1))

riesgo_vital = outc.filter(col("outc_cod_norm") == "LT") \
    .select("primaryid").distinct() \
    .withColumn("es_riesgo_vital", lit(1))

# Enriquecemos DEMO con los indicadores de gravedad
# Se usa left join para conservar TODOS los reportes de demo_geo, tengan o no desenlace grave
# registrado. Los reportes sin desenlace grave queda con NULL en las columnas indicadoras, que posteriormente
# coalesce convierte a 0. De este modo cada reporte tiene siempre un valor 0/1 en cada indicador y las sumas posteriores
# son correctas.
demo_gravedad = demo_geo \
    .join(muertes, on="primaryid", how="left") \
    .join(hospitalizaciones, on="primaryid", how="left") \
    .join(riesgo_vital, on="primaryid", how="left") \
    .withColumn("es_muerte", coalesce(col("es_muerte"), lit(0))) \
    .withColumn("es_hospitalizacion",
                coalesce(col("es_hospitalizacion"), lit(0))) \
    .withColumn("es_riesgo_vital",
                coalesce(col("es_riesgo_vital"), lit(0))) \
    .cache()

# Preparamos las dos tablas base que se reutilizan en varios análisis:
# drug_ps -> pares (reporte, fármaco) quedándonos solo con el fármaco sospechoso primario. Se
# usa distinct para que un mismo fármaco no cuente varias veces dentro del mismo reporte.
# reac_pt -> pares (reporte, reacción) con el término MedDRA normalizado. Ambas se cachean
# por el mismo motivo.
drug_ps = drug.filter(col("rol") == "PS") \
    .select("primaryid", "drugname_norm").distinct().cache()

reac_pt = reac.select("primaryid", "pt_norm").distinct().cache()

# Análisis 1. Perfil de notificación por país
# Objetivo: caracterizar cada país notificador según el volúmen, demografía y gravedad de los reportes.
# La proporción de desenlaces mortales sobre el total de reportes de un país es un indicador indirecto
# de su cultura de notificación.
print("\n" + "=" * 78)
print("ANÁLISIS 1 — PERFIL DE NOTIFICACIÓN POR PAÍS")
print("=" * 78)

# Agregación por país. Para cada país calculamos:
# - reportes: número de reportes únicos.
# - edad_media: media de la edad ya normalizada a años en la curación.
# - pct_mujeres: porcentaje de mujeres sobre los reportes con sexo conocido.
# La expresión asigna 1.0 a F y 0.0 a M, dejando NULL el resto, de modo que la media
# equivale a la proporción de mujeres entre los reportes con sexo informado.
# - muertes / hospitalización / riesgo_vital: suma de los indicadores 0/1.
perfil_pais = demo_gravedad.groupBy("reporter_country").agg(
    countDistinct("primaryid").alias("reportes"),
    spark_round(avg("age_years"), 1).alias("edad_media"),
    spark_round(
        avg(when(col("sex") == "F", 1.0)
            .when(col("sex") == "M", 0.0)) * 100, 1
    ).alias("pct_mujeres"),
    spark_sum("es_muerte").alias("muertes"),
    spark_sum("es_hospitalizacion").alias("hospitalizaciones"),
    spark_sum("es_riesgo_vital").alias("riesgo_vital"),
)

# Derivamos porcentajes de gravedad sobre el total de reportes de cada país.
# pct_grave agrega los tres tipos de desenlace grave. Un mismo reporte puede tener varios desenlaces,
# por lo que pct_grave no es la suma exacta de reportes graves distintos sino un índice de intensidad de gravedad.
perfil_pais = perfil_pais \
    .withColumn("pct_muertes",
        spark_round((col("muertes") / col("reportes")) * 100, 2)) \
    .withColumn("pct_hospitalizacion",
        spark_round((col("hospitalizaciones") / col("reportes")) * 100, 2)) \
    .withColumn("pct_grave",
        spark_round(
            ((col("muertes") + col("hospitalizaciones")
              + col("riesgo_vital")) / col("reportes")) * 100, 2)) \
    .cache()

# Ranking por volumen. Se filtran los países con al menos 1.000 reportes para
# evitar que aquellos con pocos reportes distorsionen la vista.
print("\nTop 20 países por volumen de notificación:")
perfil_pais.filter(col("reportes") >= 1000) \
    .orderBy(col("reportes").desc()) \
    .select("reporter_country", "reportes", "edad_media", "pct_mujeres",
            "muertes", "pct_muertes", "pct_hospitalizacion", "pct_grave") \
    .show(20, truncate=False)

# La proporción de desenlaces mortales entre los reportes de un país es un indicador
# indirecto de su forma de reportar. Los sitemas que solo notifican los casos más graves
# presentan porcentajes elevados, mientras que los sistemas con notificación sistemática
# presentan porcentajes bajos. Se exige un mínimo de 5.000 reportes para que el porcentaje
# sea estadísticamente estable.
print("\nPaíses con mayor proporción de desenlaces mortales "
      "(mínimo 5.000 reportes):")
perfil_pais.filter(col("reportes") >= 5000) \
    .orderBy(col("pct_muertes").desc()) \
    .select("reporter_country", "reportes", "muertes", "pct_muertes",
            "pct_grave") \
    .show(15, truncate=False)

print("\nPaíses con menor proporción de desenlaces mortales "
      "(mínimo 5.000 reportes):")
perfil_pais.filter(col("reportes") >= 5000) \
    .orderBy(col("pct_muertes").asc()) \
    .select("reporter_country", "reportes", "muertes", "pct_muertes",
            "pct_grave") \
    .show(15, truncate=False)

# Analisis 2. Divergencia España vs Patrón Global
# Objetivo: identificar que fármacos y que reacciones se notifican en España con una
# frecuencia relativa distinta a la esperada según el patrón mundial.
# Parte diferencial del proyecto.
print("\n" + "=" * 78)
print("ANÁLISIS 2 — DIVERGENCIA DE ESPAÑA FRENTE AL PATRÓN GLOBAL")
print("=" * 78)

# Subconjunto de reportes españoles y conjunto global. Ambos se cachean
# porque se usan repetidamente en las funciones de divergencia
# y posteriormente en el análisis 3
ids_es = demo_geo.filter(col("reporter_country") == "ES") \
    .select("primaryid").distinct().cache()
n_es = ids_es.count()

ids_global = demo_geo.select("primaryid").distinct().cache()
n_global = ids_global.count()

print(f"\nReportes de España: {n_es:,}")
print(f"Reportes globales (periodo analizable): {n_global:,}")
print(f"Peso relativo de España: {(n_es / n_global) * 100:.2f}%")


def calcular_divergencia(tabla, columna, min_es, min_global):
    """
    Calcula el ratio de frecuencias relativas entre España y el conjunto global
    para cada valor de la columna indicada (fármaco / reacción), junto con su intervalo
    de confianza.

    Metodología empleada:
    1. Se cuentan los reportes españoles y globales que contienen cada valor.
    2. Convertimos a frecuencias relativas dividiendo por el tamaño de cada poblicación
    (n_es y n_global).
    3. El ratio = frec_es / frec_global mide cuantas veces más o menos se notifica
    ese valor en España respecto a lo esperado a nivel mundial.
    4. El error estándar del logaritmo del ratio se aproxima como
    SE(ln ratio) = sqrt(1/casos_es + 1/casos_global)
    5. El intervalo de confianza se obtiene exponenciando
    ln(ratio) +- 1.96 * SE
    6. Una divergencia la consideramos estadísticamente sostenible cuando el intervalo
    no incluye el valor 1, es decir, que IC es inferior a 1 para sobrerrepresentación o
    que IC es superior a 1 para infrarrepresentación.

    Los umbrales min_es y min_global descartan los valores con muy pocos casos.
    """
    # Conteo de reportes españoles que contienen cada valor
    en_es = tabla.join(ids_es, on="primaryid", how="inner") \
        .groupBy(columna) \
        .agg(countDistinct("primaryid").alias("casos_es"))
    # Conteo de reportes globales que contienen cada valor
    en_global = tabla.join(ids_global, on="primaryid", how="inner") \
        .groupBy(columna) \
        .agg(countDistinct("primaryid").alias("casos_global"))
    # Unimos ambos conteos y aplicamos los umbrales mínimos de casos
    div = en_es.join(en_global, on=columna, how="inner") \
        .filter((col("casos_es") >= min_es) &
                (col("casos_global") >= min_global)) \
        .withColumn("frec_es", col("casos_es") / lit(float(n_es))) \
        .withColumn("frec_global",
                    col("casos_global") / lit(float(n_global))) \
        .withColumn("ratio", col("frec_es") / col("frec_global")) \
        .withColumn("se_ln_ratio",
            sqrt((lit(1.0) / col("casos_es")) +
                 (lit(1.0) / col("casos_global")))) \
        .withColumn("ic_inf",
            exp(log(col("ratio")) - lit(1.96) * col("se_ln_ratio"))) \
        .withColumn("ic_sup",
            exp(log(col("ratio")) + lit(1.96) * col("se_ln_ratio"))) \
        .withColumn("significativo",
            (col("ic_inf") > lit(1.0)) | (col("ic_sup") < lit(1.0)))

    return div

# Divergencia de fármacos. Se cachea porque se muestra en dos ordenaciones distintas
# (sobrerrepresentados e infrarrepresentados) y así no se recalcula.
divergencia_farmacos = calcular_divergencia(
    drug_ps, "drugname_norm",
    MIN_CASOS_DIVERGENCIA, MIN_GLOBAL_DIVERGENCIA
).cache()

# Fármacos que se notifican en España más de lo esperado según el patrón global
print("\nFármacos SOBRERREPRESENTADOS en España "
      "(se notifican más de lo esperado):")
divergencia_farmacos.filter(col("significativo")) \
    .orderBy(col("ratio").desc()) \
    .select("drugname_norm", "casos_es", "casos_global",
            spark_round(col("ratio"), 2).alias("ratio"),
            spark_round(col("ic_inf"), 2).alias("IC95_inf"),
            spark_round(col("ic_sup"), 2).alias("IC95_sup")) \
    .show(20, truncate=False)

# Fármacos que se notifican en España menos de lo esperado según el patrón global
print("\nFármacos INFRARREPRESENTADOS en España "
      "(se notifican menos de lo esperado):")
divergencia_farmacos.filter(col("significativo")) \
    .orderBy(col("ratio").asc()) \
    .select("drugname_norm", "casos_es", "casos_global",
            spark_round(col("ratio"), 3).alias("ratio"),
            spark_round(col("ic_inf"), 3).alias("IC95_inf"),
            spark_round(col("ic_sup"), 3).alias("IC95_sup")) \
    .show(20, truncate=False)

# Divergencia de reacciones. Se exige un mínimo global mayor porque las reacciones
# son mucho más frecuentes que los fármacos concretos y sin ese umbral el ranking
# se llenaría de inconsistencias.
divergencia_reacciones = calcular_divergencia(
    reac_pt, "pt_norm",
    MIN_CASOS_DIVERGENCIA, MIN_GLOBAL_DIVERGENCIA * 3
).cache()

print("\nReacciones SOBRERREPRESENTADAS en España:")
divergencia_reacciones.filter(col("significativo")) \
    .orderBy(col("ratio").desc()) \
    .select("pt_norm", "casos_es", "casos_global",
            spark_round(col("ratio"), 2).alias("ratio"),
            spark_round(col("ic_inf"), 2).alias("IC95_inf"),
            spark_round(col("ic_sup"), 2).alias("IC95_sup")) \
    .show(20, truncate=False)

print("\nReacciones INFRARREPRESENTADAS en España:")
divergencia_reacciones.filter(col("significativo")) \
    .orderBy(col("ratio").asc()) \
    .select("pt_norm", "casos_es", "casos_global",
            spark_round(col("ratio"), 3).alias("ratio"),
            spark_round(col("ic_inf"), 3).alias("IC95_inf"),
            spark_round(col("ic_sup"), 3).alias("IC95_sup")) \
    .show(20, truncate=False)

# Análisis 3. Señales PRR restringidos en España
# Objetivo: aplicar la misma metodología de detección de señales PRR pero usando
# únicamente los reportes españoles, y contrastar el resultado con el PRR global
# calculado en prr_ror.py. Este es el núcle de la parte geográfica, demostrar que existen
# señales que solo emergen al desagregar por país.
print("\n" + "=" * 78)
print("ANÁLISIS 3 — SEÑALES PRR EN ESPAÑA FRENTE AL PRR GLOBAL")
print("=" * 78)

# Construimos los pares fármaco-reacción del subconjunto español
# Un par representa la coincidencia de un fármaco sospechoso primario y una
# reacción en un mismo reporte. distinct en este caso elimina repeticiones dentro
# del mismo reporte para no inflar el conteo de la celda 'a'.
pares_es = drug_ps.join(ids_es, on="primaryid", how="inner") \
    .join(reac_pt, on="primaryid", how="inner") \
    .select("primaryid", "drugname_norm", "pt_norm").distinct()

# Celda 'a' de la tabla de contingencia: reportes españoles que contienen simultáneamente el fármaco y la reacción
conteo_a_es = pares_es.groupBy("drugname_norm", "pt_norm") \
    .agg(countDistinct("primaryid").alias("a"))

# Marginal del fármaco: reportes españoles que contienen el fármaco, independientemente de la reacción
# Equivale a a + b.
n_farmaco_es = pares_es.groupBy("drugname_norm") \
    .agg(countDistinct("primaryid").alias("n_farmaco"))

# Marginal de la reacción: reportes españoles que contienen la reacción independientemente del fármaco en este caso
# Equivale a a + c
n_reaccion_es = pares_es.groupBy("pt_norm") \
    .agg(countDistinct("primaryid").alias("n_reaccion"))

# Reconstrucción de la tabla de contingencia 2x2 y cálculo del PRR local.
# Se replica exactamente la misma metodología que aplicamos en prr_ror.py, es decir:
#   b = n_farmaco - a  (fármaco sin la reacción)
#   c = n_reaccion - a (reacción sin el fármaco)
#   d = N - a - b - c  (ni fármaco ni reacción)
# broadcast se usa en los marginales porque son tablas pequeñas en comparación al contero de pares,
# evita un shuffle costoso al replicarlas en memoria.

prr_es = conteo_a_es \
    .join(broadcast(n_farmaco_es), on="drugname_norm", how="inner") \
    .join(broadcast(n_reaccion_es), on="pt_norm", how="inner") \
    .withColumn("b", col("n_farmaco") - col("a")) \
    .withColumn("c", col("n_reaccion") - col("a")) \
    .filter(col("a") >= MIN_CASOS_ES) \
    .withColumn("a", col("a").cast("double") + lit(0.5)) \
    .withColumn("b", col("b").cast("double") + lit(0.5)) \
    .withColumn("c", col("c").cast("double") + lit(0.5)) \
    .withColumn("d",
        lit(float(n_es)) - col("a") - col("b") - col("c") + lit(0.5)) \
    .withColumn("prr_es",
        (col("a") / (col("a") + col("b"))) /
        (col("c") / (col("c") + col("d")))) \
    .withColumn("chi2_es",
        (lit(float(n_es)) *
         ((col("a") * col("d")) - (col("b") * col("c"))) *
         ((col("a") * col("d")) - (col("b") * col("c")))) /
        ((col("a") + col("b")) * (col("c") + col("d")) *
         (col("a") + col("c")) * (col("b") + col("d")))) \
    .withColumn("es_senal_es",
        (col("prr_es") >= lit(2.0)) & (col("chi2_es") >= lit(4.0))) \
    .select("drugname_norm", "pt_norm",
            col("a").cast("int").alias("casos_es"),
            "prr_es", "chi2_es", "es_senal_es") \
    .cache()

n_senales_es = prr_es.filter(col("es_senal_es")).count()
print(f"\nSeñales detectadas en el subconjunto español: {n_senales_es:,}")

# Cargamos el PRR global ya calculado por prr_ror.py para poder cruzarlo.
prr_global = spark.read.format("delta") \
    .load(f"{CURATED_PATH}/senales_prr_ror") \
    .select("drugname_norm", "pt_norm",
            col("a").cast("int").alias("casos_global"),
            col("prr").alias("prr_global"),
            col("es_senal").alias("es_senal_global"))

# Cruce España vs global mediante left join sobre prr_es. Conservamos todas las señales
# españolas, incluidas las que no existen a nivel global, que quedarían con NULL en las columnas
# globales. Coalesce convierte esos NULL en valores neutros ( 0 / False) para poder clasificar sin errores.
# ratio_prr mide cuantas veces mas intensa es la señasl en España que a nivel global
comparativa = prr_es.join(
        prr_global, on=["drugname_norm", "pt_norm"], how="left"
    ) \
    .withColumn("prr_global", coalesce(col("prr_global"), lit(0.0))) \
    .withColumn("casos_global", coalesce(col("casos_global"), lit(0))) \
    .withColumn("es_senal_global",
                coalesce(col("es_senal_global"), lit(False))) \
    .withColumn("ratio_prr",
        when(col("prr_global") > 0,
             col("prr_es") / col("prr_global")).otherwise(None)) \
    .cache()

# Categoría A — señales exclusivas solamente de España
# Son señal en el subconjunto español pero no son señal en el conjunto global.
# Constituye el argumento central del enfoque geográfico, el análisis mundial
# las diluye y solo aparecen al desagregar por país.
exclusivas_es = comparativa.filter(
    col("es_senal_es") & (~col("es_senal_global"))
)
n_exclusivas = exclusivas_es.count()

print(f"\nSeñales EXCLUSIVAS de España "
      f"(detectadas localmente pero no en el agregado global): "
      f"{n_exclusivas:,}")

print("\nTop 25 señales exclusivas de España:")
exclusivas_es.orderBy(col("prr_es").desc()) \
    .select("drugname_norm", "pt_norm", "casos_es", "casos_global",
            spark_round(col("prr_es"), 2).alias("PRR_ES"),
            spark_round(col("prr_global"), 2).alias("PRR_global"),
            spark_round(col("chi2_es"), 1).alias("Chi2_ES")) \
    .show(25, truncate=False)

# Categoría B — Señaes amplificadas en España.
# Presentes en ambos ámbitos, pero con intensidad PRR marcadamente superior
# en España. ratio_prr > 1 indica amplificación local. Se exige un mínimo de casos globales
# para que la comparación sea fiable.
print("\nSeñales AMPLIFICADAS en España "
      "(presentes en ambos ámbitos, mayor intensidad local):")
comparativa.filter(
        col("es_senal_es") & col("es_senal_global") &
        (col("casos_global") >= MIN_CASOS_GLOBAL) &
        (col("ratio_prr") > lit(1.0))
    ) \
    .orderBy(col("ratio_prr").desc()) \
    .select("drugname_norm", "pt_norm", "casos_es", "casos_global",
            spark_round(col("prr_es"), 2).alias("PRR_ES"),
            spark_round(col("prr_global"), 2).alias("PRR_global"),
            spark_round(col("ratio_prr"), 2).alias("ratio")) \
    .show(25, truncate=False)

# Categoría C — Señales atenuadas en España
# La señal existe a nivel global pero en España se reproduce con menor intensidad.
# Puede reflejar diferencias de práctica clínica, de patrones de prescripción o de cultura
# de notificación.
print("\nSeñales ATENUADAS en España "
      "(señal global con menor intensidad local):")
comparativa.filter(
        col("es_senal_global") &
        (col("casos_global") >= MIN_CASOS_GLOBAL * 5) &
        (col("ratio_prr") < lit(1.0)) &
        (col("ratio_prr").isNotNull())
    ) \
    .orderBy(col("ratio_prr").asc()) \
    .select("drugname_norm", "pt_norm", "casos_es", "casos_global",
            spark_round(col("prr_es"), 2).alias("PRR_ES"),
            spark_round(col("prr_global"), 2).alias("PRR_global"),
            spark_round(col("ratio_prr"), 3).alias("ratio")) \
    .show(25, truncate=False)

# Análisis 4. Comparativa por nivel de renta
# Objetivo: evaluar si el perfil de notificación (gravedad, demografía y tipo de reaccciones)
# difiere entre países de renta alta y media, usando la clasificación del Banco Mundial que hemos definido al comienzo.
print("\n" + "=" * 78)
print("ANÁLISIS 4 — COMPARATIVA POR NIVEL DE RENTA (BANCO MUNDIAL)")
print("=" * 78)

# Etiquetamos cada reporte con el nivel de renta de su país notificador.
# Los países fuera de las dos listas quedan como NO_CLASIFICADO.
demo_renta = demo_gravedad.withColumn(
    "nivel_renta",
    when(col("reporter_country").isin(RENTA_ALTA), "ALTA")
    .when(col("reporter_country").isin(RENTA_MEDIA), "MEDIA")
    .otherwise("NO_CLASIFICADO")
)

# Perfil agregado por renta: mismo cálculo que el perfil por país pero agrupado por nivel de renta en lugar de por país.
perfil_renta = demo_renta.groupBy("nivel_renta").agg(
    countDistinct("primaryid").alias("reportes"),
    spark_round(avg("age_years"), 1).alias("edad_media"),
    spark_round(
        avg(when(col("sex") == "F", 1.0)
            .when(col("sex") == "M", 0.0)) * 100, 1
    ).alias("pct_mujeres"),
    spark_sum("es_muerte").alias("muertes"),
    spark_sum("es_hospitalizacion").alias("hospitalizaciones"),
)

perfil_renta = perfil_renta \
    .withColumn("pct_muertes",
        spark_round((col("muertes") / col("reportes")) * 100, 2)) \
    .withColumn("pct_hospitalizacion",
        spark_round((col("hospitalizaciones") / col("reportes")) * 100, 2))

print("\nPerfil de notificación por nivel de renta:")
perfil_renta.orderBy(col("reportes").desc()) \
    .select("nivel_renta", "reportes", "edad_media", "pct_mujeres",
            "muertes", "pct_muertes", "pct_hospitalizacion") \
    .show(truncate=False)

# Las reacciones más notificadas permiten valorar si el perfil de eventos
# adversos difiere según el nivel de desarrollo económico.
print("\nTop 10 reacciones en países de RENTA ALTA:")
ids_alta = demo_renta.filter(col("nivel_renta") == "ALTA") \
    .select("primaryid").distinct()
reac_pt.join(ids_alta, on="primaryid", how="inner") \
    .groupBy("pt_norm").agg(countDistinct("primaryid").alias("casos")) \
    .orderBy(col("casos").desc()) \
    .show(10, truncate=False)

print("\nTop 10 reacciones en países de RENTA MEDIA:")
ids_media = demo_renta.filter(col("nivel_renta") == "MEDIA") \
    .select("primaryid").distinct()
reac_pt.join(ids_media, on="primaryid", how="inner") \
    .groupBy("pt_norm").agg(countDistinct("primaryid").alias("casos")) \
    .orderBy(col("casos").desc()) \
    .show(10, truncate=False)

# Análisis 5. Fármacos GLP-1 por país
# Objetivo: caracterizar la distribución geográfica de los fármacos GLP-1,
# otra de las partes claves del periodo trabajado, y sus reacciones asociadas en España
print("\n" + "=" * 78)
print("ANÁLISIS 5 — DISTRIBUCIÓN GEOGRÁFICA DE LOS FÁRMACOS GLP-1")
print("=" * 78)

# Reportes que tienen algún fármaco GLP-1 como sospechoso primario.
glp1_reportes = drug_ps.filter(col("drugname_norm").isin(GLP1)) \
    .select("primaryid").distinct()

# Conteo de reportes GLP-1 por país.
glp1_por_pais = demo_geo.join(glp1_reportes, on="primaryid", how="inner") \
    .groupBy("reporter_country") \
    .agg(countDistinct("primaryid").alias("reportes_glp1"))

# El porcentaje de reportes GLP-1 sobre el total del país es un indicador
# indirecto de la penetración de estos fármacos en cada mercado. Se cruza con el total
# de reportes por país y se filtran los países con al menos 5.000 reportes para que las conclusiones
# sean significativas.
glp1_comparativa = glp1_por_pais \
    .join(perfil_pais.select("reporter_country", "reportes"),
          on="reporter_country", how="inner") \
    .withColumn("pct_glp1",
        spark_round((col("reportes_glp1") / col("reportes")) * 100, 2)) \
    .filter(col("reportes") >= 5000)

print("\nPaíses con mayor peso relativo de notificaciones GLP-1:")
glp1_comparativa.orderBy(col("pct_glp1").desc()) \
    .select("reporter_country", "reportes_glp1", "reportes", "pct_glp1") \
    .show(20, truncate=False)

# Reacciones más frecuentes asociadas a GLP-1 específicas de España
print("\nReacciones asociadas a GLP-1 en España:")
pares_glp1_es = drug_ps.filter(col("drugname_norm").isin(GLP1)) \
    .join(ids_es, on="primaryid", how="inner") \
    .join(reac_pt, on="primaryid", how="inner") \
    .groupBy("pt_norm") \
    .agg(countDistinct("primaryid").alias("casos_es")) \
    .orderBy(col("casos_es").desc())

pares_glp1_es.show(15, truncate=False)

# Análisis 6. Evolución temporal del peso de España
# Objetivo: mostrar cómo evoluciona la proporción de reportes españoles sobre el total
# trimestre a trimestre. Sirve además para visualizar el efecto de la recodificación ES -> EU.
print("\n" + "=" * 78)
print("ANÁLISIS 6 — EVOLUCIÓN TRIMESTRAL DEL PESO DE ESPAÑA")
print("=" * 78)

# Total de reportes por trimestre (todos los países)
por_trimestre = demo_geo.groupBy("trimestre").agg(
    countDistinct("primaryid").alias("total_trimestre")
)

# Reportes españoles por trimestre
es_por_trimestre = demo_geo.filter(col("reporter_country") == "ES") \
    .groupBy("trimestre") \
    .agg(countDistinct("primaryid").alias("reportes_es"))

# Cruce mediante left join para conservar todos los trimestres, incluidos aquellos sin reportes
# españoles, que quedan a 0 gracias a coalesce.
# pct_es expresa el peso de España en cada trimestre
evolucion_es = por_trimestre \
    .join(es_por_trimestre, on="trimestre", how="left") \
    .withColumn("reportes_es", coalesce(col("reportes_es"), lit(0))) \
    .withColumn("pct_es",
        spark_round((col("reportes_es") / col("total_trimestre")) * 100, 3)) \
    .orderBy("trimestre")

print("\nPeso de España en el total de notificaciones, por trimestre:")
evolucion_es.select("trimestre", "reportes_es", "total_trimestre",
                    "pct_es") \
    .show(24, truncate=False)

# Análisis 7. Concentración geográfica de la notificación
# Objetivo: cuantificar hasta que punto el sistema FAERS depende de un número reducido de países,
# mediante el índice Herfindahl-Hirschman (HHI).
print("\n" + "=" * 78)
print("ANÁLISIS 7 — CONCENTRACIÓN GEOGRÁFICA DE LA NOTIFICACIÓN")
print("=" * 78)

# El índice de Herfindahl-Hirschman mide la concentración de un sistema.
# Se calcula como la suma de los cuadrados de las cuotas de mercado
# en este caso la cuota de cada país sobre el total de reportes. Interpretación:
#   - HHI próximo a 1  -> la notificación depende de muy pocos países.
#   - HHI próximo a 0  -> la notificación está repartida de forma equitativa.
# Elevar al cuadraro penaliza a los países con una cuota alta, de tal manera que el índice
# crece cuando unos pocos países concentran la mayoría de reportes.
cuotas = perfil_pais \
    .withColumn("cuota", col("reportes") / lit(float(total_analizable))) \
    .withColumn("cuota_cuadrado", col("cuota") * col("cuota"))

# collect() trae un único valor escalar al driver, es seguro porque es el resultado de una
# agregación global
hhi = cuotas.agg(spark_sum("cuota_cuadrado").alias("hhi")).collect()[0]["hhi"]

n_paises = perfil_pais.count()

# Cuota acumulada de los 5 y 10 principales notificadores, como medida complementaria
# e intuitiva de la concentración.
top_paises = perfil_pais.orderBy(col("reportes").desc()) \
    .limit(5).agg(spark_sum("reportes").alias("top5")).collect()[0]["top5"]
top10 = perfil_pais.orderBy(col("reportes").desc()) \
    .limit(10).agg(spark_sum("reportes").alias("top10")).collect()[0]["top10"]

print(f"\nPaíses notificadores distintos: {n_paises:,}")
print(f"Índice de Herfindahl-Hirschman: {hhi:.4f}")
print(f"Cuota de los 5 principales notificadores: "
      f"{(top_paises / total_analizable) * 100:.1f}%")
print(f"Cuota de los 10 principales notificadores: "
      f"{(top10 / total_analizable) * 100:.1f}%")
print("\nUn HHI elevado indica que el sistema FAERS depende de forma "
      "acusada de un\nnúmero reducido de países, lo que limita la "
      "representatividad global de las\nseñales detectadas sobre el "
      "agregado mundial y refuerza el interés del\nanálisis desagregado "
      "por país.")

# Persistencia de resultados
# Cada tabla de resultados se materializa en Delta Lake para que el frontend Streamlit posteriormente
# pueda consumirlas sin recalcular el análisis de cada carga.
print("\n" + "=" * 78)
print("GUARDANDO RESULTADOS EN DELTA LAKE")
print("=" * 78)

# Diccionario nombre_tabla -> DataFrame. Se recorre escribiendo cada resultado
# en su ruta correspondiente con modo overwrite (reejecutable) y overwriteSchema
# que permite cambios de esquema entre ejecuciones.
salidas = {
    "geo_perfil_paises": perfil_pais,
    "geo_divergencia_farmacos": divergencia_farmacos,
    "geo_divergencia_reacciones": divergencia_reacciones,
    "geo_senales_espana": comparativa,
    "geo_perfil_renta": perfil_renta,
    "geo_glp1_paises": glp1_comparativa,
    "geo_evolucion_espana": evolucion_es,
}

for nombre, df in salidas.items():
    ruta = f"{CURATED_PATH}/{nombre}"
    df.write.format("delta").mode("overwrite") \
        .option("overwriteSchema", "true").save(ruta)
    print(f"  {nombre}")

print("\nAnálisis geográfico completado.")

spark.stop()



































