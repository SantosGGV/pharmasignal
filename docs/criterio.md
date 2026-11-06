# Criterio de PharmaSignal

Este es el único documento que describe el criterio que afecta a las cifras. README, `CLAUDE.md` y los agentes enlazan aquí. Recoge lo que hace el código: si discrepan, manda el código y se corrige este documento. Cambiar el criterio cambia las cifras y pide su propia tarea.

**Una señal es una hipótesis de trabajo, no una prueba de causalidad, y una tasa de notificación no es una incidencia.**

El manual de usuario en PDF describe la versión `v1.0-tfb`; el criterio vigente está en este documento.

Las cifras se midieron el 06/11/2026 sobre los 24 trimestres 2020q1–2025q4, antes de los cambios de la tarea 0.8, partiendo del commit `8620744`. Versiones Delta: `bronce/demo` 4, `plata/demo_geo` 3, `plata/drug_curado` 5, `plata/reac_curado` 4, `oro/senales_prr_ror` 7 y `oro/geo_senales_espana` 6.

## Valores

`tests/test_criterio.py` falla si esta tabla y `config.toml` dejan de coincidir. Hay filas para todas las claves de estas cinco secciones.

<!-- criterio:valores:inicio -->
| Clave | Valor | Regla | Dónde se usa |
| --- | --- | --- | --- |
| `senal.prr_min` | `2.0` | PRR mínimo de una señal (≥), global y de España | `prr_ror.py`, `analisis_geografico.py` |
| `senal.casos_min` | `3` | Casos mínimos para evaluar una combinación global (≥) | `prr_ror.py`, `medir_escalabilidad.py` |
| `senal.chi2_min` | `4.0` | χ² mínimo de una señal (≥), global y de España | `prr_ror.py`, `analisis_geografico.py` |
| `senal.ror_ic_inf_umbral` | `1.0` | El límite inferior del IC95 del ROR debe superarlo (>) para `ror_significativo` | `prr_ror.py` |
| `interfaz.min_casos_respaldo` | `20` | Casos mínimos de una «señal con respaldo» (≥) | `streamlit_app.py`, `validar_senales.py` |
| `listados.trivial_min_c` | `100` | Filtro de señales triviales: `c` corregida (≥) | `prr_ror.py` (consola), `streamlit_app.py` |
| `listados.trivial_min_reportes_farmaco` | `200` | Filtro de señales triviales: `a + b` corregidas (≥) | `prr_ror.py` (consola), `streamlit_app.py` |
| `geografia.min_casos_es` | `5` | Casos mínimos para evaluar una combinación en España (≥) | `analisis_geografico.py` |
| `geografia.min_casos_global` | `20` | Casos globales mínimos de los listados de consola: amplificadas (≥ 20) y atenuadas (≥ 100, el valor por 5). No filtra la tabla guardada | `analisis_geografico.py` |
| `geografia.min_casos_divergencia` | `30` | Casos mínimos en España para la divergencia (≥) | `analisis_geografico.py` |
| `geografia.min_global_divergencia` | `150` | Casos globales mínimos para la divergencia de fármacos (≥); en reacciones, el valor por 3 (450) | `analisis_geografico.py` |
| `geografia.min_reportes_pais` | `5000` | Notificaciones mínimas de un país en los rankings de geografía (≥) | `analisis_geografico.py`, `streamlit_app.py` |
| `geografia.ultimo_trimestre_es` | `"2025q2"` | Solo marca el último trimestre de España en la gráfica de evolución; no filtra datos | `streamlit_app.py` |
| `geografia.trimestres_recodificados` | `["2025q3", "2025q4"]` | Trimestres con `geo_analizable = False` | `curar_geografia.py` |
| `explorador.min_reportes_farmaco` | `5000` | Fármaco en los cruces del constructor y «Lectura fiable» (≥) | `analisis_explorador.py`, `analisis_explorador_cruces.py`, `consultas_explorador.py` |
| `explorador.min_casos_reaccion` | `1000` | Reacción en los cruces del constructor y «Lectura fiable» (≥) | `analisis_explorador.py`, `analisis_explorador_cruces.py`, `consultas_explorador.py` |
| `explorador.min_reportes_pais` | `10000` | País en los cruces del constructor (≥) | `analisis_explorador_cruces.py` |
<!-- criterio:valores:fin -->

Otros umbrales no están en `config.toml`:

- **Listados de consola:** `a ≥ 50` y `a ≥ 20` (GLP-1) en `prr_ror.py`, y `reportes ≥ 1000` en `analisis_geografico.py`.
- **Tablas guardadas del constructor, sin efecto en la señal:** `reportes ≥ 10` en `expl_farmaco_indicacion` (`analisis_explorador.py`), y las constantes `TOP_REACCIONES_POR_FARMACO` (15), `TOP_FARMACOS_POR_REACCION` (15) y `TOP_INDICACIONES_POR_FARMACO` (10) en `analisis_explorador_cruces.py`.
- **Fórmula:** la corrección de 0,5 y el 1,96 del IC95.

## Datos que entran

- **Ventana:** `ingesta_faers.py` lee todas las carpetas `data/raw/faers_ascii_*`, hoy 24 trimestres, de 2020q1 a 2025q4. No hay clave de configuración. `analisis_temporal.py` y `medir_escalabilidad.py` llevan su propia lista de esos 24 trimestres. El trimestre es el de publicación de la FDA, no la fecha del evento.
- **Deduplicación:** `curar_demo.py` deja una fila por `caseid`, la de mayor `caseversion`. Las demás tablas se alinean por `primaryid` con `demo_curado`. De 10.355.898 filas de DEMO en bruto quedan 8.785.483 casos.
- **Sospechoso primario:** `curar_drug.py` conserva todos los roles en la columna `rol` (`PS`, `SS`, `C`, `I` y `UNK`), pero los análisis usan solo `PS`.

## Tabla 2x2 y corrección

`a` son los reportes con el fármaco y la reacción; `a + b`, los del fármaco; `a + c`, los de la reacción. En `prr_ror.py`, N son los reportes que forman al menos un par fármaco-reacción: 8.783.781.

Las combinaciones con menos casos que el mínimo se descartan antes de corregir y no llegan a la tabla. Después:

- `a`, `b` y `c` suman 0,5.
- `d = N − a − b − c + 0,5`, con `a`, `b` y `c` ya corregidas. Queda en d real − 1 y no en d real + 0,5, y las cuatro casillas suman N + 0,5 (ver «Fallos conocidos»).
- La tabla guarda `a`, `b`, `c` y `d` corregidas. Los casos reales son `a − 0,5`.

Medidas:

- PRR = [a / (a + b)] / [c / (c + d)]
- ROR = (a · d) / (b · c), con IC95 = exp(ln ROR ± 1,96 · √(1/a + 1/b + 1/c + 1/d))
- χ² = N · (a·d − b·c)² / [(a + b)(c + d)(a + c)(b + d)], sin corrección de Yates

## Señal global

`es_senal` exige PRR ≥ 2, χ² ≥ 4 y a ≥ 3. **El ROR no entra en `es_senal`:** `ror_significativo` es una columna aparte, cierta si el límite inferior del IC95 supera 1.

| Nombre (interfaz y logs) | English | Significado | Cifra |
| --- | --- | --- | --- |
| Señales según criterio PRR | PRR-criterion signals | `es_senal` | 460.897 de 868.093 combinaciones |
| Señales confirmadas | Confirmed signals | `es_senal` y `ror_significativo` a la vez; hoy solo aparece en el log de `prr_ror.py` | 459.213 |
| Señales con respaldo | Supported signals | `es_senal` y al menos 20 casos reales | Depende de la consulta |

«Confirmada» solo significa que se cumplen a la vez dos criterios estadísticos: no es una confirmación clínica ni causal.

Hay 1.684 señales sin ROR significativo y 26.689 combinaciones con ROR significativo que no son señal.

PRR y ROR se calculan juntos en la tabla global. Van juntos en la descarga del panel de señales, en «Conjuntos listos» y en `outputs/validacion_senales.csv`. En pantalla, el panel de señales no enseña el ROR, y Inicio, la vista por familias y el constructor muestran solo el PRR máximo, con el nombre «veces» (ver «Fallos conocidos»). La consola de `validar_senales.py` imprime solo el PRR. España no calcula ROR.

## España y geografía

- **País:** se usa `reporter_country`, sin nulos en `demo_geo`.
- **Corte:** `geo_analizable` es falso en los trimestres recodificados. El análisis geográfico y los cruces por país exigen `geo_analizable` y `nivel_geografico = NACIONAL`. Por tanto:
  - El corte afecta a **todos los países**, no solo a España, y deja 22 trimestres (2020q1–2025q2).
  - `NACIONAL` excluye también los reportes `EU` anteriores al corte (663) y los que no tienen país identificable.
  - El corte se aplica después de deduplicar: mira el trimestre de la última versión del caso.
- **Señal en España:** a ≥ 5 casos españoles, PRR ≥ 2 y χ² ≥ 4, sobre 75.609 reportes (N incluye los que no forman ningún par; con pares son 75.503). Da 8.579 combinaciones y 6.991 señales. `geo_senales_espana` guarda la comparación con el PRR global y está retirada del catálogo «Conjuntos listos» de la interfaz.
- **Categorías:** exclusivas (señal en España y no global; 1.443), amplificadas (señal en ambos y razón de PRR > 1) y atenuadas (señal global y razón de PRR < 1). Son lecturas de consola, no columnas guardadas.
- **Límite de la fuente:** de fuera de EE. UU., la FDA solo exige los casos graves e inesperados, así que España en FAERS es un subconjunto filtrado (ver [ADR 0004](decisiones/0004-numerador-espanol.md)).

## Filtro de señales triviales

La casilla «Ocultar señales triviales» y el listado de consola exigen `c ≥ 100` y `a + b ≥ 200` **sobre valores corregidos**. `c ≥ 100` equivale a 100 reales; `a + b ≥ 200` equivale a 199 reportes reales del fármaco (ver «Fallos conocidos»).

## «Lectura fiable»

La columna «Lectura fiable» del catálogo de la interfaz **solo mide volumen**: un fármaco la tiene con ≥ 5000 reportes como sospechoso primario y una reacción con ≥ 1000 casos, ambos en toda la ventana. No dice nada de la fiabilidad estadística de una señal ni de causalidad, y no depende del respaldo de 20 casos. Las entidades por debajo se consultan igualmente, con una advertencia y solo sobre el total del periodo. El nombre se revisa en la Fase 3.

## Fallos conocidos

No se corrigen todavía. Cada uno tiene su destino.

| Fallo | Efecto medido | Destino |
| --- | --- | --- |
| `d` sin +0,5: queda en d real − 1, en `prr_ror.py`, `analisis_geografico.py` y `medir_escalabilidad.py`; `tests/test_prr_ror.py` lo da por bueno | Con `d` corregida, y también con N + 2 en χ², no cambia ninguna señal global ni de España | Fase 1, con la 1.4 |
| `a + b ≥ 200` se compara con valores corregidos: equivale a 199 reportes reales | 227 combinaciones con 199 reportes; 186 son señal y 183 de ellas pasan también `c ≥ 100` | Fase 1, con la 1.4 |
| Empate sin resolver en la deduplicación: mismo `caseversion` y mismo `primaryid` en dos trimestres, así que la fila que queda es arbitraria | 144 casos; puede variar su trimestre entre ejecuciones. En los 157 `primaryid` presentes en dos trimestres, que incluyen esos 144, el país no difiere, ninguno es de España y ninguno cruza el corte | Con la 1.0, que ya cambia la curación y obliga a reconstruir |
| Casos españoles que salen del análisis nacional: la última versión cae en un trimestre recodificado | 1.411 casos con una versión ES anterior (1.409 acaban como `EU`, 1 `US` y 1 `CN`) | Tarea nueva en la Fase 1, junto a la 1.12 |
| Ventanas distintas al comparar: España usa 22 trimestres y el PRR global 24 | Afecta a la lectura de las 1.443 exclusivas (sin medir cuánto) | Con la 1.6 |
| España sin ROR | `geo_senales_espana` no tiene columnas de ROR | Con la 1.6 |
| La interfaz muestra PRR sin ROR: la regla anterior decía «siempre juntos» y el código nunca la cumplió | Panel de señales en pantalla, Inicio, familias y constructor | Con la 1.6 en España (fila anterior) y con la 3.9 en la interfaz |
| Trimestres futuros: lo que no esté en `trimestres_recodificados` cuenta como analizable | Hoy ninguno; 2026Q1 y 2026Q2 entrarían sin aviso al cargarse en la 3.1 | Con la 0.6 |
| N distinto: en España cuenta todos los reportes y en `prr_ror.py` solo los que forman pares | 75.609 frente a 75.503 reportes españoles; con 75.503 salen 6.987 señales en vez de 6.991 (4 menos) | Con la 1.6 |
