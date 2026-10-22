# 0008 · Las fases se declaran en config.toml, no en el código

- Fecha: 2026-10-22 · Tarea: 0.3 · Estado: aceptada

## Contexto
El lanzador tiene que saber qué script corre en cada fase y qué rutas lee y escribe. La 0.11 cambia la estructura por capas del pipeline. La regla del proyecto dice que umbrales y rutas se leen solo desde la configuración.

## Opciones
- Config: `[[lanzador.fases]]` en `config.toml`, con el script y claves de `[rutas]` en entrada y salida, no nombres de tablas. La 0.11 solo cambia configuración. Cumple la regla de umbrales y rutas solo desde config.
- Constante en el código: más simple, pero la 0.11 tendría que tocar el código del lanzador.

## Decisión
Fases en `config.toml`. Cada fase lleva `escribe_tablas`, que dice si escribe tablas. `[[lanzador.fuera]]` lista lo que no se ejecuta; hoy, `traducir_terminos.py` (ADR 0010).

## Consecuencias
- Cambiar el orden o el script de una fase es editar `config.toml`. El lanzador no cambia.
- Como las fases usan claves de `[rutas]` y no nombres de tablas, una ruta se cambia en un solo sitio.
- `escribe_tablas` decide qué fases exigen `--confirmar` sobre la base del repositorio (ADR 0011).
