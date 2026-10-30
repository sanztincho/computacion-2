"""Bus de eventos para el WebSocket /eventos (bonus 1).

Cada cliente conectado tiene su propia `asyncio.Queue` acotada. Publicar es
un `put_nowait` en cada una: **publicar nunca hace await**, así que un
navegador lento no puede frenar a los workers que generan los eventos.

Si la cola de un suscriptor se llena (el cliente no lee), se lo desconecta.
Es la misma idea de backpressure de `drain()` (clase 20), pero resuelta del
lado opuesto: en vez de frenar al productor, se suelta al consumidor lento.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)

# Marca que se le manda a un suscriptor para decirle "se terminó".
FIN = object()


class BusDeEventos:
    def __init__(self, tamanio_cola: int = 1000) -> None:
        self._suscriptores: set[asyncio.Queue] = set()
        self._tamanio = tamanio_cola

    @property
    def cantidad(self) -> int:
        return len(self._suscriptores)

    def suscribir(self) -> asyncio.Queue:
        cola: asyncio.Queue = asyncio.Queue(maxsize=self._tamanio)
        self._suscriptores.add(cola)
        return cola

    def desuscribir(self, cola: asyncio.Queue) -> None:
        self._suscriptores.discard(cola)

    def publicar(self, evento: dict[str, Any]) -> None:
        # Se itera sobre una copia porque podemos sacar suscriptores en el medio.
        for cola in list(self._suscriptores):
            try:
                cola.put_nowait(evento)
            except asyncio.QueueFull:
                log.warning('suscriptor lento: se lo desconecta')
                self._suscriptores.discard(cola)
                self._cerrar(cola)

    def cerrar_todos(self) -> None:
        for cola in list(self._suscriptores):
            self._cerrar(cola)
        self._suscriptores.clear()

    @staticmethod
    def _cerrar(cola: asyncio.Queue) -> None:
        # Vaciamos para que entre FIN aunque la cola esté llena.
        while not cola.empty():
            cola.get_nowait()
        cola.put_nowait(FIN)
