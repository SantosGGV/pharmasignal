# PharmaSignal — instrucciones para Claude Code

## Qué es
- Sistema de detección y triaje de señales de farmacovigilancia sobre FAERS 2020–2025: 146,5 M de registros en bruto, 113,3 M curados, 868.000 combinaciones fármaco–reacción evaluadas y 460.000 señales.
- Nació como el TFB de Santos (aprobado el 16/10/2026) y evoluciona a producto por fases. La hoja de ruta completa es privada y vive fuera del repositorio, en `$PHARMASIGNAL_PRIVADO/hoja_de_ruta.md`. Si discrepa de este fichero, manda la hoja.
- Pipeline por lotes con PySpark y Delta Lake. La interfaz actual (Streamlit + Plotly) lee tablas ya calculadas con `deltalake`, sin Spark; la definitiva será una web estática con DuckDB-WASM (tareas 2.9 y 3.9). Docker solo empaqueta la interfaz.

## Principios del proyecto
1. Señal no es causalidad, y una tasa de notificación no es una incidencia. Se dice en cada pantalla, informe y texto.
2. Cada cifra es trazable: versión de datos (trimestres y versión Delta) y de código (commit).
3. Método antes que pantallas.
4. Lo pesado, una vez (Spark); lo ligero, al momento (sin Spark).
5. Abierto por defecto, respetando las licencias de terceros.
6. Español primero.
7. Nada del empleador de Santos: ni datos, ni clientes, ni conocimiento de producto. No se nombra al empleador en nada de lo que se versiona.
8. Coste cero: nada de APIs, servicios, licencias ni dependencias de pago, ni los modelos `fable` o `best`, que pueden gastar créditos de uso. Si algo cuesta dinero, para y pregunta.
9. Todo queda escrito: cada sesión deja su entrada en la bitácora.

## Reglas de trabajo
1. Una tarea de la hoja por rama: `faseN/<id>-<nombre-corto>`, por ejemplo `fase0/0.3-orden`. Nunca trabajes en `main` ni mezcles tareas en una rama.
2. No hagas commit ni push. Santos revisa el diff y hace los commits; el id de la tarea entra solo en el mensaje.
3. Las tareas se llevan con `/tarea <id>` (desde la 0.13): plan del arquitecto (o plan corto de la sesión principal en tareas solo de documentación o de menos de 2 h), «sí» explícito de Santos, implementación, revisores y documentador. Hasta entonces, plan corto y OK de Santos antes de editar. Sin plan aprobado no se toca código.
4. Pasos pequeños y `pytest tests/ -v` después de cada cambio. Una tarea con pruebas en rojo no está terminada.
5. Avisa antes de lanzar una fase completa del pipeline: tarda minutos y el pico de memoria llega a unos 15,7 GB. Nunca dos ejecuciones de Spark a la vez; en cuanto exista el lanzador con candado (0.3), se lanza siempre con él.
6. Nunca modifiques ni borres nada en `data/raw/`. Las tablas de datos solo se regeneran ejecutando su script.
7. Conserva los comentarios del código tal cual, incluidas las grafías informales intencionadas («pandemos», «órden», «distringuir», «fronten»).
8. Comentarios, mensajes, documentación y textos de la interfaz, en español. No renombres funciones, tablas ni columnas sin que lo pida la tarea.
9. Umbrales y rutas, solo desde `config.toml` a través de `src/config.py`. Ni números mágicos ni rutas escritas a mano.
10. Pide confirmación antes de instalar paquetes, cambiar versiones fijadas, borrar ficheros o tocar CI y `.claude/`.
11. Al terminar, resume qué cambió, qué pruebas pasaron y las cifras de antes y después, con los hallazgos separados en «hay que arreglar sí o sí» y «opcional/menor». Nunca inventes una cifra: si no se midió, dilo.

## Seguridad
- El repositorio es público. En lo que se versiona no puede haber secretos, rutas personales, nombres de usuario, correos, horarios de trabajo ni nada del empleador. Lo privado vive en `$PHARMASIGNAL_PRIVADO`, fuera del repo.
- Secretos: nunca en código, logs, salidas, bitácora ni capturas. `.env`, `.env.*` y `.streamlit/secrets.toml` no se leen ni se versionan. gitleaks se lanza siempre con `--redact`. Las credenciales de la carpeta personal (`~/.ssh`, `~/.git-credentials`, `~/.config/gh` y `~/.netrc`) están bloqueadas en `.claude/settings.json`.
- La lista de términos prohibidos solo la lee `scripts/git/terminos_prohibidos.sh`, que enseña fichero:línea y nunca el término. Ni la lista ni `horas.csv` se abren desde Claude Code.
- Código: `bandit` sin hallazgos de severidad media o alta. Nada de `eval`, `exec`, `pickle` con datos externos, `subprocess` con `shell=True` ni `yaml.load` sin `SafeLoader`. Los ficheros de FAERS/AEMS y las respuestas de las APIs son entrada externa: se validan.
- Dependencias: versiones fijadas, `pip-audit` cada vez que cambien y licencias compatibles (nada «no comercial» ni de pago).
- Red: descargas solo de las fuentes de la hoja (FDA y openFDA, NLM/RxNav, AEMPS/CIMA, EMA, CMS, AHRQ, OCDE y Europe PMC), con suma sha256 y fecha registradas.
- `pre-commit` pasa antes de cada commit gitleaks, bandit y la lista privada de términos prohibidos; pip-audit, si cambian los requisitos; y las pruebas, si cambia código. Nunca se salta con `--no-verify`.
- Docker sin usuario root (tarea 3.6). La web futura, con CSP estricta y sin cookies de seguimiento.
- Ante la duda, para y pregunta.

## Equipo de agentes (`.claude/agents/`, desde la 0.13)
| Agente | Modelo | Cuándo entra | Qué puede hacer |
| --- | --- | --- | --- |
| arquitecto | opus | Al empezar cada tarea: plan, riesgos y decisiones (no en las de solo documentación o de menos de 2 h) | Solo leer |
| metodo | opus | Si el cambio toca `src/analisis`, umbrales de `config.toml` o cifras de señales | Leer; Bash de solo lectura |
| calidad | sonnet | Si cambia código o configuración: pruebas, cifras de antes y después, reglas de este fichero | Leer; editar solo `tests/`; Bash de solo lectura |
| seguridad | sonnet | En cada tarea, antes del commit | Leer; Bash de solo lectura (escáneres) |
| documentador | haiku | Al cerrar: bitácora, índice, CHANGELOG, ADR y «Para contar» | Leer; editar solo `docs/` y `CHANGELOG.md` |

- Los permisos los imponen hooks, no solo los prompts: `solo_en.py` limita dónde escribe cada agente y `solo_lectura.py` deja a los revisores un Bash de solo lectura. Solo corren en carpetas de confianza.
- La sesión principal orquesta e implementa. Los revisores devuelven «hay que arreglar sí o sí» y «opcional/menor»; lo primero se corrige antes de cerrar, con dos vueltas de revisión como mucho.
- El límite de uso del plan es compartido: los revisores solo entran cuando cambia su área y nunca se lanzan agentes «por si acaso».
- Varias tareas a la vez: una por worktree (`git worktree add ../pharmasignal-<id> -b faseN/<id>-<nombre>` y `claude` dentro). Los datos se comparten con `PHARMASIGNAL_BASE`; Spark, de uno en uno.

## Bitácora y trazabilidad
- `docs/bitacora/AAAA-MM-DD_<id>-<tema>.md`: una entrada por sesión, con `docs/bitacora/PLANTILLA.md`; índice en `docs/bitacora/README.md`.
- `docs/decisiones/NNNN-<titulo>.md`: un ADR por decisión con alternativas, con `docs/decisiones/PLANTILLA.md`.
- `CHANGELOG.md` con el formato Keep a Changelog; lo nuevo va en «Sin publicar».
- La bitácora es pública: sin horas, sin datos personales y sin nada del empleador. Las horas las lleva Santos en su registro privado.
- Una tarea se cierra con un mensaje que empieza por «## Cierre de la tarea <id>». El hook de cierre comprueba entonces que hay entrada de bitácora de hoy para esa tarea.
- Las capturas para «Para contar» van en `docs/img/AAAA-MM-DD_<tema>.png` y las revisa el agente de seguridad antes de versionarlas.

## Entorno
- WSL2 con Ubuntu 24.04, 24 GB de RAM y 12 núcleos. Proyecto en `~/pharmasignal` y entorno virtual en `~/pharmasignal/.venv` (Python 3.12). Java 17 (OpenJDK).
- Versiones: PySpark 4.1.1, delta-spark 4.3.1, deltalake 1.6.2, pyarrow 24.0.0, pandas 3.0.3, Streamlit 1.59.1 y Plotly 6.9.0.
- pyarrow va fijado en 24.0.0: la 25.0.0 provoca SIGSEGV con deltalake 1.6.2 y el proceso muere sin traza (código de salida 139).
- Spark en local: `local[*]`, driver de 16g, executor de 8g y `spark.sql.shuffle.partitions` = 200.
- Nunca uses `inferSchema=True` al leer el ASCII de FAERS: hay campos con varios valores separados por comas. Se lee todo como STRING y se tipa en la curación.
- El hook de inicio de sesión activa el entorno virtual para las órdenes de Claude, también en un worktree (con el del repositorio principal).
- Variables de entorno (en `~/.bashrc`, nunca en el repo): `PHARMASIGNAL_BASE` (raíz de los datos) y `PHARMASIGNAL_PRIVADO` (carpeta privada con la hoja de ruta y la lista de términos prohibidos).

## Configuración
- Umbrales y rutas en `config.toml`, leídos con `src/config.py`, que los expone con el prefijo de su sección (por ejemplo, `config.SENAL_PRR_MIN`). `PHARMASIGNAL_BASE` cambia la raíz de los datos (worktrees y Docker).
- Secciones: `[rutas]` (raw, curated, diccionarios, outputs y logs); `[senal]` (prr_min 2.0, casos_min 3, chi2_min 4.0 y ror_ic_inf_umbral 1.0); `[interfaz]` (min_casos_respaldo 20); `[listados]` (trivial_min_c 100 y trivial_min_reportes_farmaco 200); `[geografia]` (min_casos_es 5, min_casos_global 20, min_casos_divergencia 30, min_global_divergencia 150, min_reportes_pais 5000, último trimestre de España 2025q2 y trimestres recodificados 2025q3 y 2025q4); `[explorador]` (min_reportes_farmaco 5000, min_casos_reaccion 1000 y min_reportes_pais 10000); `[lanzador]` (candado en `~/.cache/pharmasignal/pipeline.lock`, espacio_min_gb 25 en el disco con menos libre entre la base, la temporal y `discos_extra` (`/mnt/c`, el que se llena de verdad en WSL2), espera_terminar_s 30, las cinco `[[lanzador.fases]]` con sus scripts y claves de `[rutas]`, y `[[lanzador.fuera]]` con `traducir_terminos.py`).
- Si esta sección no coincide con lo que dejó la tarea 0.2, manda el código: corrígela aquí.

## Comandos
- Entorno: `source .venv/bin/activate`
- Pruebas: `pytest tests/ -v`. El CI (`.github/workflows/pruebas.yml`) instala solo pytest y pyspark.
- Calidad antes del commit: `pre-commit run --all-files`
- Pipeline, siempre con el lanzador (0.3): `python src/lanzador.py --lista` (plan, sin ejecutar), `todo`, `--desde <fase>` o `--solo <fase>`. Las fases, en su orden obligatorio, son `ingesta`, `curacion`, `validacion`, `analisis` y `control`, y se declaran en `config.toml`. Sobre la base del repositorio, las fases que escriben tablas piden `--confirmar`; para reconstruir sin pisar los datos, base aparte con `PHARMASIGNAL_BASE`. Logs en `outputs/logs/`. Códigos de salida: el del script que falle, 2 (uso o comprobaciones previas), 75 (candado ocupado) y 130 (interrumpido). `traducir_terminos.py` queda fuera hasta la 0.7.
- Interfaz: `streamlit run src/app/streamlit_app.py`
- Docker, solo la interfaz: `docker build -f docker/Dockerfile -t pharmasignal:1.0 .` y `docker run --rm -p 8501:8501 pharmasignal:1.0`. Los datos de demo se descargan de la release `datos-demo` de GitHub; `docker/preparar_demo.sh` regenera ese paquete. El `.dockerignore` va en la raíz del repo.
- Otra tarea en paralelo: `git worktree add ../pharmasignal-<id> -b faseN/<id>-<nombre>`, `cd` allí, `source ~/pharmasignal/.venv/bin/activate` y `claude`. El worktree usa el entorno virtual y los datos del principal (`PHARMASIGNAL_BASE`).

## Estructura
- `src/ingesta` (2): `ingesta_faers.py` lee `data/raw/faers_ascii_*/ASCII/{DEMO,DRUG,REAC,OUTC,INDI,THER,RPSR}*.txt` con separador `$` y escribe Delta; `explorar_faers.py`.
- `src/curacion` (12): un `curar_*.py` por tabla, `curar_geografia.py`, `traducir_terminos.py`, `validar_curacion.py` y dos diagnósticos de geografía.
- `src/analisis` (8): `prr_ror.py`, `analisis_geografico.py`, `analisis_temporal.py`, `analisis_explorador.py`, `analisis_explorador_cruces.py`, `familias.py`, `validar_senales.py` y `medir_escalabilidad.py`.
- `src/app` (2): `streamlit_app.py` y `consultas_explorador.py`.
- `src/config.py` y `config.toml` (0.2); `src/lanzador.py` (0.3); `tests/` con `test_prr_ror.py`, `test_lanzador.py` y las pruebas de los hooks (`test_hooks_commit.py` y `test_hooks_agentes.py`).
- `docs/bitacora`, `docs/decisiones` y `docs/img`; `CHANGELOG.md`.
- `.claude/agents`, `.claude/skills/tarea`, `.claude/hooks` y `.claude/settings.json`; `scripts/git` (hooks de pre-commit); `.pre-commit-config.yaml`.

## Datos
- `data/raw/`: 24 carpetas, de `faers_ascii_2020q1` a `faers_ascii_2025q4`. Cada una tiene `ASCII/` con las 7 tablas y una carpeta `Deleted` o `DELETED` con los casos eliminados por la FDA, en cuatro formatos de nombre (se aplican en la 1.0). `integridad_faers.sha256` usa rutas relativas a `data/raw`.
- Desde el 11/03/2026 la FDA publica FAERS como AEMS. Los extractos trimestrales siguen en el mismo ASCII; 2026Q1 y 2026Q2 ya están publicados y se cargan en la 3.1.
- `data/diccionarios/`: `paises.txt` y `terminos_es.txt`.
- `data/curated/`: 40 tablas Delta (se separan por capas en la 0.11).
  - Bronce (7): `demo`, `drug`, `indi`, `outc`, `reac`, `rpsr`, `ther`.
  - Plata (9): los 7 `*_curado`, `demo_geo` y `trad_terminos`.
  - Oro (24): `senales_prr_ror`; `serie_temporal_familias` y `serie_temporal_glp1_farmacos`; 7 tablas `geo_*` (`geo_senales_espana` está retirada del catálogo «Conjuntos listos»); y las 14 `expl_*` del constructor.
- `outputs/`: logs (`outputs/logs/`, del lanzador) y mediciones. En Git solo están `escalabilidad.json` y `validacion_senales.csv`.

## Método (no se cambia sin una tarea explícita)
- Criterio de señal: PRR ≥ 2, a ≥ 3 y χ² ≥ 4, con corrección de Haldane-Anscombe (+0,5 en las cuatro casillas, siempre).
- ROR con su IC95; cuenta como señal si el límite inferior supera 1. PRR y ROR se calculan y se muestran siempre juntos.
- Solo el fármaco sospechoso principal. La geografía usa `reporter_country` (0 % de nulos).
- Desde 2025Q3, FAERS mete a España en el agregado europeo, así que el análisis nacional se limita a 2020Q1–2025Q2.
- De fuera de EE. UU., la FDA solo exige los casos graves e inesperados: España en FAERS es un subconjunto filtrado (se mide en la 1.12).
- Nunca un denominador común entre bases distintas (FAERS, EudraVigilance, VAERS, MAUDE): cada una se calcula por separado y, como mucho, se replica la señal.
- Las tasas por exposición (2.10) son tasas de notificación, no incidencias.

## Hoja de ruta (resumen; el detalle está en la hoja privada)
- **Fase 0 · Base técnica (hasta el 26/11/2026):** 0.1 etiqueta, ramas y CHANGELOG · 0.2 configuración única · 0.3 orden única y relanzado por fase, con candado · 0.4 sello de ejecución · 0.5 prueba de referencia · 0.6 controles por trimestre · 0.7 dependencias e imagen en CI · 0.8 criterio documentado · 0.9 repo limpio · 0.10 licencia · 0.11 capas · 0.12 bitácora y trazabilidad · 0.13 equipo de agentes.
- **Fase 1 · Método creíble (27/11/2026–20/02/2027):** 1.0 casos eliminados (primero) · 1.1 RxNorm · 1.2 ATC con RxClass · 1.3 ruido · 1.4 BCPNN · 1.5 MGPS · 1.6 España con corrección bayesiana · 1.7 y 1.8 duplicados · 1.9 OMOP · 1.10 referencia PRAC/FDA · 1.11 READUS-PV · 1.12 sesgo de España en FAERS.
- **Fase 2 · Triaje útil (21/02–18/06/2027):** 2.1 etiquetas FDA · 2.2 ficha de CIMA · 2.3 emparejamiento con LLM local · 2.4 prioridad · 2.5 ficha de la señal · 2.6 detección temprana · 2.7 listas de vigilancia · 2.8 informe · 2.9 análisis de la interfaz definitiva · 2.10 denominadores de exposición · 2.11 Europe PMC · 2.12 notas de la AEMPS · 2.13 antigüedad del fármaco.
- **Fase 3 · Plataforma (19/06–12/11/2027):** 3.1 carga incremental · 3.2 orquestación · 3.3 Parquet y GitHub Pages · 3.4 demo pública · 3.5 repo abierto con DOI · 3.6 seguridad en CI · 3.7 memoria · 3.8 compactación · 3.9 interfaz definitiva.
- **Después:** puerta «producto digno» (hacia el 15/11/2027), ronda de contactos y Fase 5 con nuevas fuentes (VAERS, EudraVigilance y, si procede, MAUDE).
