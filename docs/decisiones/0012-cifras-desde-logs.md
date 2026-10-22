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
- 868.093: «Combinaciones evaluadas» de `prr_ror.py`.
- 460.897: «Señales según criterio PRR» de `prr_ror.py`.
- Además, diff vacío entre los dos `validacion_senales.csv`: el de la base aparte y el de la base del repositorio.

Aviso: el «TOTAL crudo» de `validar_curacion.py` está escrito a mano en el script. No vale como medida.

## Consecuencias
- Las cifras son valores de referencia. Se comprueban en la reconstrucción completa, todavía sin medir.
- La comprobación automática de cifras es de la 0.5.
