# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Se publica una versión por fase cerrada.

## [Sin publicar]

### Añadido
- Umbrales y rutas en config.toml (0.2).
- Bitácora, decisiones (ADR) y trazabilidad de commits (0.12).
- Hooks de pre-commit: gitleaks, bandit, pip-audit, términos prohibidos, pruebas y prefijo de tarea; dependencias de desarrollo en requirements-dev.txt (0.12).
- Hooks de Claude Code: contexto al iniciar sesión y bitácora obligatoria al cerrar una tarea (0.12).
- Equipo de agentes de Claude Code: arquitecto, metodo, calidad, seguridad y documentador, con guardas de escritura y de Bash de solo lectura y la skill /tarea (0.13).
- Lanzador del pipeline `src/lanzador.py` con los modos `todo`, `--desde`, `--solo`, `--lista` y `--confirmar`; candado `flock` global, logs por fase en `outputs/logs/` y comprobaciones previas (0.3).
- Sección `[lanzador]` y fases en `config.toml`, leídas desde `src/config.py` (0.3).

### Cambiado
- Los comandos del pipeline se lanzan con el lanzador, según CLAUDE.md (0.3).

### Seguridad
- anyio 4.14.2, GitPython 3.1.60 y urllib3 2.8.0, que corrigen 10 vulnerabilidades conocidas (0.12).
- Candado del lanzador con `O_NOFOLLOW` y comprobación de dueño, tipo y permisos de fichero y carpeta; si falla, código 2 (0.3).
- Logs del lanzador con permisos 0600 (0.3).

## [1.0-tfb] - 2026-10-16
- Versión defendida del TFB (etiqueta v1.0-tfb).
