# 0018 · El Cierre de la sesión lo guarda un hook Stop, no la propia sesión

- Fecha: 2026-10-24 · Tarea: 0.13 · Estado: aceptada

## Contexto
Al cerrar, la sesión escribe un Cierre. Ese texto debe quedar guardado tal cual, en la carpeta privada. ¿Quién lo escribe?

## Opciones
- A) Un hook Stop, `guardar_cierre.py`. Guarda el mensaje idéntico al del chat. No abre permisos de escritura y no gasta tokens.
- B) Que la sesión lo escriba con Write. Haría falta abrir Edit en la carpeta privada. Depende de que el modelo se acuerde, y el texto puede no coincidir con el del chat.
- C) Meterlo dentro de `exigir_bitacora.py`. Sería un hook con dos responsabilidades.

## Decisión
Opción A.

## Consecuencias
- Solo guarda mensajes que empiezan por «## Cierre de la tarea» o «## Cierre de la sesión».
- Nombre: `AAAA-MM-DD_<id>-<nombre>.md` en una rama de tarea, y `AAAA-MM-DD_sesion-<rama>.md` fuera de ella. En la misma sesión se sobrescribe. Otra sesión del mismo día añade `_2`.
- Si la carpeta privada no está definida, no escribe nada.
- `exigir_bitacora.py` sigue exigiendo la entrada. Reconoce el cierre de sesión solo si el mensaje empieza por la marca.
