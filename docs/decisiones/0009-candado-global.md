# 0009 · Un candado para toda la máquina en ~/.cache/pharmasignal/pipeline.lock

- Fecha: 2026-10-22 · Tarea: 0.3 · Estado: aceptada

## Contexto
Spark arranca con un driver de 16 g y la máquina tiene 24 GB. Dos Spark a la vez no caben en memoria, aunque trabajen sobre bases o worktrees distintos. El candado tiene que proteger la memoria, no solo una base.

## Opciones
- Global, uno para toda la máquina. Protege la memoria. Es la opción elegida.
- Uno por base. Permitiría dos Spark a la vez en bases distintas.
- En `/tmp`. Se borra al reiniciar y cualquier usuario puede escribir en él.

## Decisión
Candado global en `~/.cache/pharmasignal/pipeline.lock`, con `fcntl.flock`.

## Consecuencias
- El fichero no se borra nunca.
- El núcleo suelta el candado cuando muere el proceso que lo tiene.
- El script hijo hereda el candado. Si se mata al lanzador con `kill -9`, el candado sigue cogido hasta que acaba el script hijo.
- El fichero se abre con `O_NOFOLLOW`. Se comprueba que fichero y carpeta son del usuario actual y que no tienen permisos para otros. Si no, el lanzador sale con código 2 («candado inseguro»).
- Los scripts lanzados a mano fuera del lanzador no cogen el candado.
