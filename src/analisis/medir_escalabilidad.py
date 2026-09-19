"""
medir_escalabilidad.py

Metodología:
Se ejecuta la fase de cálculo de señales, que es la más costosa del pipeline por
combinar dos joins sobre tablas de decenas de millones de filas con una
agregación de alta cardinalidad, sobre subconjuntos crecientes del periodo
analizado: 4, 8, 12, 16 y 24 trimestres. Los recursos permanecen fijos en los
doce núcleos disponibles y 16 GB de memoria de driver.

Consideraciones metodológicas:
  - Se realiza una ejecución de calentamiento previa cuyo resultado se descarta.
    La primera ejecución sobre una máquina virtual de Java incurre en el coste
    de compilación en tiempo de ejecución, que distorsionaría la comparación.
  - La caché se limpia entre mediciones para que ninguna ejecución se beneficie
    de los resultados de la anterior.
  - Cada configuración se ejecuta el número de repeticiones indicado en
    REPETICIONES y se conserva la mediana, que es menos sensible que la media a
    una ejecución atípica.
  - La memoria se muestrea sobre el árbol de procesos completo, ya que en modo
    local el motor se ejecuta en un proceso hijo distinto del intérprete.

"""

import json
import os
import statistics
import threading
import time

from pyspark.sql import SparkSession
from pyspark.sql.functions import broadcast, col, countDistinct, lit
from delta import configure_spark_with_delta_pip

CURATED_PATH = os.path.expanduser("~/pharmasignal/data/curated")
SALIDA = os.path.expanduser("~/pharmasignal/outputs/escalabilidad.json")

# Configuración del experimento. Se define como constantes para que las
# decisiones queden explícitas y sean reproducibles.
NUCLEOS = 12                    # recursos fijos durante todo el escalado de carga
MEMORIA_DRIVER = "16g"
PARTICIONES = 200
REPETICIONES = 3                # mediciones por configuración; se toma la mediana
VOLUMENES = [4, 8, 12, 16, 24]  # trimestres acumulados

# Los 24 trimestres en orden cronológico. Los subconjuntos se toman siempre
# desde el principio de la serie para que el crecimiento sea acumulativo y no
# dependa de qué trimestres concretos se seleccionen.
TRIMESTRES = [f"{a}q{q}" for a in range(2020, 2026) for q in range(1, 5)]

# Umbrales del cálculo de señales, replicados de prr_ror.py.
MIN_CASOS = 3


class MonitorMemoria:
    """Muestrea el consumo de memoria del árbol de procesos en segundo plano.

    En modo local el motor de procesamiento se ejecuta sobre una máquina virtual
    de Java lanzada como proceso hijo del intérprete, de modo que medir
    únicamente el proceso principal no reflejaría el consumo real.

    """

    def __init__(self, intervalo=0.5):
        self.intervalo = intervalo
        self.pico_mb = 0.0
        self._activo = False
        self._hilo = None
        try:
            import psutil
            self._psutil = psutil
            self._proc = psutil.Process(os.getpid())
        except ImportError:
            self._psutil = None

    def _muestrear(self):
        while self._activo:
            try:
                total = self._proc.memory_info().rss
                for hijo in self._proc.children(recursive=True):
                    try:
                        total += hijo.memory_info().rss
                    except Exception:
                        pass
                self.pico_mb = max(self.pico_mb, total / (1024 ** 2))
            except Exception:
                pass
            time.sleep(self.intervalo)

    def __enter__(self):
        if self._psutil is not None:
            self._activo = True
            self._hilo = threading.Thread(target=self._muestrear, daemon=True)
            self._hilo.start()
        return self

    def __exit__(self, *args):
        self._activo = False
        if self._hilo is not None:
            self._hilo.join(timeout=2)

    @property
    def resultado(self):
        return round(self.pico_mb, 1) if self._psutil is not None else None


def crear_sesion(nucleos, memoria):
    """Construye una sesión con los recursos indicados."""
    builder = SparkSession.builder \
        .appName(f"PharmaSignal-Escalabilidad-{nucleos}c") \
        .master(f"local[{nucleos}]") \
        .config("spark.driver.memory", memoria) \
        .config("spark.sql.shuffle.partitions", str(PARTICIONES)) \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    ses = configure_spark_with_delta_pip(builder).getOrCreate()
    ses.sparkContext.setLogLevel("ERROR")
    return ses


def calcular_senales(spark, n_trimestres):
    """Ejecuta la fase de cálculo de señales sobre los primeros n trimestres.

    Reproduce la cadena de prr_ror.py: construcción de la tabla de contingencia
    a partir de los pares fármaco-reacción y cálculo de la medida de
    desproporcionalidad. Devuelve el número de combinaciones evaluadas y el
    número de reportes del subconjunto.

    La acción final es un recuento, necesario para que la ejecución sea
    perezosa solo hasta ese punto, sin una acción, el motor no llegaría a
    ejecutar nada y la medición carecería de sentido.
    """
    subconjunto = TRIMESTRES[:n_trimestres]

    demo = spark.read.format("delta").load(f"{CURATED_PATH}/demo_curado") \
        .filter(col("trimestre").isin(subconjunto)) \
        .select("primaryid").distinct()

    drug = spark.read.format("delta").load(f"{CURATED_PATH}/drug_curado") \
        .filter((col("rol") == "PS") & col("trimestre").isin(subconjunto)) \
        .select("primaryid", "drugname_norm").distinct()

    reac = spark.read.format("delta").load(f"{CURATED_PATH}/reac_curado") \
        .filter(col("trimestre").isin(subconjunto)) \
        .select("primaryid", "pt_norm").distinct()

    n_reportes = demo.count()

    # Pares fármaco-reacción presentes en un mismo reporte.
    pares = drug.join(demo, on="primaryid", how="inner") \
                .join(reac, on="primaryid", how="inner") \
                .select("primaryid", "drugname_norm", "pt_norm").distinct()

    # Celda 'a' de la tabla de contingencia y marginales.
    conteo_a = pares.groupBy("drugname_norm", "pt_norm") \
        .agg(countDistinct("primaryid").alias("a"))

    n_farmaco = pares.groupBy("drugname_norm") \
        .agg(countDistinct("primaryid").alias("n_farmaco"))

    n_reaccion = pares.groupBy("pt_norm") \
        .agg(countDistinct("primaryid").alias("n_reaccion"))

    # Reconstrucción de la tabla 2x2
    contingencia = conteo_a \
        .join(broadcast(n_farmaco), on="drugname_norm", how="inner") \
        .join(broadcast(n_reaccion), on="pt_norm", how="inner") \
        .filter(col("a") >= MIN_CASOS) \
        .withColumn("b", col("n_farmaco") - col("a")) \
        .withColumn("c", col("n_reaccion") - col("a")) \
        .withColumn("a", col("a").cast("double") + lit(0.5)) \
        .withColumn("b", col("b").cast("double") + lit(0.5)) \
        .withColumn("c", col("c").cast("double") + lit(0.5)) \
        .withColumn("d", lit(float(n_reportes)) - col("a") - col("b")
                    - col("c") + lit(0.5)) \
        .withColumn("prr",
                    (col("a") / (col("a") + col("b"))) /
                    (col("c") / (col("c") + col("d"))))

    n_combinaciones = contingencia.count()
    return n_combinaciones, n_reportes


def medir(spark, n_trimestres, repeticiones):
    """Ejecuta la medición y devuelve la mediana de los tiempos observados."""
    tiempos = []
    memorias = []
    n_comb = n_rep = 0

    for i in range(repeticiones):
        # La caché se limpia antes de cada repetición para que ninguna se
        # beneficie de los resultados de la anterior.
        spark.catalog.clearCache()

        with MonitorMemoria() as mon:
            inicio = time.perf_counter()
            n_comb, n_rep = calcular_senales(spark, n_trimestres)
            transcurrido = time.perf_counter() - inicio

        tiempos.append(transcurrido)
        if mon.resultado is not None:
            memorias.append(mon.resultado)
        print(f"    repetición {i + 1}/{repeticiones}: {transcurrido:7.2f} s")

    return {
        "trimestres": n_trimestres,
        "reportes": n_rep,
        "combinaciones": n_comb,
        "tiempo_mediana_s": round(statistics.median(tiempos), 2),
        "tiempo_min_s": round(min(tiempos), 2),
        "tiempo_max_s": round(max(tiempos), 2),
        "memoria_pico_mb": round(statistics.median(memorias), 1) if memorias else None,
    }


def main():
    print("\n" + "=" * 78)
    print("MEDICIÓN DE ESCALABILIDAD — ESCALADO DE CARGA")
    print("=" * 78)
    print(f"Recursos fijos: local[{NUCLEOS}], driver {MEMORIA_DRIVER}, "
          f"{PARTICIONES} particiones")
    print(f"Repeticiones por configuración: {REPETICIONES}")

    spark = crear_sesion(NUCLEOS, MEMORIA_DRIVER)

    # Ejecución de calentamiento. Su resultado se descarta, la primera ejecución
    # sobre la máquina virtual incurre en el coste de compilación en tiempo de
    # ejecución y en la lectura inicial de los metadatos de las tablas, costes
    # que no se repiten después y que distorsionarían la comparación.
    print("\nEjecución de calentamiento (resultado descartado)...")
    calcular_senales(spark, 4)
    spark.catalog.clearCache()

    resultados = []
    for n in VOLUMENES:
        print(f"\n  {n} trimestres:")
        r = medir(spark, n, REPETICIONES)
        resultados.append(r)
        print(f"    -> {r['reportes']:,} reportes · "
              f"{r['combinaciones']:,} combinaciones · "
              f"mediana {r['tiempo_mediana_s']} s")

    spark.stop()

    # Métricas derivadas. El tiempo por millón de reportes es la magnitud que
    # permite valorar la naturaleza del escalado, si se mantiene estable al
    # aumentar el volumen, el crecimiento del tiempo es proporcional a la carga,
    # si disminuye, el sistema aprovecha mejor los recursos con volúmenes
    # mayores, comportamiento habitual cuando el coste fijo de planificación se
    # reparte entre más datos.
    print("\n" + "=" * 78)
    print("RESULTADOS")
    print("=" * 78)
    print(f"\n{'Trimestres':>11} {'Reportes':>12} {'Combinaciones':>14} "
          f"{'Tiempo (s)':>11} {'s/M reportes':>13} {'Memoria (MB)':>13}")
    print("-" * 78)

    base = resultados[0]
    for r in resultados:
        por_millon = r["tiempo_mediana_s"] / (r["reportes"] / 1_000_000)
        r["segundos_por_millon"] = round(por_millon, 2)
        r["factor_volumen"] = round(r["reportes"] / base["reportes"], 2)
        r["factor_tiempo"] = round(
            r["tiempo_mediana_s"] / base["tiempo_mediana_s"], 2)
        mem = f"{r['memoria_pico_mb']:,.0f}" if r["memoria_pico_mb"] else "n/d"
        print(f"{r['trimestres']:>11} {r['reportes']:>12,} "
              f"{r['combinaciones']:>14,} {r['tiempo_mediana_s']:>11.2f} "
              f"{por_millon:>13.2f} {mem:>13}")

    print("\nFactores de crecimiento respecto a la configuración de 4 trimestres:")
    print(f"{'Trimestres':>11} {'× volumen':>11} {'× tiempo':>10} {'Relación':>10}")
    print("-" * 46)
    for r in resultados:
        rel = r["factor_tiempo"] / r["factor_volumen"] if r["factor_volumen"] else 0
        print(f"{r['trimestres']:>11} {r['factor_volumen']:>11.2f} "
              f"{r['factor_tiempo']:>10.2f} {rel:>10.2f}")

    print("\nUna relación inferior a 1 indica que el tiempo crece menos que "
          "proporcionalmente\nal volumen, es decir, un escalado sublineal.")

    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump({
            "configuracion": {
                "nucleos": NUCLEOS,
                "memoria_driver": MEMORIA_DRIVER,
                "particiones": PARTICIONES,
                "repeticiones": REPETICIONES,
            },
            "resultados": resultados,
        }, f, indent=2, ensure_ascii=False)

    print(f"\nResultados guardados en: {SALIDA}")


if __name__ == "__main__":
    main()