"""
curar_drug.py

Curación de la tabla DRUG de FAERS.
Reglas aplicadas:

1. Alineación con DEMO curado:
Se retienen únicamente los resgistros cuyo primaryid
existe en la tabla DEMO curada. Esto elimina automáticamente los fármacos de reportes
que no superaron la deduplicación en DEMO.

2. Filtro por rol del fármaco:
"1" = Primary Suspect - fármaco principal sospechoso de causar la reacción.
"2" = Seconday Suspect, "3" = Concomitant, "4" = Interacting.
Se conservan todos los roles pero se añade columna normalizada.
El cálculo de PRR y ROR usa exclusivamente el rol "1"

3. Normalización de drugname:
El nombre del fármaco presenta alta variabilidad (nombres comerciales, genéricos, abreviaturas, errores
tipográficos, espacios, puntuación). Se aplica:
- Conversión a minúsculas y elinimación de espacios.
- Eliminación de puntuación final (puntos, comas, guiones).
- Eliminación contenido entre paréntesis para quedarse con el nombre principal del fármaco.
- Los registros sin nombre de fármaco se descartan.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, trim, lower, upper, regexp_replace, when
)
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Curación-DRUG") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Cargamos DRUG desde Delta Lake (dato crudo consolidado)
drug = spark.read.format("delta").load(f"{CURATED_PATH}/drug")
total_inicial = drug.count()
print(f"\nRegistros iniciales DRUG: {total_inicial:,}")

# Cargamos DEMO curado para alinearlo por primaryid
demo_curado = spark.read.format("delta").load(f"{CURATED_PATH}/demo_curado")
primaryids_validos = demo_curado.select("primaryid").distinct()

# Regla 1. Alineación con DEMO curado
# Solo conservamos fármacos de reportes que superaron la curación de DEMO.
# Esto elimina automáticamente los duplicados de versiones antiguas.
drug_alineado = drug.join(primaryids_validos, on="primaryid", how="inner")
total_alineado = drug_alineado.count()
print(f"Tras alineación con DEMO curado: {total_alineado:,} "
      f"({total_inicial - total_alineado:,} registros eliminados)")

# Regla 2. Normalización del rol del fármaco
# Mapeamos drugcharacterization a etiqueta legible para facilitar filtros.
# Se realiza modificación
# role_cod ya viene como texto en FAERS ASCII:
# PS = Primary Suspect, SS = Secondary Suspect,
# C = Concominant, I = Interacting
drug_rol = drug_alineado.withColumn(
    "rol",
    when(upper(trim(col("role_cod"))) == "PS", "PS")
    .when(upper(trim(col("role_cod"))) == "SS", "SS")
    .when(upper(trim(col("role_cod"))) == "C",  "C")
    .when(upper(trim(col("role_cod"))) == "I",  "I")
    .otherwise("UNK")
)

# Conteo por rol para documentar la distribución
print("\nDistribución por rol del fármaco:")
drug_rol.groupBy("rol").count().orderBy("rol").show()

# Regla 3. Normalización de drugname
# Paso 1: eliminamos el contenido entre paréntesis para quedarnos con el nombre principal.
# Paso 2: convertimos a minúsculas y eliminamos espacios extremos.
# Paso 3: eliminamos puntuación final (puntos, comas).
# Paso 4: eliminamos espacios múltiples internos.
drug_norm = drug_rol \
    .withColumn("drugname_norm",
        regexp_replace(
            trim(lower(
                regexp_replace(col("drugname"), r'\s*\(.*?\)', '')
            )),
            r'[.,;]+$', ''
        )
    ) \
    .withColumn("drugname_norm",
        regexp_replace(col("drugname_norm"), r'\s+', ' ')
    )

# Regla 4. Eliminación de registros sin drugname
sin_nombre_antes = drug_norm.filter(
    col("drugname").isNull() | (trim(col("drugname")) == "")
).count()

drug_limpio = drug_norm.filter(
    col("drugname_norm").isNotNull() & (col("drugname_norm") != "")
)

print(f"\nRegistros sin nombre de fármaco eliminados: {sin_nombre_antes:,}")

total_final = drug_limpio.count()
print(f"\nRegistros finales DRUG curado: {total_final:,}")
print(f"Reducción total respecto al original: "
      f"{total_inicial - total_final:,} registros")

# Fármacos únicos tras la normalización
farmacos_unicos = drug_limpio.select("drugname_norm").distinct().count()
farmacos_unicos_raw = drug_limpio.select("drugname").distinct().count()
print(f"\nFármacos únicos antes de normalización: {farmacos_unicos_raw:,}")
print(f"Fármacos únicos tras normalización: {farmacos_unicos:,}")
print(f"Reducción por normalización: "
      f"{farmacos_unicos_raw - farmacos_unicos:,} variantes consolidadas")

# Mostramos los 20 fármacos más notificados como Primary Suspect
print("\nTop 20 fármacos Primary Suspect (PS) tras normalización:")
drug_limpio.filter(col("rol") == "PS") \
    .groupBy("drugname_norm").count() \
    .orderBy(col("count").desc()) \
    .show(20, truncate=False)

# Guardamos DRUG curado en Delta Lake
ruta_salida = f"{CURATED_PATH}/drug_curado"
drug_limpio.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(ruta_salida)

print(f"\nDRUG curado guardado en: {ruta_salida}")
print("\n=== SCHEMA DRUG CURADO ===")
drug_limpio.printSchema()

spark.stop()

























