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
- Tres capas de tablas en `data/`: bronce (7 tablas), plata (9) y oro (24), con rutas en `config.toml` y `src/config.py` (0.11).
- `src/migrar_capas.py`: traslado de un solo uso de las tablas de `data/curated` a las capas, con `--confirmar` y `--revertir`; mueve con `os.rename` y nunca pisa ni borra (0.11).
- Paquete de demo `datos-demo-v2`, con solo la versión vigente de cada tabla Delta, y `docker/preparar_demo.sh` con comprobación final (0.11).
- Hook `check-added-large-files` de pre-commit, con límite de 1 MB para ficheros nuevos (0.11).
- Pruebas de capas, traslado y paquete de demo en `tests/test_capas.py` (0.11).

### Cambiado
- Los comandos del pipeline se lanzan con el lanzador, según CLAUDE.md (0.3).
- Cada fase del lanzador escribe en su capa: ingesta de raw a bronce, curación de bronce a plata, análisis de plata a oro y control de oro a `outputs/` (0.11).
- La interfaz lee las tablas de oro, y `trad_terminos` de plata (0.11).
- La imagen Docker descarga `datos-demo-v2`. `datos-demo` se mantiene para la imagen `v1.0-tfb` (0.11).
- `.gitignore` y `.dockerignore` ignoran `data/bronce`, `data/plata` y `data/oro` (0.11).

### Seguridad
- anyio 4.14.2, GitPython 3.1.60 y urllib3 2.8.0, que corrigen 10 vulnerabilidades conocidas (0.12).
- Candado del lanzador con `O_NOFOLLOW` y comprobación de dueño, tipo y permisos de fichero y carpeta; si falla, código 2 (0.3).
- Logs del lanzador con permisos 0600 (0.3).
- El paquete de demo no lleva rutas personales ni nombres de usuario en el registro Delta, y todos sus ficheros pertenecen a 0:0 (0.11).

## [1.0-tfb] - 2026-10-16
- Versión defendida del TFB (etiqueta v1.0-tfb).
