# 0011 · La reconstrucción va en una base aparte, con data/raw copiado y verificado

- Fecha: 2026-10-22 · Tarea: 0.3 · Estado: aceptada

## Contexto
Reconstruir desde cero escribe tablas. La base del repositorio no debe cambiar sin querer. El espacio que cuenta es el libre del disco de Windows (`/mnt/c`). Los 920 GB que muestra WSL son el tamaño máximo del disco virtual, no espacio real. Hoy hay 225 GB libres de 476 GB.

## Opciones
- Copiar `data/raw` a la base aparte y verificarlo con `sha256sum -c`. Es la opción elegida.
- Enlace simbólico a `data/raw`. No ocupa espacio, pero deja el original expuesto a un error de ruta.

## Decisión
Reconstrucción en una base aparte, indicada con `PHARMASIGNAL_BASE`. `data/raw` se copia y se verifica antes de lanzar.

## Consecuencias
- Sobre la base del repositorio, toda fase con `escribe_tablas = true` exige `--confirmar`.
- Antes de lanzar, se mira el espacio libre de `/mnt/c`. El lanzador también lo mide (`discos_extra` en `config.toml`) y exige `espacio_min_gb` en el disco con menos libre.
- La reconstrucción completa se hace una sola vez, tras fusionar la 0.11. Esa ejecución cierra la 0.3 y la 0.11.
- La lanza Santos en una terminal.
