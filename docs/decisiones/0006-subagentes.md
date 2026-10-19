# 0006 · Subagentes con permisos mínimos, no equipos de agentes

- Fecha: 2026-10-18 · Tarea: 0.13 · Estado: aceptada

## Contexto
Se quiere un desarrollo con varios agentes especializados, no una sesión solitaria.

## Opciones
- Subagentes de Claude Code, cada uno con su responsabilidad y sus permisos.
- Equipos de agentes de Claude Code (experimentales).
- Varias sesiones a mano, sin reparto de papeles.

## Decisión
Cinco subagentes con permisos mínimos y una skill /tarea que los encadena. Varias tareas a la vez, con worktrees. Los equipos de agentes se prueban más adelante, para investigar o revisar.

## Consecuencias
Menos consumo del límite de uso compartido. Santos aprueba cada plan y hace todos los commits.
