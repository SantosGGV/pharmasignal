# PharmaSignal

Sistema de detección de señales de farmacovigilancia sobre datos FAERS (2020–2025)

![Pruebas unitarias](https://github.com/SantosGGV/pharmasignal/actions/workflows/pruebas.yml/badge.svg)

## Descripción

PharmaSignal es un sistema de análisis de datos masivos que explota la base pública de reacciones adversas
de la FDA (FAERS en el periodo 2020–2025) para detectar señales de farmacovigilancia sobre más de 146 millones de registros.
Aplica las medidas de desproporción PRR y ROR con especial foco en la dimensión geográfica,
y presenta los resultados en una interfaz para usuarios expertos y no expertos.

Es una herramienta de apoyo al profesional y no sustituye en ningún caso el criterio clínico.

## Fuente de datos

FAERS (FDA Adverse Event Reporting System), 2020–2025, vía ficheros ASCII + OpenFDA API.

## Stack

- Python 3.12 · PySpark 4.1.1 · Delta Lake 4.3.1 · Pandas 3.0.3
- Streamlit 1.59.1 · Plotly 6.9.0 · Docker
- Entorno: WSL2 Ubuntu 24.04

## Estructura del proyecto

![img_3.png](img_3.png)

## Ejecución

El sistema admite dos formas de ejecución según lo que se quiera hacer. La interfaz
puede levantarse en contenedor con datos de demostración incluidos, sin necesidad de
descargar los ficheros de origen ni ejecutar el pipeline. Reproducir el análisis
completo sobre los datos de FAERS requiere en cambio la instalación local, ya que el
procesamiento se apoya en Spark.

### Interfaz en contenedor

```bash
docker build -f docker/Dockerfile -t pharmasignal:1.0 .
docker run --rm -p 8501:8501 pharmasignal:1.0
```

La interfaz queda accesible en `http://localhost:8501`.

La imagen contiene únicamente la capa de presentación. Durante la construcción se
descargan las tablas de resultados publicadas como recurso adjunto del repositorio,
de modo que no es necesario disponer de los ficheros de origen ni haber ejecutado
previamente el pipeline. El procesamiento de datos queda fuera del contenedor porque
requiere Spark y varios gigabytes de datos.

El script `docker/preparar_demo.sh` regenera ese paquete a partir de las tablas
curadas locales, y solo resulta necesario si se quiere publicar una versión
actualizada de los datos de demostración.

### Instalación local y pipeline completo

```bash
# 1. Entorno
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Pipeline (necesario seguir este órden específico)
python src/ingesta/ingesta_faers.py
python src/curación/curar_demo.py
python src/curación/curar_drug.py
python src/curación/curar_reac.py
python src/curación/curar_outc.py
python src/curación/curar_indi.py
python src/curación/curar_ther.py
python src/curación/curar_rpsr.py
python src/curación/curar_geografia.py
python src/curación/validar_curacion.py
python src/analisis/prr_ror.py
python src/analisis/analisis_geografico.py
python src/analisis/analisis_temporal.py

# 3. Frontend
streamlit run src/app/streamlit_app.py
```

## Pruebas

```bash
pytest tests/ -v
```

Las pruebas verifican las expresiones estadísticas del módulo de detección de señales
sobre tablas de contingencia con valores conocidos. Se ejecutan automáticamente en cada
incorporación de código al repositorio.

## Nota sobre los datos

Los ficheros de FAERS quedan excluidos del repositorio mediante `.gitignore` por su
volumen (unos 9 GB descomprimidos, que generan alrededor de 6 GB de tablas curadas).
Se descargan del portal público de la FDA.

El fichero `data/integridad_faers.sha256` permite verificar que los ficheros de origen
se corresponden con los empleados en el análisis:

```bash
cd data/raw && sha256sum -c ../integridad_faers.sha256 --quiet
```

## Aviso

Una señal estadística es una hipótesis de trabajo, no una prueba de causalidad.

## Autor

Santos Gómez Gómez