---
name: tarea
description: "Lleva una tarea de la hoja de ruta de PharmaSignal de principio a fin con el equipo de agentes. Se lanza con /tarea <id>."
argument-hint: "[id de la tarea, por ejemplo 0.3]"
disable-model-invocation: true
---
# Tarea $ARGUMENTS

Sigue estos pasos en orden, sin saltarte ninguno.

1. **Contexto.** Lee la fila de la tarea $ARGUMENTS en la hoja de ruta privada (su ruta absoluta está en el contexto de inicio de sesión): entregable, prioridad, esfuerzo y «hecho cuando». Lee también lo pendiente de la última entrada de docs/bitacora.
2. **Rama.** Tienes que estar en faseN/$ARGUMENTS-<nombre>. Si no existe, propón el nombre y créala cuando Santos diga que sí. Nunca trabajes en main.
3. **Plan.** Delega en el subagente arquitecto y pásale la fila de la tarea tal cual, lo pendiente de la bitácora y lo que haya dicho Santos. Enseña su plan tal cual y espera el «sí» explícito de Santos: sin él no se edita nada. Si pide cambios, vuelve al arquitecto. En las tareas solo de documentación o de menos de 2 h, el plan lo haces tú, corto y con el mismo formato, sin arquitecto.
4. **Implementación.** En esta sesión, paso a paso, con `pytest tests/ -v` después de cada paso. Avisa antes de lanzar Spark y nunca lances dos ejecuciones a la vez. Si la tarea puede mover cifras de señales, ejecuta validar_senales.py antes y después (solo si no lanza una fase completa de Spark) y guarda el diff de outputs/validacion_senales.csv.
5. **Revisión en paralelo.** seguridad, siempre; calidad, si cambia código o configuración; metodo, si cambian src/analisis, los umbrales de config.toml, tests/test_prr_ror.py o cifras de señales. A cada uno pásale el id, el objetivo del plan y la salida de `git diff --stat`; a metodo, también el antes y el después de validar_senales.py. Corrige lo que marquen como «hay que arreglar sí o sí» y vuelve a pasar solo al revisor que lo marcó. Si tras dos vueltas sigue habiendo algo, para y pregunta a Santos.
6. **Documentación.** Delega en documentador y pásale la fecha de hoy, el id, el resumen de lo hecho, las pruebas, las cifras de antes y después, las decisiones del arquitecto y la salida de `git diff --stat`.
7. **Cierre.** Termina con un mensaje que empiece por «## Cierre de la tarea $ARGUMENTS» con: qué cambió, pruebas, cifras de antes y después, lo opcional que dejan los revisores, el mensaje de commit propuesto y un recordatorio para que Santos apunte sus horas en su registro privado. No hagas commit: lo hace Santos.
