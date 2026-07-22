# Dudas / cosas que me quedaron sin resolver del todo

- **`pid: host` en `docker-compose.yml`**: no estoy 100% seguro de que esta
  opción esté disponible en todos los entornos donde se vaya a corregir el
  TP (algunos runners de Docker en CI la deshabilitan por motivos de
  seguridad, ya que le da al contenedor visibilidad sobre los procesos del
  host). Si falla al levantar el compose, comentar esa línea soluciona el
  arranque, pero entonces el monitor solo ve los procesos del propio
  contenedor (bastante menos interesante para mostrar en la corrección).
  No encontré una forma de detectar esto automáticamente y avisar con un
  mensaje lindo en vez de que Docker tire un error crudo.

- **Precisión del `%CPU` en el primer ciclo de cada analizador**: como el
  cálculo depende de un delta entre dos lecturas de `utime`/`stime`, el
  primer valor que se muestra de cada proceso siempre es `0.0`. Es
  matemáticamente inevitable (no hay delta contra nada), pero no sé si hay
  una forma más prolija de comunicarle esto al usuario en la UI más allá de
  simplemente mostrar 0.0 el primer ciclo.

- **Bit 0 vs señal 1 en las máscaras `SigBlk`/etc.**: asumí (y así lo
  documenté en `procfs.py`) que el bit menos significativo de la máscara
  corresponde a la señal número 1 (SIGHUP), basándome en cómo se ve
  típicamente descripta la representación de `sigset_t` en la documentación
  de Linux. No encontré una forma 100% autoritativa de confirmar esto sin
  mirar el código fuente del kernel, aunque los resultados que obtuve
  corriendo el monitor contra procesos reales (por ejemplo, ver `SIGCHLD`
  correctamente marcado como ignorado en shells típicas) son consistentes
  con esa hipótesis.

- **Zombies y la vista de Threads/FDs**: un proceso zombie no tiene
  `/proc/<pid>/task/` ni `/proc/<pid>/fd/` accesibles de forma consistente
  (o están vacíos). El monitor no rompe con esto (las funciones devuelven
  listas vacías), pero no hice nada especial para "explicar" en la UI por
  qué un zombie aparece con 0 threads/0 FDs en vez de aclarar que es porque
  está zombie — se podría mejorar mostrando un aviso explícito en el panel
  de detalle cuando el estado del proceso seleccionado es `Z`.

- **Ordenar por RSS en vistas que no son la de Memoria**: el orden `c` usa
  el RSS que reporta el analizador de Memoria, aunque la vista activa sea
  otra (por ejemplo, Threads). Esto funciona porque `_construir_filas` en
  `display.py` siempre mezcla `resumen` + `memoria`, pero si en algún
  momento se desincronizan mucho sus intervalos (por ejemplo, si alguien le
  baja mucho el intervalo a Resumen pero deja Memoria en 3s), el RSS
  mostrado puede estar más "viejo" que el resto de la fila. No me pareció
  grave pero lo anoto por las dudas.
