# 0013 · Las tablas pasan a tres capas con un traslado de un solo uso, no con una base reconstruida

- Fecha: 2026-10-22 · Tarea: 0.11 · Estado: aceptada

## Contexto
Las 40 tablas estaban juntas en `data/curated`. Cada fase tenía que saber en qué carpeta escribir, y la 0.3 necesitaba que cada fase se relanzara desde su capa. Había que mover las tablas que ya existen en la base del repositorio.

## Opciones
- A) Un script de traslado (`src/migrar_capas.py`) que mueve las carpetas con `os.rename`. Es instantáneo, no ocupa espacio extra y conserva el historial Delta (la versión 7 de `senales_prr_ror`). Es reversible.
- B) Sustituir la base por la reconstruida desde cero. La interfaz queda rota hasta reconstruir, el espacio se duplica y se pierde el historial Delta.

## Decisión
Opción A, con estas garantías:
- Lista por defecto. Mueve solo con `--confirmar`.
- Coge el candado del lanzador. Si está ocupado, sale con código 75.
- Nunca pisa, copia ni borra.
- Es reanudable. Si se interrumpe, sale con código 130.
- `--revertir` devuelve las tablas con las mismas garantías.
- `_tmp_expl_cruce` nunca se mueve.
- Una tabla fuera del reparto, o un destino en otro disco, detiene el traslado con código 2 sin mover nada.

## Consecuencias
- `[rutas] curated` queda solo para `migrar_capas.py`. Se retira en la 0.9, con `data/curated` vacía y el sí de Santos.
- El traslado real lo lanzó Santos en la base del repositorio: 7, 9 y 24 tablas en sus capas, y `data/curated` vacía.
- La reconstrucción completa sigue siendo la prueba de que el pipeline sale desde cero (ADR 0011). Se hace aparte.
