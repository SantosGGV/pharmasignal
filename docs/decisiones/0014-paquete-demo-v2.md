# 0014 · El paquete de demo nuevo sale como release datos-demo-v2, sin sustituir datos-demo

- Fecha: 2026-10-22 · Tarea: 0.11 · Estado: aceptada

## Contexto
La imagen Docker descarga un paquete de datos de demo. El paquete anterior, `datos-demo`, lo usa la imagen de la versión `v1.0-tfb`. El paquete nuevo tiene otra estructura de carpetas, por capas. El primer paquete con capas pesaba 173 MB, frente a unos 64 MB de datos de demo, porque incluía versiones antiguas de Delta sin VACUUM.

## Opciones
- A) Una release nueva con número: `datos-demo-v2`. Es la opción elegida.
- B) Sustituir el adjunto de `datos-demo`. Rompe la imagen de `v1.0-tfb`.
- C) Recolocar las carpetas en el Dockerfile para que sirva el paquete anterior. Mezcla dos estructuras en el Dockerfile.
- D) Un respaldo en la interfaz que cargue la estructura antigua. Añade código solo para un caso viejo.

## Decisión
Opción A, con nombre `datos-demo-v2`. Santos prefiere números a nombres inventados: la 1.0 cambiará los datos y publicará `datos-demo-v3`.

Además, el paquete cumple tres reglas:
- Incluye solo la versión vigente de cada tabla Delta, con su `_delta_log` y los Parquet que usa. No hace VACUUM, porque borraría datos e historial.
- `preparar_demo.sh` se comprueba a sí mismo: abre cada tabla con `deltalake` y compara filas con la base. Si no cuadra, borra el paquete y sale con error.
- No incluye `geo_senales_espana`, que la interfaz retiró por método.

## Consecuencias
- `docker/Dockerfile`: `URL_DATOS` apunta a `datos-demo-v2`.
- `datos-demo` no se borra: la imagen `v1.0-tfb` la sigue usando.
- Las siguientes releases de datos siguen la numeración.
- El paquete v2 pesa 62.998.105 bytes (61 MB) y tiene 24 tablas.
- El paquete no es reproducible: no usa `--sort` ni `--mtime`. Queda como menor pendiente.
