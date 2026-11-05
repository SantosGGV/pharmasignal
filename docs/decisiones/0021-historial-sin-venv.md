# 0021 · Historial sin `.venv`: reescribir con filter-repo y push forzado (opción A)

- Fecha: 2026-11-02 · Tarea: 0.9 · Estado: aceptada; ejecutada el 03/11/2026

## Contexto
Los hashes de commit de este ADR son los del historial reescrito el 03/11/2026; la tabla de equivalencias con los anteriores está en la carpeta privada.

El `.venv` entró en el repo público en el commit 60e1bd94 (09/07/2026) y salió en 49ca8871. Solo esos dos commits lo tocan. El árbol de trabajo ya no lo versiona, pero el historial sí.

Inventario, medido antes de tocar nada:
- gitleaks 8.30.1 (`gitleaks git . --redact`) escaneó 58 commits, unos 261 MB. Dio 2 hallazgos, los dos de la regla generic-api-key en `.venv/share/jupyter/nbextensions/pydeck/index.js.map:6`. Son identificadores JS de 8 caracteres de un source map, con entropía 3,9 y 4,1. Son falsos positivos.
- Hay 73 commits: 65 sin fusión y 8 fusiones. gitleaks no escaneó 7, porque no añaden líneas de texto. Se revisaron a mano: el PDF del manual (3 versiones, texto extraído, sin hallazgos y 0 rutas personales) y `img_3.png` (2 versiones, revisadas por el agente de seguridad: árbol de carpetas sin rutas personales ni credenciales).
- En `.venv/lib` hay 19.732 blobs (1.244,8 MB sin comprimir), 8.369 ficheros `.pyc` y 8.391 ficheros con la ruta personal (shebangs, `pyvenv.cfg` y RECORD).
- Fuera de `.venv` no hay ninguna ruta personal en ningún commit. Ningún hash de commit aparece citado en `docs/`, CHANGELOG, CLAUDE.md, README ni en la memoria del TFB.
- El pack pesa 645,7 MiB en disco, de los que 640,9 MiB son `.venv`.

Referencias públicas, antes de reescribir:

| Referencia | Commit | `^{tree}` |
| --- | --- | --- |
| main | 84694e90 | 6721500e |
| v1.0-tfb | 0c949725 | 518ac269 |
| datos-demo | 6bb6dab9 | b499c17b |
| datos-demo-v2 | 4ac4d3d7 | 2cd44d7e |

Las tres etiquetas descienden de 60e1bd94. `git ls-remote origin` da solo `main`, `datos-demo`, `datos-demo-v2` y `v1.0-tfb` (anotada). No hay `refs/pull` ni `refs/replace`.

El entregable de la 0.9 pide: sin rutas personales, sin `.pyc` y solo lo necesario en el historial.

## Opciones
**Cómo quitar el `.venv` del historial.**
- A) Reescribir con `git filter-repo --sensitive-data-removal --invert-paths --path .venv/` y push forzado. Es la opción elegida.
  - Cumple el entregable entero: 0 hallazgos sin excepciones, 0 rutas personales y 0 `.pyc`.
  - Cambian todos los hashes desde 60e1bd94. Las 3 etiquetas conservan su nombre y su `^{tree}`. Que el árbol sea idéntico prueba que el código defendido en `v1.0-tfb` no cambia.
  - Las releases cuelgan del nombre de la etiqueta.
  - Se pierden las firmas de las etiquetas, si las hubiera, y los hashes viejos de los cierres y del rastro privados. Se guarda `commit-map`.
  - Las copias de terceros y la caché de GitHub conservan lo viejo un tiempo.
- B) No reescribir y añadir `.gitleaksignore` con las 2 huellas. Se descarta.
  - No tiene riesgo y gitleaks termina con código 0.
  - No cumple «sin rutas personales», «sin `.pyc`» ni «solo lo necesario», y choca con la sección «Seguridad» de CLAUDE.md.
- C) Reescribir `main` y dejar `v1.0-tfb` en 0c949725. Se descarta.
  - 0c949725 desciende de 60e1bd94, así que la etiqueta mantiene todo el `.venv` alcanzable. Lo mismo pasa con una rama o etiqueta pública de archivo.

## Decisión
Opción A, elegida por Santos, con estas condiciones:
1. Antes del paso 8, Santos confirma lo entregado al campus y revisa forks, PR y protecciones de rama. Si una regla bloquea el push forzado, la desactiva él justo antes.
2. Antes de nada, `git clone --mirror` en la carpeta privada.
3. El clon que se reescribe sale de GitHub, no de la copia local, y se reescribe en un clon aparte.
4. gitleaks con `--log-opts="--all"` sobre el clon reescrito.
5. Comprobación sobre todas las refs, con el mismo contador del inventario: 0 rutas `.venv/`, 0 `.pyc`, 0 `__pycache__/` y 0 rutas personales. Si queda algo fuera de `.venv/`, se amplía el filtro.
6. El `^{tree}` de cada etiqueta y de `main`, idéntico al de la tabla.
7. `commit-map`, en privado.
8. Nada de `push --mirror`. Push forzado explícito solo de ramas y etiquetas, sin `refs/replace` ni `refs/pull`, con `--dry-run` primero. El push real lo lanza Santos.
9. Después, comprobar que las releases `datos-demo` y `datos-demo-v2` siguen publicadas con sus assets y que URL_DATOS responde 200.
10. Resincronizar la copia local sin reclonar: fetch forzado, `main` a `origin/main`, borrar las ramas locales viejas, `reflog expire` y `gc`. Prohibido `git clean -x`, porque ahí viven `data/` y `.venv`.
11. Si salen menos de 73 commits, no es un fallo.

## Consecuencias
- Los hashes anteriores a la reescritura dejan de existir en el repo público. La tabla de equivalencias va en la carpeta privada.
- Los clones y worktrees anteriores no se reutilizan.
- No hace falta `.gitleaksignore`.
- gitleaks sobre todo el historial en CI queda para la 3.6.
- Los revisores de seguridad recuerdan: `filter-repo` borra el remoto `origin`. GitHub sigue sirviendo los commits viejos por SHA hasta su recolección de basura (se pide a Soporte). Los forks y clones guardan lo viejo. Hay que comprobar que no se ha borrado nada fuera de `.venv`.

## Resultado
Ejecutada el 03/11/2026. Cifras sobre todas las refs.

| Cifra | Antes | Después |
| --- | --- | --- |
| Commits | 75 | 75. No se pierde ninguno |
| Rutas `.venv/` | 22.503 | 0 |
| `.pyc` | 8.369 | 0 |
| Rutas `__pycache__/` | 9.554 | 0 |
| Ficheros con la ruta personal (contador del inventario) | 8.391 | 0 |
| gitleaks con `--log-opts="--all" --redact` | 2 | 0 |
| Pack | 645 MB | 2,3 MiB |
| Ficheros en `main` | 126 | 126 |

- El `^{tree}` de `main` y de las 3 etiquetas es idéntico antes y después.
- Quedan 3 coincidencias del patrón crudo del inventario, que son marcadores de ruta de Windows y no rutas reales.
- gitleaks con `--log-opts="--tags"`: 0. Sobre los 126 ficheros versionados: 0.
- Push: `--dry-run` de un push forzado explícito de ramas y etiquetas, sin `--mirror`, con 4 actualizaciones. El push real lo lanzó Santos.
- Después del push, `main` está en 7d7c0e2a. Las releases `datos-demo` y `datos-demo-v2` siguen publicadas con sus assets, y URL_DATOS responde 200.
- Copia local resincronizada sin reclonar ni `git clean -x`. Pack local de 2,17 MiB y 0 objetos de `.venv`.
- Pruebas: 237 en verde (antes 229).
- Detalle y pendientes en la [bitácora del 03/11](../bitacora/2026-11-03_0.9-reescritura.md).
