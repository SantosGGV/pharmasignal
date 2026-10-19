# 0002 · Interfaz definitiva: web estática con DuckDB-WASM, en dos pasos

- Fecha: 2026-10-18 · Tarea: 2.9 y 3.9 · Estado: aceptada

## Contexto
Streamlit sirve de prototipo, pero se queda corto para un producto público y necesita un servidor.

## Opciones
- Streamlit con servidor.
- API (FastAPI) y una web aparte.
- Web estática que consulta las tablas oro en Parquet desde el navegador.

## Decisión
Web estática con DuckDB-WASM. Se analiza a fondo al final de la Fase 2 (2.9), cuando el triaje ya está asentado, y se construye en la Fase 3 (3.9).

## Consecuencias
Sin servidor ni coste. El tamaño de los datos publicados queda acotado. Streamlit sigue como prototipo interno hasta la 3.9.
