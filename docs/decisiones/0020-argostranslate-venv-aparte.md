# 0020 · argostranslate va en un venv aparte, y stanza 1.10.1 queda como excepción aceptada

- Fecha: 2026-10-31 · Tarea: 0.7 · Estado: aceptada. Sustituye al [ADR 0010](0010-traducir-fuera-del-lanzador.md).

## Contexto
`src/curacion/traducir_terminos.py` usa argostranslate. El [ADR 0010](0010-traducir-fuera-del-lanzador.md) lo dejó fuera del lanzador hasta la 0.7, porque sus modelos se descargan de una fuente que no está en la lista de fuentes permitidas.

Problemas al añadirlo al bloqueo principal:
- argostranslate 1.11.0, la última (2026-02-02), fija `stanza==1.10.1`. Con eso, `pip check` falla en el `.venv` (1 conflicto).
- Trae torch, que no forma parte del bloqueo de la interfaz.
- stanza 1.10.1 tiene el aviso PYSEC-2026-3075: carga insegura de checkpoints `.pt` de PyTorch. `torch.load` tiene un respaldo con `weights_only=False`. El paquete de idioma en_es instalado carga sus `.pt` de stanza en el modo por defecto.

## Opciones
**Dónde va argostranslate.**
- A) `requirements-traduccion.txt` (89 paquetes), instalado en un venv aparte, `.venv-traduccion`. Es la opción elegida.
- B) `requirements.txt`. `pip check` queda en rojo, entra torch y choca con la regla de red del proyecto.
- C) Retirar el script de traducción.

**Qué hacer con el aviso de stanza.**
- A) Dejarlo como excepción aceptada en `pip-audit`, solo para el bloque de traducción, con un análisis de riesgo y una mitigación. Es la opción elegida.
- B) Retirar la traducción. Se descarta: la 3.1 traerá términos nuevos que hay que traducir.
- C) Forzar MiniSBD. Se descarta: descarga desde otra fuente no permitida y obliga a volver a traducir.

## Decisión
- `requirements-traduccion.txt` fija el entorno de traducción. Se instala en `.venv-traduccion`, no en el `.venv` principal. `traducir_terminos.py` sigue en `[[lanzador.fuera]]` de `config.toml` y se ejecuta a mano con ese venv.
- `pip-audit` ignora PYSEC-2026-3075 solo en el bloque de traducción. Está en el hook de pre-commit y en el CI.
- Revisión de la excepción: cuando salga un argostranslate que acepte stanza 1.12.2 o posterior, o en la 2.3 (LLM local).

**Riesgo.** Bajo y acotado. Se produce solo si alguien sustituye los `.pt` ya descargados, o si se descarga un paquete comprometido. El script nunca corre en el lanzador, en Docker ni en CI.

**Mitigación.** `scripts/deps/argos_modelos.sha256` guarda el sha256 de los 3 `.pt` de stanza del paquete en_es. Se comprueba con `sha256sum -c` desde el directorio de paquetes de argos.

## Consecuencias
- `pip check` del `.venv` principal: 1 conflicto → 0. argostranslate sale de ese entorno.
- `pip-audit` sobre `requirements-traduccion.txt`: 14 vulnerabilidades en 3 paquetes → 0, con la excepción de stanza.
- El venv de traducción no se ha instalado de verdad. Solo se ha resuelto con `pip --dry-run`, porque la instalación baja torch con CUDA. Queda pendiente.
- La excepción de stanza no tiene comprobación automática que asegure que pre-commit y CI ignoran el mismo identificador.
