"""
validar_curacion.py

Fichero creado para validar la integración del conjunto de datos curado

Este fichero cierra la fase de curación de los datos de FAERS verificando
que las siete tablas curadas mantienen coherencia entre sí. La curación se ha
realizado tabla a tabla, por lo que es necesario comprobar el resultado del conjunto
de datos con el fin de verificar que es consistente y apto para poder comenzar con la explotación.

Validaciones realizadas:
1. Integridad referencial: todos los primaryid de las tabla deben existir en la tabla
maestra DEMO curada.

2. Cobertura: proporción de reportes de DEMO que tienen al menos un registro asociado en
cada tabla de detalle. Un reporte que no tiene un fármaco o reacción no es explotable.

3. Unicidad: la tabla DEMO curada no debe contener primaryid duplicados tras la deduplicación realizada.

4. Volumetría: recuento final de cada tabla y reducción respecto a los datos en crudo,
como evidencia del proceso de curación.

5. Base analítica: número de reportes que disponen de un fármaco sospechoso primario y reacción
adversa, que constituyen el conjunto sobre el que se calcularán PRR y ROR.

"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, countDistinct
from delta import configure_spark_with_delta_pip
import os

builder = SparkSession.builder \
    .appName("PharmaSignal-Validación-Curación") \
    .master("local[*]") \
    .config("spark.driver.memory", "16g") \
    .config("spark.executor.memory", "8g") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")

# Volumetría de los datos en crudo, para calcular la reducción por curación
CRUDO = {
    "demo": 10_355_898,
    "drug": 46_798_527,
    "reac": 35_234_423,
    "outc":  7_926_428,
    "indi": 30_394_424,
    "ther": 15_492_129,
    "rpsr":    307_435,
}

# Cargamos las tablas curadas
demo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_geo")
drug = spark.read.format("delta").load(f"{CURATED_PATH}/drug_curado")
reac = spark.read.format("delta").load(f"{CURATED_PATH}/reac_curado")
outc = spark.read.format("delta").load(f"{CURATED_PATH}/outc_curado")
indi = spark.read.format("delta").load(f"{CURATED_PATH}/indi_curado")
ther = spark.read.format("delta").load(f"{CURATED_PATH}/ther_curado")
rpsr = spark.read.format("delta").load(f"{CURATED_PATH}/rpsr_curado")

tablas_detalle = {
    "drug": drug,
    "reac": reac,
    "outc": outc,
    "indi": indi,
    "ther": ther,
    "rpsr": rpsr,
}

demo_ids = demo.select("primaryid").distinct()
total_demo = demo.count()
ids_demo_distintos = demo_ids.count()

print("\n")
print("VALIDACIÓN 1 — UNICIDAD DE LA TABLA MAESTRA")
print(f"Filas en DEMO curado:        {total_demo:,}")
print(f"primaryid distintos:         {ids_demo_distintos:,}")
duplicados = total_demo - ids_demo_distintos
if duplicados == 0:
    print("Resultado: CORRECTO — no existen primaryid duplicados")
else:
    print(f"Resultado: ATENCIÓN — {duplicados:,} primaryid duplicados")

print("\n")
print("VALIDACIÓN 2 — INTEGRIDAD REFERENCIAL")
print("Registros de cada tabla de detalle cuyo primaryid no existe")
print("en la tabla maestra DEMO (deberían ser cero):\n")

for nombre, tabla in tablas_detalle.items():
    huerfanos = tabla.join(demo_ids, on="primaryid", how="left_anti").count()
    estado = "CORRECTO" if huerfanos == 0 else "ATENCIÓN"
    print(f"  {nombre.upper():6} {huerfanos:>12,} huérfanos   [{estado}]")

print("\n")
print("VALIDACIÓN 3 — COBERTURA DE LAS TABLAS DE DETALLE")
print("Proporción de reportes de DEMO con al menos un registro")
print("asociado en cada tabla de detalle:\n")

for nombre, tabla in tablas_detalle.items():
    ids_tabla = tabla.select("primaryid").distinct()
    cubiertos = demo_ids.join(ids_tabla, on="primaryid", how="inner").count()
    pct = (cubiertos / ids_demo_distintos) * 100
    print(f"  {nombre.upper():6} {cubiertos:>12,} reportes  ({pct:5.1f}%)")

print("\n")
print("VALIDACIÓN 4 — VOLUMETRÍA Y REDUCCIÓN POR CURACIÓN")
print(f"{'Tabla':<8}{'Crudo':>15}{'Curado':>15}{'Reducción':>15}{'%':>8}")

total_crudo = 0
total_curado = 0

todas = {"demo": demo, **tablas_detalle}
for nombre, tabla in todas.items():
    n_crudo = CRUDO[nombre]
    n_curado = tabla.count()
    reduccion = n_crudo - n_curado
    pct = (reduccion / n_crudo) * 100
    total_crudo += n_crudo
    total_curado += n_curado
    print(f"{nombre.upper():<8}{n_crudo:>15,}{n_curado:>15,}"
          f"{reduccion:>15,}{pct:>7.1f}%")

reduccion_total = total_crudo - total_curado
pct_total = (reduccion_total / total_crudo) * 100
print("\n")
print(f"{'TOTAL':<8}{total_crudo:>15,}{total_curado:>15,}"
      f"{reduccion_total:>15,}{pct_total:>7.1f}%")

print("\n")
print("VALIDACIÓN 5 — BASE ANALÍTICA PARA PRR/ROR")

# Reportes con al menos un fármaco sospechoso primario
ids_ps = drug.filter(col("rol") == "PS").select("primaryid").distinct()
n_ps = ids_ps.count()

# Reportes con al menos una reacción adversa
ids_reac = reac.select("primaryid").distinct()
n_reac = ids_reac.count()

# Reportes con ambos: base del cálculo de PRR y ROR
base_analitica = ids_ps.join(ids_reac, on="primaryid", how="inner").count()
pct_base = (base_analitica / ids_demo_distintos) * 100

print(f"Reportes con fármaco sospechoso primario (PS): {n_ps:,}")
print(f"Reportes con reacción adversa notificada:      {n_reac:,}")
print(f"Reportes con ambos (base PRR/ROR):            {base_analitica:,}")
print(f"Cobertura sobre el total de DEMO:              {pct_base:.1f}%")

print("\n")
print("VALIDACIÓN COMPLETADA")

spark.stop()