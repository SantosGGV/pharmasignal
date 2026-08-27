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

## Manual de usuario

El manual completo de la herramienta está disponible en:
[`docs/manual_usuario.pdf`](docs/Manual%20de%20Usuario%20-%20PharmaSignal%20-%20Santos_G.pdf)

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
python src/curacion/curar_demo.py
python src/curacion/curar_drug.py
python src/curacion/curar_reac.py
python src/curacion/curar_outc.py
python src/curacion/curar_indi.py
python src/curacion/curar_ther.py
python src/curacion/curar_rpsr.py
python src/curacion/curar_geografia.py
python src/curacion/validar_curacion.py
python src/analisis/prr_ror.py
python src/analisis/analisis_geografico.py
python src/analisis/analisis_temporal.py
python src/analisis/analisis_explorador.py
python src/analisis/analisis_explorador_cruces.py

# 3. Frontend
streamlit run src/app/streamlit_app.py
```

## Solución de problemas

Estos son los fallos que han aparecido al desplegar el sistema, separados según cómo
se instale.

### 1. Instalación a través de interfaz en contenedor Docker

#### La interfaz muestra datos que no son los de la última publicación

La instrucción del Dockerfile no cambia aunque el recurso adjunto sí, así que Docker
sirve la capa de descarga desde su caché.

```bash
docker build --no-cache -f docker/Dockerfile -t pharmasignal:1.0 .
```

#### La construcción tarda demasiado o llena el disco

El contexto de construcción está arrastrando el directorio `data/`. Se ve en la
primera línea del build, que dice cuántos datos se envían al demonio: si son más de
unos pocos MB, el fichero de exclusión no se está aplicando. Tiene que estar en la
raíz del contexto y no dentro de `docker/`.

```bash
ls -la .dockerignore
docker build -f docker/Dockerfile -t pharmasignal:1.0 .
# Sending build context to Docker daemon  <pocos MB>
```

#### La construcción falla al descargar el paquete de datos de demostración

El adjunto de la release se ha renombrado o no está accesible.

```bash
curl -sIL <url_del_adjunto> | head -n 1   # debe devolver 200
```

#### La interfaz no responde en http://localhost:8501

Otro proceso ocupa el puerto.

```bash
ss -tlnp | grep 8501
docker run --rm -p 8600:8501 pharmasignal:1.0
```

### 2. Instalación local

#### El proceso muere sin excepción ni traza de Python

`pyarrow` 25.0.0 y `deltalake` 1.6.2 no son compatibles y el intérprete recibe
SIGSEGV dentro del código nativo de Arrow. No aparece ningún mensaje: lo que lo
confirma es el código de salida 139.

```bash
echo $?
pip install "pyarrow==24.0.0" --force-reinstall
python -c "import pyarrow; print(pyarrow.__version__)"
```

#### Se agota la memoria durante el análisis geográfico

WSL2 reparte por defecto alrededor de la mitad de la RAM del equipo, y el pipeline
llega a consumir 15,71 GB. Hay que editar `C:\Users\<usuario>\.wslconfig` en Windows:

```ini
[wsl2]
memory=20GB
processors=12
```

Después, `wsl --shutdown` desde PowerShell y comprobar la memoria disponible:

```bash
free -g
```

No lances dos fases del pipeline a la vez. Dos sesiones de Spark simultáneas no caben.

#### El motor de procesamiento no arranca

Falta el JDK o `JAVA_HOME` no está definida.

```bash
sudo apt install openjdk-17-jdk
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
java -version
```

#### Error de ruta inexistente en el almacén de datos

Has lanzado una fase antes que la que genera su tabla de entrada. El orden del
apartado de ejecución no es orientativo sino obligatorio.

```bash
ls data/curated/
```

#### El script de preparación de datos falla con `bad interpreter: /bin/bash^M`

El repositorio se clonó en Windows y los finales de línea son CRLF.

```bash
git config core.autocrlf false
git rm --cached -r . && git reset --hard
```

#### La verificación de integridad no encuentra el fichero de sumas

Las rutas del fichero son relativas a `data/raw`, así que el comando solo funciona
ejecutado desde ahí.

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