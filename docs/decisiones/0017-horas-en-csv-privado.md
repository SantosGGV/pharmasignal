# 0017 · Las horas de inicio y fin van a un CSV privado con lectura denegada

- Fecha: 2026-10-24 · Tarea: 0.13 · Estado: aceptada

## Contexto
El rastro de sesión debe ser legible por Claude. Pero Santos necesita las horas de inicio y fin para comparar las horas reales con las estimadas. Esas horas no deben aparecer en el repo ni en la bitácora pública.

## Opciones
- A) `$PHARMASIGNAL_PRIVADO/horas_sesiones.csv`, en la raíz privada, junto a `horas.csv`. Permisos 0600, solo se añaden líneas. Read y Edit denegados en `.claude/settings.json`, y bloqueado en `solo_lectura.py` para los agentes revisores. Sigue el patrón de `horas.csv`.
- B) No guardarlas. Santos perdería la referencia para comparar las horas reales con las estimadas.
- C) Dentro de `sesiones/`. Obligaría a denegar un fichero dentro de una carpeta que sí se puede leer, lo que es frágil.

## Decisión
Opción A.

## Consecuencias
- Claude no ve las horas en el rastro, en el contexto ni en la bitácora.
- Hueco conocido: `grep -r` o un script pueden leer el CSV, igual que `horas.csv`. Queda como pendiente.
- Las horas de este CSV no entran en la bitácora ni en el CHANGELOG.
