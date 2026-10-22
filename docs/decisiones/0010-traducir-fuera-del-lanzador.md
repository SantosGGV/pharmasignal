# 0010 · traducir_terminos.py queda fuera del lanzador hasta la 0.7

- Fecha: 2026-10-22 · Tarea: 0.3 · Estado: aceptada

## Contexto
`traducir_terminos.py` usa argostranslate. Ese paquete no está en `requirements.txt`. Sus modelos se descargan de una fuente que no está en la lista de fuentes permitidas.

## Opciones
- Incluirlo ya en el lanzador. Obliga a añadir una dependencia y una fuente que hoy no están permitidas.
- Dejarlo fuera de la orden hasta la 0.7. Es la opción elegida.

## Decisión
`traducir_terminos.py` queda en `[[lanzador.fuera]]` de `config.toml` hasta la 0.7.

## Consecuencias
- `--lista` avisa de que el script queda fuera.
- Tras reconstruir en una base aparte, la tabla `trad_terminos` se copia desde la base actual.
- No afecta a las cuatro cifras de referencia (ADR 0012).
