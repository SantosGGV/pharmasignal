---
name: cerrar
description: "Cierra cualquier sesión de PharmaSignal, sea o no de una tarea: entrada de bitácora con el documentador y mensaje de Cierre, que se guarda en la carpeta privada. Se lanza con /cerrar."
argument-hint: "[tema corto de la sesión, opcional]"
disable-model-invocation: true
---
# Cierre de la sesión

Sigue estos pasos en orden.

1. **Qué cambió.** Mira la rama, `git status` y `git diff --stat`, y los commits de la sesión. Si el inicio de sesión avisó de un rastro pendiente en `$PHARMASIGNAL_PRIVADO/sesiones/`, léelo también.
2. **Si no hay cambios en ficheros**, pregunta a Santos qué se hizo en la sesión: una release, una reconstrucción lanzada por él, una decisión u otra cosa. Si no hubo nada que contar, salta al paso 4 y di que no hay entrada.
3. **Documentación.** Siempre que haya algo que contar, delega en documentador y pásale la fecha de hoy, el id de la tarea si la rama es `faseN/<id>-<nombre>` (si no, el tema: $ARGUMENTS o uno corto que propongas), el resumen de lo hecho, las pruebas y las cifras de antes y después (si no se midieron, dilo), las decisiones y la salida de `git diff --stat`. La entrada es `docs/bitacora/AAAA-MM-DD_<id>-<tema>.md` en una rama de tarea y `docs/bitacora/AAAA-MM-DD_sesion-<tema>.md` fuera de ella. Si la rama es de tarea y la tarea no ha terminado, la entrada lo dice y deja lo pendiente.
4. **Cierre.** Termina con un mensaje que empiece exactamente por «## Cierre de la sesión» (o «## Cierre de la sesión <id>» en una rama de tarea), sin nada delante, con: qué se hizo, pruebas, cifras de antes y después, lo pendiente, el mensaje de commit propuesto si hay cambios y un recordatorio para que Santos apunte sus horas en su registro privado. El hook guardar_cierre.py lo guarda tal cual en `$PHARMASIGNAL_PRIVADO/cierres/`. No hagas commit: lo hace Santos.
