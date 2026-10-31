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
- Rastro automático de cada sesión, sin IA: `.claude/hooks/rastro_sesion.py` guarda el estado al empezar y escribe el rastro al salir en la carpeta privada. Avisa si una sesión tocó algo fuera de `docs/` sin entrada de bitácora (0.13).
- Skill `/cerrar` para cualquier sesión, y hook `.claude/hooks/guardar_cierre.py` que guarda el Cierre de la tarea o de la sesión en la carpeta privada (0.13).
- Pruebas de rastro, cierre y casos límite en `tests/test_hooks_sesion.py` y `tests/test_hooks_sesion_limites.py` (0.13).
- `scripts/git/pruebas.sh` pone el `.venv` en el PATH antes de lanzar pytest, para que los scripts que lanzan pruebas usen su Python (0.13).
- Decisiones 0016 (rastro con git), 0017 (horas en CSV privado) y 0018 (Cierre por hook Stop) (0.13).

### Cambiado
- Los comandos del pipeline se lanzan con el lanzador, según CLAUDE.md (0.3).
- Las pruebas locales se lanzan con `pytest tests/ -q`. El CI sigue con `-v` (0.13).
- `exigir_bitacora.py` reconoce el cierre de sesión solo si el mensaje empieza por la marca (0.13).
- `bandit` revisa también `.claude/hooks/`, y el hook de pruebas de pre-commit salta con cualquier cambio en `.claude/` (0.13).
- La regla de horas separa las horas de trabajo, que no se escriben, de los tiempos de ejecución, los permisos y las versiones, que sí (0.13).
- Cada fase del lanzador escribe en su capa: ingesta de raw a bronce, curación de bronce a plata, análisis de plata a oro y control de oro a `outputs/` (0.11).
- La interfaz lee las tablas de oro, y `trad_terminos` de plata (0.11).
- La imagen Docker descarga `datos-demo-v2`. `datos-demo` se mantiene para la imagen `v1.0-tfb` (0.11).
- `.gitignore` y `.dockerignore` ignoran `data/bronce`, `data/plata` y `data/oro` (0.11).

### Seguridad
- anyio 4.14.2, GitPython 3.1.60 y urllib3 2.8.0, que corrigen 10 vulnerabilidades conocidas (0.12).
- Candado del lanzador con `O_NOFOLLOW` y comprobación de dueño, tipo y permisos de fichero y carpeta; si falla, código 2 (0.3).
- Logs del lanzador con permisos 0600 (0.3).
- El paquete de demo no lleva rutas personales ni nombres de usuario en el registro Delta, y todos sus ficheros pertenecen a 0:0 (0.11).
- El CSV de horas de sesión está en la carpeta privada, con permisos 0600 y solo se añaden líneas. Read y Edit están denegados a Claude, y los agentes revisores no pueden leerlo (0.13).

## [1.0-tfb] - 2026-10-16
- Versión defendida del TFB (etiqueta v1.0-tfb).
