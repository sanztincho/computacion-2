"""
agregador.py
============

El Agregador es el unico proceso que escribe en el "snapshot global"
(el manager.dict con una entrada por cada una de las 7 dimensiones:
resumen, memoria, fds, threads, senales, scheduling, sistema).

Consume de una Queue comun a la que los 7 analizadores empujan sus
resultados como tuplas (tipo, data, timestamp).

Decisiones de diseño relevantes (ver tambien README):

- Usamos una Queue de *muchos productores* (los 7 analizadores) hacia
  *un unico consumidor* (este proceso). Ese es exactamente el patron para
  el que esta pensada multiprocessing.Queue.
- Que un unico proceso sea el que escribe el snapshot evita que dos
  analizadores pisen la escritura del otro al mismo tiempo (nunca hay dos
  escritores concurrentes sobre el mismo manager.dict), eliminando de raiz
  esa clase de race condition sin necesidad de un Lock explicito extra:
  el agregador ya serializa las escrituras simplemente por ser un unico
  proceso consumiendo una cola de a un mensaje por vez.
- Cada entrada del snapshot se reemplaza entera (snapshot[tipo] = {...})
  en una unica llamada RPC al proceso del Manager, nunca se mutan campos
  sueltos de un dict ya publicado: asi el Display jamas puede leer un
  estado a "medio escribir" (mitad datos viejos, mitad nuevos).
"""

import queue

from analizadores.base import ignorar_senales_hijo


def run(cola_entrada, snapshot, shutdown_event):
    ignorar_senales_hijo()

    while not shutdown_event.is_set():
        try:
            tipo, data, ts = cola_entrada.get(timeout=0.3)
        except queue.Empty:
            continue
        except (EOFError, OSError):
            break

        try:
            snapshot[tipo] = {"data": data, "ts": ts}
        except (BrokenPipeError, EOFError, OSError):
            break
