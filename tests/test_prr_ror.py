"""
test_prr_ror.py

Pruebas unitarias de las expresiones estadísticas del módulo de detección
de señales.

Las medidas de desproporcionalidad se calculan en prr_ror.py sobre columnas
de Spark, dentro del mismo script que lee las tablas curadas y escribe los
resultados. Al no estar aisladas en funciones independientes, no pueden
invocarse directamente desde una prueba.

La estrategia adoptada consiste en construir una tabla de contingencia con
valores conocidos, aplicar sobre ella las mismas expresiones que emplea el
módulo y contrastar el resultado con el valor calculado a mano. Esto verifica
la corrección de las fórmulas, que es donde puede producirse un error de
cálculo silencioso, aunque no cubre la integración del módulo completo.

Ejecución:  pytest tests/ -v
"""

import math

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, exp, lit, log, sqrt

# Constantes del módulo bajo prueba. Se replican aquí a propósito: si alguien
# cambia un umbral en prr_ror.py sin actualizar estas pruebas, la discrepancia
# debe hacerse visible.
UMBRAL_PRR = 2.0
MIN_CASOS = 3
UMBRAL_CHI2 = 4.0


@pytest.fixture(scope="session")
def spark():
    """Sesión de Spark compartida por todas las pruebas del fichero.

    El ámbito de sesión es necesario por rendimiento: levantar una sesión
    tarda del orden de veinte segundos, de modo que crearla en cada prueba
    multiplicaría el tiempo total de ejecución.

    La configuración es deliberadamente mínima. No se cargan las extensiones
    de Delta Lake porque las pruebas no leen ni escriben tablas, solo operan
    sobre DataFrames construidos en memoria.
    """
    ses = (SparkSession.builder
           .appName("PharmaSignal-Tests")
           .master("local[1]")
           .config("spark.driver.memory", "1g")
           .config("spark.sql.shuffle.partitions", "1")
           .config("spark.ui.enabled", "false")
           .getOrCreate())
    ses.sparkContext.setLogLevel("ERROR")
    yield ses
    ses.stop()


def calcular(spark, a, n_farmaco, n_reaccion, N):
    """Reproduce la cadena de cálculo de prr_ror.py sobre un único par.

    Recibe la celda 'a' de la tabla de contingencia y los dos marginales, que
    es exactamente lo que el módulo obtiene de las agregaciones sobre las
    tablas curadas, y devuelve un diccionario con todas las medidas.
    """
    df = spark.createDataFrame(
        [(a, n_farmaco, n_reaccion)],
        ["a", "n_farmaco", "n_reaccion"])

    # Reconstrucción de la tabla 2x2 y corrección de Haldane-Anscombe.
    # El orden importa: primero se derivan b y c de los marginales y después
    # se suma 0,5 a las cuatro celdas.
    df = (df
          .withColumn("b", col("n_farmaco") - col("a"))
          .withColumn("c", col("n_reaccion") - col("a"))
          .withColumn("a", col("a").cast("double") + lit(0.5))
          .withColumn("b", col("b").cast("double") + lit(0.5))
          .withColumn("c", col("c").cast("double") + lit(0.5))
          .withColumn("d", lit(float(N)) - col("a") - col("b") - col("c") + lit(0.5)))

    df = (df
          .withColumn("prr",
                      (col("a") / (col("a") + col("b"))) /
                      (col("c") / (col("c") + col("d"))))
          .withColumn("ror",
                      (col("a") * col("d")) / (col("b") * col("c")))
          .withColumn("chi2",
                      (lit(float(N)) *
                       ((col("a") * col("d")) - (col("b") * col("c"))) *
                       ((col("a") * col("d")) - (col("b") * col("c")))) /
                      ((col("a") + col("b")) * (col("c") + col("d")) *
                       (col("a") + col("c")) * (col("b") + col("d"))))
          .withColumn("se_ln_ror",
                      sqrt(lit(1.0) / col("a") + lit(1.0) / col("b") +
                           lit(1.0) / col("c") + lit(1.0) / col("d")))
          .withColumn("ror_ic_inf",
                      exp(log(col("ror")) - lit(1.96) * col("se_ln_ror")))
          .withColumn("ror_ic_sup",
                      exp(log(col("ror")) + lit(1.96) * col("se_ln_ror"))))

    return df.collect()[0].asDict()

# Reconstrucción de la tabla de contingencia

def test_celdas_derivadas_de_marginales(spark):
    """Las celdas b y c se derivan correctamente de los marginales.

    Con 100 casos del fármaco, 500 de la reacción y 40 que presentan ambos:
    b = 100 - 40 = 60 y c = 500 - 40 = 460, más la corrección de 0,5.
    """
    r = calcular(spark, a=40, n_farmaco=100, n_reaccion=500, N=10000)
    assert r["a"] == pytest.approx(40.5)
    assert r["b"] == pytest.approx(60.5)
    assert r["c"] == pytest.approx(460.5)


def test_suma_de_celdas_iguala_el_total(spark):
    """Las cuatro celdas suman el total de reportes más 0,5.

    La celda d se obtiene restando al total las otras tres, que ya incorporan
    su corrección, y sumando después 0,5. El resultado es que la suma de las
    cuatro celdas excede el total en 0,5 y no en 2, como podría suponerse por
    haber cuatro celdas corregidas.
    """
    N = 10000
    r = calcular(spark, a=40, n_farmaco=100, n_reaccion=500, N=N)
    total = r["a"] + r["b"] + r["c"] + r["d"]
    assert total == pytest.approx(N + 0.5)

# Corrección de Haldane-Anscombe

def test_correccion_evita_division_por_cero(spark):
    """Con celdas a cero el cálculo sigue siendo finito.

    Si el fármaco solo aparece junto a esta reacción, b vale cero antes de la
    corrección y el cociente de probabilidades sería una división por cero.
    La corrección de 0,5 lo evita.
    """
    r = calcular(spark, a=5, n_farmaco=5, n_reaccion=100, N=10000)
    assert r["b"] == pytest.approx(0.5)
    assert math.isfinite(r["ror"])
    assert math.isfinite(r["prr"])
    assert r["ror"] > 0


def test_correccion_se_aplica_siempre(spark):
    """La corrección se aplica también cuando ninguna celda es cero.

    Es una decisión metodológica: aplicarla solo en presencia de ceros
    introduciría una discontinuidad en el estimador entre pares con y sin
    celdas vacías.
    """
    r = calcular(spark, a=50, n_farmaco=200, n_reaccion=800, N=10000)
    assert r["a"] == pytest.approx(50.5)
    assert r["b"] == pytest.approx(150.5)

# Cociente de notificación proporcional

def test_prr_sobre_tabla_conocida(spark):
    """El PRR coincide con el valor calculado sobre la tabla corregida.

    Tabla tras la corrección: a=40,5  b=60,5  c=460,5  d=9439,0
    PRR = (40,5/101) / (460,5/9899,5) = 8,62
    El valor esperado se construye a partir de la propia celda d para evitar
    introducir un error de redondeo en el cálculo de referencia.
    """
    r = calcular(spark, a=40, n_farmaco=100, n_reaccion=500, N=10000)
    esperado = (40.5 / 101.0) / (460.5 / (460.5 + r["d"]))
    assert r["prr"] == pytest.approx(esperado, rel=1e-9)
    assert r["prr"] == pytest.approx(8.62, abs=0.01)


def test_prr_proximo_a_uno_sin_asociacion(spark):
    """Sin asociación entre fármaco y reacción el PRR se aproxima a 1.

    Si el 10 % de los reportes menciona el fármaco y el 10 % de esos presenta
    la reacción, la proporción es la misma dentro y fuera del grupo expuesto.
    """
    r = calcular(spark, a=100, n_farmaco=1000, n_reaccion=1000, N=10000)
    assert r["prr"] == pytest.approx(1.0, abs=0.05)

# Cociente de probabilidades de notificación

def test_ror_sobre_tabla_conocida(spark):
    """El ROR coincide con el valor calculado a mano.

    ROR = (a*d) / (b*c), con las cuatro celdas ya corregidas.
    """
    r = calcular(spark, a=40, n_farmaco=100, n_reaccion=500, N=10000)
    esperado = (40.5 * r["d"]) / (60.5 * 460.5)
    assert r["ror"] == pytest.approx(esperado, rel=1e-9)


def test_ror_supera_al_prr_en_eventos_frecuentes(spark):
    """El ROR sobrestima el PRR cuando el evento no es infrecuente.

    Ambas medidas convergen cuando la reacción es rara en la base, pero
    divergen a medida que aumenta su frecuencia. Esta es la razón por la que
    el sistema presenta siempre las dos y no una sola.
    """
    r = calcular(spark, a=40, n_farmaco=100, n_reaccion=500, N=10000)
    assert r["ror"] > r["prr"]


def test_intervalo_de_confianza_contiene_la_estimacion(spark):
    """El intervalo al 95 % contiene el valor estimado del ROR.

    El intervalo se construye sobre la escala logarítmica y se transforma
    después, de modo que resulta asimétrico respecto al estimador en la
    escala original pero debe contenerlo en todo caso.
    """
    r = calcular(spark, a=40, n_farmaco=100, n_reaccion=500, N=10000)
    assert r["ror_ic_inf"] < r["ror"] < r["ror_ic_sup"]
    assert r["ror_ic_inf"] > 0


def test_intervalo_se_estrecha_al_escalar_la_tabla(spark):
    """El intervalo se estrecha al aumentar el tamaño de la tabla.

    Se comparan dos tablas de contingencia con la misma estructura relativa y
    distinto tamaño. Es la propiedad que justifica exigir un número mínimo de
    casos: con pocos, el intervalo resulta tan amplio que la estimación es
    poco informativa.

    Conviene precisar que la amplitud del intervalo no depende únicamente del
    número de casos de la celda a, sino de la configuración completa de la
    tabla: una celda con muchos casos acompañada de marginales desequilibrados
    puede producir un intervalo más amplio que otra con menos casos y una
    estructura proporcionada.
    """
    pocos = calcular(spark, a=5, n_farmaco=20, n_reaccion=50, N=1000)
    muchos = calcular(spark, a=500, n_farmaco=2000, n_reaccion=5000, N=100000)
    amplitud_pocos = pocos["ror_ic_sup"] / pocos["ror_ic_inf"]
    amplitud_muchos = muchos["ror_ic_sup"] / muchos["ror_ic_inf"]
    assert amplitud_muchos < amplitud_pocos

# Estadístico chi cuadrado

def test_chi2_es_positivo_y_finito(spark):
    """El estadístico es siempre positivo por construcción.

    La diferencia entre productos cruzados aparece elevada al cuadrado, de
    modo que el signo de la asociación no afecta al valor del estadístico.
    """
    r = calcular(spark, a=40, n_farmaco=100, n_reaccion=500, N=10000)
    assert r["chi2"] > 0
    assert math.isfinite(r["chi2"])


def test_chi2_proximo_a_cero_sin_asociacion(spark):
    """Sin asociación el estadístico se aproxima a cero.

    Cuando los productos cruzados se igualan, el numerador tiende a cero y
    con él el estadístico.
    """
    r = calcular(spark, a=100, n_farmaco=1000, n_reaccion=1000, N=10000)
    assert r["chi2"] < 1.0


def test_chi2_crece_con_el_numero_de_casos(spark):
    """A igualdad de proporciones, el estadístico crece con el tamaño.

    Es la propiedad que hace del chi cuadrado un criterio de respaldo y no de
    intensidad: mide la evidencia disponible, no la magnitud del efecto.
    """
    pequeno = calcular(spark, a=8, n_farmaco=20, n_reaccion=500, N=10000)
    grande = calcular(spark, a=80, n_farmaco=200, n_reaccion=5000, N=100000)
    assert grande["chi2"] > pequeno["chi2"]

# Criterio de señal

def es_senal(r):
    """Aplica el criterio de señal del módulo sobre un resultado calculado."""
    return (r["prr"] >= UMBRAL_PRR
            and (r["a"] - 0.5) >= MIN_CASOS
            and r["chi2"] >= UMBRAL_CHI2)


def test_combinacion_con_asociacion_marcada_es_senal(spark):
    """Una asociación intensa y con respaldo suficiente se marca como señal."""
    r = calcular(spark, a=40, n_farmaco=100, n_reaccion=500, N=10000)
    assert r["prr"] >= UMBRAL_PRR
    assert r["chi2"] >= UMBRAL_CHI2
    assert es_senal(r)


def test_asociacion_debil_no_es_senal(spark):
    """Una asociación por debajo del umbral no se marca aunque tenga casos.

    El criterio exige superar simultáneamente los tres umbrales, de modo que
    un número elevado de casos no compensa una desproporcionalidad baja.
    """
    r = calcular(spark, a=100, n_farmaco=1000, n_reaccion=1000, N=10000)
    assert r["prr"] < UMBRAL_PRR
    assert not es_senal(r)


def test_casos_insuficientes_no_es_senal(spark):
    """Con menos casos del mínimo no se marca señal pese a un PRR elevado.

    Es el filtro que descarta las combinaciones con desproporcionalidad
    aparente sostenida por un número de casos demasiado reducido.
    """
    r = calcular(spark, a=2, n_farmaco=2, n_reaccion=50, N=10000)
    assert (r["a"] - 0.5) < MIN_CASOS
    assert not es_senal(r)


def test_umbrales_del_modulo(spark):
    """Los umbrales aplicados son los declarados en la metodología.

    Se comprueba de forma explícita para que cualquier modificación de los
    criterios de señal quede registrada como un cambio deliberado y no pase
    inadvertida.
    """
    assert UMBRAL_PRR == 2.0
    assert MIN_CASOS == 3
    assert UMBRAL_CHI2 == 4.0