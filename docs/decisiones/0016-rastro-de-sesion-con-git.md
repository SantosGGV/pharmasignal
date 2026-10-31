# 0016 · El rastro de cada sesión sale de git, comparado con un estado guardado al empezar

- Fecha: 2026-10-24 · Tarea: 0.13 · Estado: aceptada

## Contexto
Cada sesión debe dejar escrito qué tocó. Si la regla depende de acordarse, falla. Hace falta un registro que se escriba solo. ¿Cómo saber, sin IA, qué cambió una sesión, incluidas las ediciones a mano y los commits?

## Opciones
- A) git. Al empezar se guarda el HEAD y los ficheros ya sucios, con su hash. Al salir se compara y se listan los commits y los ficheros tocados. Es determinista. Ve también lo que se edita a mano.
- B) Leer `transcript_path`. Es un formato interno de Claude Code. No ve los commits ni lo que se escribe desde Bash.
- C) Solo `git status` al final. Mezcla lo que ya estaba sucio antes de la sesión y no ve los commits.

## Decisión
Opción A. El estado al empezar separa lo que ya estaba sucio de lo que tocó la sesión.

## Consecuencias
- El rastro es reproducible y no gasta tokens.
- Escribe en `$PHARMASIGNAL_PRIVADO/sesiones/`. Si la carpeta privada no está definida o está dentro del repo, no escribe nada.
- Si la sesión cambia de rama, el rastro mezcla commits y ficheros de ambas ramas. Registra la rama de inicio y la de fin. Queda como pendiente opcional.
- Las sesiones cortadas a la fuerza se cierran como «sesión sin cierre» cuando arranca otra, si llevan más de 24 h sin salida.
