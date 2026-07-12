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
    col, trim, lower, regexp_replace, when
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
drug_rol = drug_alineado.withColumn(
    "rol",
    when(col("drugcharacterization") == "1", "PS")
    .when(col("drugcharacterization") == "2", "SS")
    .when(col("drugcharacterization") == "3", "C")
    .when(col("drugcharacterization") == "4", "I")
    .otherwise("UNK")
)

# Conteo por rol para documentar la distribución
print("\nDistribución por rol del fármaco:")
drug_rol.groupBy("rol").count().orderBy("rol").show()



























