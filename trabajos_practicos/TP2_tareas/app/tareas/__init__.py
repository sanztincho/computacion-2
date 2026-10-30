"""Tipos de tarea.

Cada tipo es una corrutina `ejecutar(params, ctx) -> dict`. El pool de
workers no sabe nada de URLs ni de hashes: busca la función en `TIPOS` y la
ejecuta. Agregar un tipo nuevo es escribir un módulo y sumarlo acá.
"""
from __future__ import annotations

import ssl
from concurrent.futures import Executor
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx

from ..config import Config


@dataclass
class Contexto:
    """Lo que una tarea necesita del mundo exterior.

    Todo se crea UNA vez al arrancar (en el lifespan) y se comparte entre
    tareas: el cliente HTTP con su pool de conexiones (clase 20), el pool de
    procesos (clase 22: "crear el pool una vez") y los contextos TLS, que
    leen del disco el almacén de certificados al crearse.
    """
    config: Config
    cliente_http: httpx.AsyncClient
    pool_procesos: Executor
    ssl_verificado: ssl.SSLContext
    ssl_sin_verificar: ssl.SSLContext
    reportar: Callable[[float], None] = lambda _p: None

    def para(self, reportar: Callable[[float], None]) -> 'Contexto':
        """Copia del contexto con el callback de progreso de UNA tarea."""
        return Contexto(self.config, self.cliente_http, self.pool_procesos,
                        self.ssl_verificado, self.ssl_sin_verificar, reportar)


Ejecutor = Callable[[dict[str, Any], Contexto], Awaitable[Any]]


def _registro() -> dict[str, Ejecutor]:
    from . import chequear_ssl, descargar, esperar, hashear
    return {
        'descargar': descargar.ejecutar,
        'hashear': hashear.ejecutar,
        'esperar': esperar.ejecutar,
        'chequear_ssl': chequear_ssl.ejecutar,
    }


TIPOS: dict[str, Ejecutor] = _registro()
