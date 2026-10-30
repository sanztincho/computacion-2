# Dudas / cosas que me quedaron sin resolver del todo

- **¿Está bien que las tareas pendientes no se re-encolen al reiniciar?** El
  enunciado pide volcar el estado y *reportar* el volcado previo al arrancar, y
  eso es lo que hice. Re-encolarlas sería fácil, pero no sé si es lo esperado: una
  tarea `hashear` que quedó pendiente quizás ya no le sirve a nadie después de un
  reinicio, y una `descargar` de hace una hora tampoco dice nada del estado
  actual del sitio.

- **Cancelar un `hashear` en ejecución.** Lo resolví partiendo el cálculo en
  bloques, porque un trabajo que ya arrancó en un `ProcessPoolExecutor` no se
  puede interrumpir con `Future.cancel()`. La alternativa sería matar el proceso
  (`os.kill` sobre el PID del worker del pool), pero `ProcessPoolExecutor` no
  expone qué proceso tiene cada trabajo, y matar uno deja al pool en estado
  `BrokenProcessPool`. ¿Hay una forma más directa que no conozca?

- **¿Cuenta como "event loop bloqueado" serializar un listado grande?**
  `GET /tareas` con 10.000 tareas tardaba ~500 ms de CPU en el loop. Lo acoté con
  un máximo de 1000 por pedido, pero una paginación de verdad (con cursor) sería
  más prolija. No supe si vale la pena para el TP.

- **El handler de señales de uvicorn.** uvicorn instala sus handlers con
  `signal.signal` y no con `loop.add_signal_handler` (que es lo que vimos en la
  clase 20). Extendí su `handle_exit` para engancharme en vez de pisarlo, pero no
  estoy seguro de si es la forma "oficial": no encontré una API pública para
  agregar un callback de señal en uvicorn.

- **Los números de la medición 3 dependen mucho del cliente.** Con httpx, el
  generador de carga se volvía el cuello de botella antes que el servidor. Lo
  reemplacé por un cliente HTTP mínimo escrito a mano, pero me queda la duda de
  cuánto del resultado sigue siendo del cliente (comparten los mismos cores).
  Lo ideal sería medir desde otra máquina.
