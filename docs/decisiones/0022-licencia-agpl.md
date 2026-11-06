# 0022 · Licencia AGPL-3.0-only para el código

- Fecha: 2026-11-06 · Tarea: 0.10 · Estado: aceptada

## Contexto
El repositorio no tenía fichero de licencia ni avisos de licencias de terceros. La interfaz de PharmaSignal se sirve por red con Streamlit. Quien ejecuta una versión modificada la ofrece a otros por red, así que la licencia debe cubrir ese uso.

## Opciones
- A) AGPL-3.0-only. Es la opción elegida.
- B) Apache-2.0. Se descarta. Permite cerrar una versión modificada, y la AGPL no.

## Decisión
Licencia AGPL-3.0-only para el código del repositorio. Titular: Santos Gómez Gómez, 2026.

Motivo: que cualquier versión modificada que se ofrezca como servicio siga siendo abierta.

## Consecuencias
- La interfaz enseña, en el pie de la barra lateral, enlaces al código y a la licencia, en español e inglés. Se pintan antes de ejecutar la vista, para que salgan aunque una vista falle.
- `LICENSE` es el texto oficial de la AGPL-3.0, sin tocar. Se descargó de https://www.gnu.org/licenses/agpl-3.0.txt el 2026-11-06. Su sha256 es `0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`. Como no se toca, el titular y el «-only» constan en el README y en el pie.
- La licencia cubre solo el código. Los paquetes y los datos de terceros se rigen por sus propias condiciones, recogidas en `THIRD_PARTY_NOTICES.md`.
- No hay fichero NOTICE.
- La imagen Docker lleva `LICENSE` y `THIRD_PARTY_NOTICES.md`.

## Decisión adicional: paquetes CUDA de NVIDIA
Esta decisión va aparte de la licencia del código.

Los paquetes CUDA de NVIDIA del bloqueo de traducción (`requirements-traduccion.txt`) tienen licencia propietaria de NVIDIA. No impiden la licencia del código. Ese entorno es opcional y no se distribuye: ni en la imagen Docker ni en el repositorio.

`cuda-toolkit` no declara licencia en sus metadatos. Figura como «no declarada» en la tabla de NVIDIA de `THIRD_PARTY_NOTICES.md`.
