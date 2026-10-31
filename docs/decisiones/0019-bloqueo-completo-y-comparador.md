# 0019 · Bloqueo completo de dependencias, comprobado por un comparador, sin herramienta nueva

- Fecha: 2026-10-31 · Tarea: 0.7 · Estado: aceptada

## Contexto
La 0.7 pide que una instalación limpia dé las mismas versiones. Antes no las daba:
- `requirements.txt` tenía 58 líneas y no incluía las dependencias transitivas de deltalake. Una instalación limpia habría resuelto arro3-core 0.9.1, Deprecated 3.0.1 y wrapt 2.5.2.
- `pip-audit` marcaba 47 vulnerabilidades en `requirements.txt`, en pillow, GitPython y certifi.
- La imagen Docker fijaba 6 paquetes a mano en el Dockerfile. Certifi y GitPython salían sueltos.

## Opciones
**Forma del bloqueo (D1).**
- A) Freeze completo de `pip`, con todas las transitivas, sin herramienta nueva. Es la opción elegida.
- B) pip-tools, C) uv, D) `pip lock`. Se descartan por ahora. pip-tools con hashes se reconsidera en la 3.6.

**Comprobación (D2).**
- A) Un script comparador, `scripts/deps/comprobar_bloqueo.py`, que compara lo instalado con el bloqueo usando `importlib.metadata`. Sale con 0 si coincide, 1 si no coincide y 2 si el fichero de bloqueo es inválido. Se ejecuta en CI, en local y dentro de la imagen. Es la opción elegida.
- B) `pip freeze | diff`. Falla por la normalización de nombres.

**Imagen (D4).**
- A) `requirements-interfaz.txt`, con 39 paquetes y las mismas versiones que el bloqueo. El Dockerfile lo instala. Es la opción elegida.
- B) Seguir con pines a mano en el Dockerfile. Solo 6 paquetes quedaban fijados.

**Paquetes sin uso (D5).**
- A) Quitar los 9 paquetes sin uso en todo el repo (scikit-learn, scipy, joblib, threadpoolctl, contourpy, cycler, fonttools, kiwisolver, pyparsing). Quitar también los 8 huérfanos que dejó la subida de Streamlit. Es la opción elegida.

**Comprobación de la interfaz (D6).**
- A) 12 recorridos AppTest en `scripts/comprobar_interfaz.py`, en local y en CI dentro de la imagen. Es la opción elegida.

**Vulnerabilidad de pillow (39 avisos).**
- A) Subir Streamlit de 1.59.1 a 1.66.1. Es la primera versión que acepta pillow 13 (`pillow<14`). Pillow sube de 12.3.0 a 13.0.0. Es la opción elegida.
- B) Ignorar los 39 identificadores en `pip-audit`. Se descarta.
- Streamlit 1.59.1 exige `pillow<13`. La 12.3.0 es la última 12.x, así que sin subir Streamlit no había versión compatible que cerrara los avisos.

## Decisión
- `requirements.txt` es un bloqueo completo de 44 paquetes.
- `requirements-interfaz.txt` es el bloqueo de la imagen Docker.
- `scripts/deps/comprobar_bloqueo.py` es la comprobación. Corre en CI, en local y dentro de la imagen.
- Se suben solo los paquetes necesarios. En el bloqueo principal: certifi, pillow (con Streamlit) y GitPython, que después sale del bloqueo porque Streamlit 1.66.1 ya no lo pide. En el de traducción: filelock y setuptools. La lista completa, con el motivo de cada subida, está en la bitácora.
- Las pruebas de AppTest se lanzan como script, en local y en CI dentro de la imagen.

## Consecuencias
- Una instalación limpia de `requirements.txt` da exactamente las 44 versiones del bloqueo. Verificado.
- `pip-audit` sobre `requirements.txt`: 47 vulnerabilidades → 0.
- Subir una versión exige regenerar el bloqueo y pasar el comparador. El comparador falla si algo no coincide.
- La imagen se instala desde `requirements-interfaz.txt`. El comparador dentro de la imagen coincide.
- El `.venv` principal conserva paquetes fuera del bloqueo (matplotlib, torch y los 9 retirados). No afectan a la comprobación de instalación limpia.
- Quedan para la 3.6, como opcionales: `--require-hashes`, pip-tools con hashes, digest de la imagen base y usuario no root en Docker.
- El argostranslate y la excepción de stanza están en el [ADR 0020](0020-argostranslate-venv-aparte.md).
