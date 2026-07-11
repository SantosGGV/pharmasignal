"""
explorar_faers.py

Este script servirá para la exploración inicial de los datos FAERS.
El objetivo es verificar que PySpark lee correctamente los ficheros ASCII
de FAERS y entender la estructura real de los datos antes de construir
el pipeline de ingesta completo.

"""

from pyspark.sql import SparkSession
import os

# Configuraicón de la sesión Spark
# Se usa modo local[*] para aprovechar todos los núcleos disponibles
# sin necesitar un cluster externo. 8 GB de driver memory es suficiente
# para la exploración de un solo trimestre.

spark = SparkSession.builder \
    .appName("PharmaSignal-Exploración") \
    .master("local[*]") \
    .config("spark.driver.memory", "8g") \
    .getOrCreate()

# Suprimimos los logs INFO/WARN de Spark para que la salida sea legible
spark.sparkContext.setLogLevel("ERROR")


# Rutas de los datos
# Los ficheros FAERS estan almacenados en WSL2
# (~/pharmasignal/data/raw/) para maximizar el rendimiento de I/O.

RAW_PATH = os.path.expanduser("~/pharmasignal/data/raw")

# Exploramos el trimestre 2020Q1 como muestra representativa
demo_path = f"{RAW_PATH}/faers_ascii_2020q1/ASCII/DEMO20Q1.txt"


# Lectura del fichero
# Los ficheros ASCII de FAERS usan el separador "$" (pipe-dollar)
# y tienen cabecera en la primera fila.
# inferSchema=True detecta automáticamente los tipos de columna.

demo = spark.read \
    .option("header", "true") \
    .option("sep", "$") \
    .option("inferSchema", "true") \
    .csv(demo_path)

# Mostramos el schema para documentar la estructura real de los datos
print("=== SCHEMA DEMO ===")
demo.printSchema()

# Conteo de filas para validar el volumen del trimestre
print(f"\n=== FILAS 2020Q1: {demo.count()} ===")

# Muestra de las primeras filas para inspección visual
print("\n=== PRIMERAS 5 FILAS ===")
demo.show(5, truncate=False)

# Cerramos la sesión Spark para liberar recursos
spark.stop()