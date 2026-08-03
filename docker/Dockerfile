# Imagen para la ejecución del frontend de PharmaSignal.
#
# El contenedor incluye únicamente la capa de presentación. El pipeline de
# ingesta y análisis requiere Spark y varios gigabytes de datos de origen, de
# modo que containerizarlo no aportaría un despliegue utilizable. La interfaz,
# en cambio, solo lee tablas Delta ya materializadas mediante una biblioteca
# ligera, sin necesidad de motor distribuido.
FROM python:3.12-slim

LABEL org.opencontainers.image.title="PharmaSignal"
LABEL org.opencontainers.image.description="Deteccion de senales de farmacovigilancia sobre FAERS"

WORKDIR /app

# Solo las dependencias que la interfaz utiliza realmente. Se fijan las
# versiones para que la imagen sea reproducible.
RUN pip install --no-cache-dir \
      streamlit==1.59.1 \
      deltalake==1.6.2 \
      pyarrow==24.0.0 \
      pandas==3.0.3 \
      plotly==6.9.0 \
      numpy==2.5.1

# Codigo de la aplicacion.
COPY src/app/ /app/src/app/

# Configuracion de tema de la interfaz. Sin este fichero Streamlit aplica su
# paleta por defecto, con el color primario en rojo.
COPY .streamlit/ /app/.streamlit/

# Datos de demostracion. El archivo se genera con docker/preparar_demo.sh y
# contiene las tablas de resultados necesarias para que la interfaz muestre
# contenido sin ejecutar previamente el pipeline.
# El paquete se descarga desde el repositorio en lugar de copiarse del contexto
# de construccion. De este modo la imagen puede construirse a partir de un clon
# del repositorio, sin necesidad de haber ejecutado antes el pipeline para
# generar las tablas.
ARG URL_DATOS=https://github.com/SantosGGV/pharmasignal/releases/download/datos-demo/pharmasignal-datos-demo.tar.gz

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /root/pharmasignal && \
    curl -fsSL "$URL_DATOS" -o /tmp/datos.tar.gz && \
    tar xzf /tmp/datos.tar.gz -C /root/pharmasignal && \
    rm /tmp/datos.tar.gz && \
    apt-get purge -y curl && apt-get autoremove -y

EXPOSE 8501

# La comprobacion de estado permite que un orquestador detecte si la
# aplicacion ha dejado de responder.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "src/app/streamlit_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true"]
