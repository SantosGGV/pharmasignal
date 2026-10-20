# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Se publica una versión por fase cerrada.

## [Sin publicar]

### Añadido
- Umbrales y rutas en config.toml (0.2).
- Bitácora, decisiones (ADR) y trazabilidad de commits (0.12).
- Hooks de pre-commit: gitleaks, bandit, pip-audit, términos prohibidos, pruebas y prefijo de tarea; dependencias de desarrollo en requirements-dev.txt (0.12).
- Hooks de Claude Code: contexto al iniciar sesión y bitácora obligatoria al cerrar una tarea (0.12).
- Equipo de agentes de Claude Code: arquitecto, metodo, calidad, seguridad y documentador, con guardas de escritura y de Bash de solo lectura y la skill /tarea (0.13).

### Seguridad
- anyio 4.14.2, GitPython 3.1.60 y urllib3 2.8.0, que corrigen 10 vulnerabilidades conocidas (0.12).

## [1.0-tfb] - 2026-10-16
- Versión defendida del TFB (etiqueta v1.0-tfb).
