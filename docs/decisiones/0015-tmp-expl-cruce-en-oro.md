# 0015 · La tabla temporal _tmp_expl_cruce vive en data/oro

- Fecha: 2026-10-22 · Tarea: 0.11 · Estado: aceptada

## Contexto
`analisis_explorador_cruces.py` escribe una tabla temporal, `_tmp_expl_cruce`, antes de dejarla en su sitio final. Con las capas, ¿dónde debe vivir esa temporal?

## Opciones
- A) `data/oro/_tmp_expl_cruce`. Es el cambio mínimo: queda en el mismo disco y Git la ignora. Si el script falla, deja restos en oro. La interfaz no los lee, porque carga las tablas por nombre.
- B) Una clave nueva en `[rutas]` para la temporal. Añade configuración para un caso de un solo script.
- C) La carpeta temporal del sistema. Puede caer en otro disco, y el `rename` final dejaría de ser instantáneo.

## Decisión
Opción A.

## Consecuencias
- `_tmp_expl_cruce` no se mueve en el traslado (ADR 0013).
- Si `analisis_explorador_cruces.py` falla, pueden quedar restos en `data/oro`. La reconstrucción cuenta 24 tablas en oro sin `_tmp_expl_cruce`.
- El comentario «No forma parte de la capa curada» de `analisis_explorador_cruces.py:80-82` ha quedado algo desfasado. No se toca, por la regla de comentarios.
