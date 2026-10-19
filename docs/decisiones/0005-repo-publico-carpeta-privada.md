# 0005 · Repositorio público, carpeta privada

- Fecha: 2026-10-18 · Tarea: 0.12 · Estado: aceptada

## Contexto
El repositorio es público y la bitácora se va a enseñar.

## Opciones
- Versionar todo, también la planificación y las horas.
- Versionar solo lo técnico y guardar lo personal fuera del repositorio.

## Decisión
En el repositorio, solo lo técnico. La hoja de ruta, la lista de términos prohibidos y las horas viven en $PHARMASIGNAL_PRIVADO, fuera del repo. Un hook de pre-commit bloquea los términos de esa lista.

## Consecuencias
La bitácora se puede publicar tal cual. Las horas se apuntan aparte, en el registro privado.
