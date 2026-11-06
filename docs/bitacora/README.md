# Bitácora de PharmaSignal

Una entrada por sesión de trabajo, la más reciente arriba. Plantilla: [PLANTILLA.md](PLANTILLA.md). Las decisiones con alternativas están en [docs/decisiones](../decisiones/).

| Fecha | Tarea | Resumen | Entrada |
| --- | --- | --- | --- |
| 2026-11-06 | 0.10 | Licencia AGPL-3.0-only con `LICENSE`, avisos de terceros generados sin instalar nada y enlaces de licencia en el pie de la interfaz; 282 pruebas en verde (antes 237) y ADR 0022 | [2026-11-06_0.10-licencia.md](2026-11-06_0.10-licencia.md) |
| 2026-11-03 | 0.9 (cierre) | Historial reescrito sin `.venv`: pack de 645 MB a 2,3 MiB y gitleaks de 2 hallazgos a 0, con el mismo árbol en cada etiqueta; 237 pruebas en verde (antes 229) y ADR 0021 ejecutado | [2026-11-03_0.9-reescritura.md](2026-11-03_0.9-reescritura.md) |
| 2026-11-02 | 0.9 (parte 1) | Inventario del historial, `.gitignore` sin líneas repetidas, prueba de repo limpio y retirada de `curated` y `migrar_capas`; 229 pruebas al final (antes 247) y ADR 0021 para reescribir el historial, paso 8 pendiente | [2026-11-02_0.9-repo-limpio.md](2026-11-02_0.9-repo-limpio.md) |
| 2026-10-31 | 0.7 | Dependencias con bloqueo completo de 44 paquetes, pip-audit de `requirements.txt` de 47 vulnerabilidades a 0, imagen desde `requirements-interfaz.txt` y traducción en venv aparte; 247 pruebas en verde (antes 226) y ADR 0019 y 0020 | [2026-10-31_0.7-dependencias.md](2026-10-31_0.7-dependencias.md) |
| 2026-10-31 | 0.13 (ampliación) | Comprobaciones en vivo: rastro, marca y aviso de sesión sin bitácora pasan; bloqueo de horas a medias y hook pendiente de OK; sin cambios de código | [2026-10-31_0.13-comprobaciones-en-vivo.md](2026-10-31_0.13-comprobaciones-en-vivo.md) |
| 2026-10-24 | 0.13 (ampliación) | Rastro automático de cada sesión con git y sin IA, `/cerrar` con Cierre guardado por hook y pruebas con `pytest -q`; 226 pruebas en verde (antes 188) y 3 ADR (0016 a 0018) | [2026-10-24_0.13-ampliacion.md](2026-10-24_0.13-ampliacion.md) |
| 2026-10-24 | 0.3 y 0.11 | Reconstrucción completa desde cero en base aparte con código 0; las cuatro cifras del «hecho cuando» coinciden y las 33 tablas de plata y oro, iguales; cierra la 0.3 y la 0.11 | [2026-10-24_0.11-reconstruccion.md](2026-10-24_0.11-reconstruccion.md) |
| 2026-10-22 | 0.11 | Tablas en tres capas (bronce, plata y oro) con traslado reversible, paquete de demo v2 de 61 MB y 188 pruebas en verde; falta la reconstrucción completa | [2026-10-22_0.11-capas.md](2026-10-22_0.11-capas.md) |
| 2026-10-22 | 0.3 | Orden `todo` y `--desde`/`--solo` con candado `flock` global y logs por fase; 154 pruebas en verde; revisiones terminadas, falta el commit y la reconstrucción tras la 0.11 | [2026-10-22_0.3-orden.md](2026-10-22_0.3-orden.md) |
| 2026-10-20 | 0.13 | Cinco subagentes con permisos mínimos, guardas `solo_en.py` y `solo_lectura.py` y skill `/tarea`; 115 pruebas en verde | [2026-10-20_0.13-agentes.md](2026-10-20_0.13-agentes.md) |
| 2026-10-19 | 0.12 | Bitácora, ADR, CHANGELOG, hooks de Claude Code y de pre-commit; 31 pruebas en verde y 10 vulnerabilidades de dependencias corregidas | [2026-10-19_0.12-bitacora.md](2026-10-19_0.12-bitacora.md) |
| 2026-10-19 | 0.2 | Umbrales y rutas de 23 scripts en `config.toml`, leído con `src/config.py`; mismos resultados y 17 pruebas en verde | [2026-10-19_0.2-config.md](2026-10-19_0.2-config.md) |
