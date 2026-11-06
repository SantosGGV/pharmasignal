# 0023 · Criterio en un único documento, con prueba contra config.toml

- Fecha: 2026-11-06 · Tarea: 0.8 · Estado: aceptada

## Contexto
El criterio que afecta a las cifras estaba repartido entre el README, CLAUDE.md, los comentarios del código y el agente de método. Los textos discrepaban entre sí.

## Opciones
- A) Documento único `docs/criterio.md`, más una prueba (`tests/test_criterio.py`) que compara sus valores con `config.toml`. Es la opción elegida.
- B) Mantener el criterio en cada documento. Se descarta: es lo que produjo las discrepancias.
- C) Generar la tabla de valores desde `config.toml`. Se descarta: añade herramientas a una tarea de documentación.

## Decisión
El criterio vive en `docs/criterio.md`. El README, CLAUDE.md y los agentes enlazan a ese documento y no copian el criterio.

La prueba falla si la tabla de valores y `config.toml` dejan de coincidir.

## Consecuencias
- Un cambio de umbral en `config.toml` obliga a actualizar `docs/criterio.md`, o falla `tests/test_criterio.py`.
- La prueba compara valores. No comprueba las reglas escritas en prosa ni los multiplicadores del código, por ejemplo el valor por 3 y por 5 de los listados.
- Los fallos que el documento reconoce van en «Fallos conocidos», cada uno con su destino. No se corrigen en la 0.8, porque cambiar el criterio cambia las cifras.
- Si el código y el documento discrepan, manda el código y se corrige el documento.
