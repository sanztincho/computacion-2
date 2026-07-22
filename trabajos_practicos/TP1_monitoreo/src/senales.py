"""
senales.py
==========

Manejo de señales del proceso principal (el que corre la TUI) usando el
patron **self-pipe**, que vimos en la clase 6 de la materia.

La idea central de implementacion: un signal handler de Python corre en cualquier punto de
la ejecucion del thread principal, y no es seguro hacer trabajo complejo
ahi (no es "async-signal-safe": no deberia tocar curses, escribir a
disco, tomar locks, etc. desde el handler). Por eso el handler hace lo
minimo posible -- un os.write() de un solo byte a un pipe -- y todo el
trabajo real (recargar config, volcar el snapshot, togglear verbose,
pedir shutdown) se hace en el loop principal, que revisa ese pipe en
cada vuelta con una lectura no bloqueante.
"""

import os
import signal
import fcntl


SENALES_CAPTURADAS = (
    signal.SIGINT,
    signal.SIGTERM,
    signal.SIGHUP,
    signal.SIGUSR1,
    signal.SIGUSR2,
    signal.SIGWINCH,
)


class ManejadorSenales:
    def __init__(self):
        r, w = os.pipe()
        fcntl.fcntl(r, fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(w, fcntl.F_SETFL, os.O_NONBLOCK)
        self._r = r
        self._w = w

    def instalar(self):
        for sig in SENALES_CAPTURADAS:
            signal.signal(sig, self._handler)

    def _handler(self, signum, _frame):
        # Todo lo que hace el handler: un unico write() de 1 byte.
        try:
            os.write(self._w, bytes([signum & 0xFF]))
        except (BlockingIOError, OSError):
            # El pipe esta lleno (rafaga de señales) -> se pierde el aviso
            # de ESA repeticion puntual, pero no rompe nada: en la proxima
            # señal se vuelve a intentar. Preferible a bloquear el handler.
            pass

    def leer_pendientes(self):
        """Devuelve la lista de numeros de señal recibidos desde la ultima
        vez que se llamo a este metodo. No bloquea nunca."""
        pendientes = []
        try:
            while True:
                datos = os.read(self._r, 4096)
                if not datos:
                    break
                pendientes.extend(datos)
        except BlockingIOError:
            pass
        except OSError:
            pass
        return pendientes

    def fd_lectura(self):
        return self._r