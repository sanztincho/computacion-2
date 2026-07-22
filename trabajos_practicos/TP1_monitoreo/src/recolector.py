"""
recolector.py
=============

El Recolector es un proceso independiente. Su unica
responsabilidad es listar los PIDs vivos leyendo /proc (os.listdir) y
publicar esa lista en memoria compartida para que los 7 analizadores la
lean, en lugar de que cada uno de los 7 procesos haga su propio
os.listdir("/proc") por separado.

¿Por que memoria compartida (un manager.dict) y no una Queue para este caso?
Porque una Queue es un canal de un-productor-a-un-consumidor por mensaje:
si el recolector pusiera la lista en una Queue, solo 1 de los 7
analizadores se la llevaria por lectura (serian consumidores en
competencia), no los 7. Lo que necesito es que los 7 analizadores
puedan leer el mismo valor mas reciente cuantas veces quieran, es decir, 
eso es "estado compartido de lectura amplia", el caso de uso tipico de
multiprocessing.Manager().
"""

import time

from analizadores.base import ignorar_senales_hijo
import procfs


def run(compartido, intervalo_value, shutdown_event):
    ignorar_senales_hijo()

    while not shutdown_event.is_set():
        inicio = time.time()

        pids = procfs.listar_pids()
        # Reemplazo atomico (una unica llamada RPC al proceso del Manager)
        # de la lista completa, en vez de ir mutandola pid por pid
        try:
            compartido["pids"] = pids
            compartido["ts_pids"] = time.time()
        except (BrokenPipeError, EOFError, OSError):
            break

        intervalo = max(0.2, intervalo_value.value)
        objetivo = inicio + intervalo
        while not shutdown_event.is_set():
            restante = objetivo - time.time()
            if restante <= 0:
                break
            time.sleep(min(0.2, restante))
