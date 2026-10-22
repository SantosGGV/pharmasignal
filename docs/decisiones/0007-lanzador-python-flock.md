# 0007 · El lanzador es Python con fcntl.flock, no bash con flock

- Fecha: 2026-10-22 · Tarea: 0.3 · Estado: aceptada

## Contexto
El pipeline se puede relanzar desde cualquier fase, y no deben correr dos a la vez. El lanzador necesita leer `config.toml`, gestionar señales y devolver códigos de salida distintos según el caso.

## Opciones
- Python, en `src/lanzador.py`. Lee `config.toml` con `tomllib` a través de `src/config.py`. Las pruebas van con pytest. Bandit lo revisa. Gestiona señales y códigos de salida.
- Bash con `/usr/bin/flock`. Es más corto, pero leer TOML desde bash es frágil, las pruebas son peores y bandit no lo cubre.

## Decisión
Python con `fcntl.flock`.

## Consecuencias
- Las pruebas del lanzador son de pytest: 35 en `tests/test_lanzador.py`, con scripts falsos.
- Bandit revisa `src/lanzador.py`.
- `fcntl` solo existe en sistemas tipo Unix. El proyecto corre en WSL2, así que no hay problema.
