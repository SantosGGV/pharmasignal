# 0012 · Las cuatro cifras de «hecho cuando» se leen de los logs del lanzador

- Fecha: 2026-10-22 · Tarea: 0.3 · Estado: aceptada

## Contexto
El «hecho cuando» de la 0.3 pide cuatro cifras de referencia tras reconstruir desde cero. Hace falta una forma de leerlas. La 0.5 es la prueba de referencia, donde vivirá la comprobación automática.

## Opciones
- Leer las cifras de los logs del lanzador. Es la opción elegida.
- Un script nuevo de comprobación. Se solaparía con la 0.5.

## Decisión
Leer las cifras de los logs del lanzador, con estos valores de referencia:
- 146.509.264: suma de los «Total» del log de ingesta.
- 113.311.496: «TOTAL curado» de `validar_curacion.py`.
- 868.093: «Combinaciones fármaco-reacción evaluadas (a>=3)» de `prr_ror.py`.
- 460.897: «Señales según criterio PRR» de `prr_ror.py`.
- Además se vigilan en el mismo log de análisis, sin ser cifras de referencia:
  - «Combinaciones con IC95 inferior del ROR > 1» de `prr_ror.py`.
  - «Señales confirmadas por ambos criterios» de `prr_ror.py`.
- La suma de las líneas «Total XXX: N filas» del log de ingesta debe coincidir con la columna Crudo de la línea TOTAL de `validar_curacion.py`.
- Además, diff vacío entre los dos `validacion_senales.csv`: el de la base aparte y el de la base del repositorio.

Aviso: la columna Crudo de `validar_curacion.py` está escrita a mano en el script (`CRUDO`). No vale como medida. Solo sirve para comparar con la suma del log de ingesta.

## Consecuencias
- Las cifras son valores de referencia. Se comprueban en la reconstrucción completa, todavía sin medir.
- La comprobación automática de cifras es de la 0.5.
