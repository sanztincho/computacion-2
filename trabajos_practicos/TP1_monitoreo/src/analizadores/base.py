"""
analizadores/base.py
=====================

Cada analizador es un PROCESO independiente (multiprocessing.Process, no
threading.Thread) que:

  1. ignora las señales que maneja el proceso principal (para que Ctrl+C,
     que el driver de la terminal manda a todo el process group, no mate
     a los analizadores de forma descontrolada -- el shutdown limpio lo
     coordina el proceso principal via `shutdown_event`);
  2. en un loop, lee la lista de pids actual (que escribe el recolector
     en memoria compartida), extrae "su" dimension de cada proceso, y
     empuja el resultado a la cola que consume el agregador;
  3. duerme hasta su propio intervalo (ajustable en caliente via un
     multiprocessing.Value), revisando el shutdown_event cada 0.2s como
     maximo para poder reaccionar rapido a un cierre pedido por el usuario
     aunque este a mitad de un sleep largo.
"""

import queue
import signal
import time


def ignorar_senales_hijo():
    """Los procesos hijos no deben reaccionar a las señales que le llegan
    al monitor (SIGINT/SIGTERM del Ctrl+C se propagan a todo el grupo de
    procesos). El shutdown coordinado lo maneja unicamente el proceso
    principal a traves de `shutdown_event`."""
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP,
                signal.SIGUSR1, signal.SIGUSR2):
        try:
            signal.signal(sig, signal.SIG_IGN)
        except (ValueError, OSError):
            pass


def ejecutar_loop(nombre, intervalo_value, compartido, cola_salida,
                   shutdown_event, funcion_extraccion, contador_global=None,
                   **kwargs_extra):
    ignorar_senales_hijo()

    while not shutdown_event.is_set():
        inicio = time.time()

        try:
            pids = list(compartido.get("pids", []))
        except (BrokenPipeError, EOFError, OSError):
            break

        try:
            data = funcion_extraccion(pids, **kwargs_extra)
        except Exception:
            # Un analizador no debe tirar abajo el monitor entero por un
            # error puntual leyendo /proc (proceso que desaparecio a mitad
            # de lectura, permisos, etc.) -- se salta este ciclo.
            data = {}

        ts = time.time()
        try:
            cola_salida.put((nombre, data, ts), timeout=1)
        except queue.Full:
            pass
        except (BrokenPipeError, EOFError, OSError):
            break

        if contador_global is not None:
            with contador_global.get_lock():
                contador_global.value += 1

        intervalo = max(0.1, intervalo_value.value)
        objetivo = inicio + intervalo
        while not shutdown_event.is_set():
            restante = objetivo - time.time()
            if restante <= 0:
                break
            time.sleep(min(0.2, restante))
