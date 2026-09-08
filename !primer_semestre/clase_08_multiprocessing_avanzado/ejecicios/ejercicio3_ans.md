# ¿Qué pasa si quitás el with contador.get_lock():?

Se desata una condición de carrera (race condition). La operación contador.value += 1 no es atómica: el procesador lee el valor, le suma 1 en los registros locales y luego vuelve a escribirlo en la RAM compartida. Sin el lock, dos procesos pueden leer el mismo valor original simultáneamente, sumarle 1 de forma independiente y escribir el mismo resultado, haciendo que uno de los incrementos se pierda en el camino. El contador final dará un número caótico e impredecible (ej. 23412), menor a 40000.

# ¿Necesitarías un lock para el Array en este caso? ¿Por qué no?

No es necesario un lock para el Array en este caso. Por que la lógica del programa particiona matemáticamente los índices mediante las variables inicio y fin basándose en el id único de cada worker. Dado que ningún proceso lee ni escribe en las posiciones asignadas a otro proceso, no existe un solapamiento de escrituras concurrentes en la misma dirección de memoria.