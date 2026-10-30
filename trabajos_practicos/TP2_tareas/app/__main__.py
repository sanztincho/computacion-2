"""Punto de entrada: `python -m app`.

Levanta uvicorn por programa (y no con el comando `uvicorn app.main:app`)
para poder engancharse a la llegada de SIGTERM / SIGINT.

uvicorn ya instala sus handlers con `signal.signal()`; nosotros heredamos su
`Server` y extendemos `handle_exit`. Ese handler corre en el hilo principal
entre dos instrucciones de bytecode, en un momento arbitrario, así que hace
lo mínimo indispensable —asignar dos atributos— y nada más: ni logging, ni
I/O, ni tocar el event loop (es la regla de async-signal-safety de la clase
de señales). El trabajo de verdad lo hace después el `lifespan`, ya en el
event loop, cuando uvicorn termina de cerrar el socket que escucha.

    señal ──> handle_exit(): aceptando=False, should_exit=True
          ──> uvicorn cierra el socket de escucha (no entran conexiones)
          ──> lifespan (finally): espera tareas en curso, cancela el resto,
              cierra el cliente HTTP y el pool de procesos, vuelca el JSON
"""
from __future__ import annotations

import signal
from types import FrameType

import uvicorn

from .config import Config
from .main import app, configurar_logs


class Servidor(uvicorn.Server):
    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        pool = getattr(app.state, 'pool', None)
        if pool is not None:
            pool.aceptando = False          # desde ya, POST /tareas da 503
        app.state.senal = signal.Signals(sig).name
        super().handle_exit(sig, frame)     # uvicorn: should_exit = True


def main() -> None:
    config: Config = app.state.config
    configurar_logs(config.nivel_log)
    servidor = Servidor(uvicorn.Config(
        app,
        host=config.host,
        port=config.puerto,
        log_level=config.nivel_log.lower(),
        # Cuánto espera uvicorn a que terminen los pedidos HTTP en vuelo antes
        # de pasar al lifespan. Las TAREAS se esperan después, con ESPERA_APAGADO.
        timeout_graceful_shutdown=5,
    ))
    servidor.run()


if __name__ == '__main__':
    main()
