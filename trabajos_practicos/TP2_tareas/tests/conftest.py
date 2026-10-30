"""Fixtures compartidas por los tests."""
from __future__ import annotations

import asyncio
import dataclasses
import multiprocessing
import ssl
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

import httpx
import pytest

from app.almacen import Almacen
from app.config import Config
from app.eventos import BusDeEventos
from app.pool import PoolDeWorkers
from app.tareas import Contexto


@pytest.fixture(scope='session')
def procesos():
    pool = ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context('spawn'))
    yield pool
    pool.shutdown(cancel_futures=True)


def config_de_prueba(tmp_path, **cambios) -> Config:
    base = Config()
    return dataclasses.replace(base, **{
        'workers': 2, 'max_cola': 100, 'procesos': 2, 'bloque_hash': 20_000,
        'timeout_defecto': 10.0, 'dir_volcados': tmp_path, 'espera_apagado': 1.0,
        **cambios,
    })


async def _manejador_por_defecto(pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=b'ok')


@pytest.fixture
def crear_pool(tmp_path, procesos):
    """Fábrica: `async with crear_pool(workers=1) as pool: ...`"""

    @asynccontextmanager
    async def fabrica(transporte: httpx.AsyncBaseTransport | None = None,
                      ssl_verificado: ssl.SSLContext | None = None, **cambios):
        config = config_de_prueba(tmp_path, **cambios)
        almacen = Almacen(BusDeEventos(), config.max_historial)
        cliente = httpx.AsyncClient(
            transport=transporte or httpx.MockTransport(_manejador_por_defecto),
            timeout=config.timeout_http)
        sin_verificar = ssl.create_default_context()
        sin_verificar.check_hostname = False
        sin_verificar.verify_mode = ssl.CERT_NONE
        ctx = Contexto(config, cliente, procesos,
                       ssl_verificado or ssl.create_default_context(), sin_verificar)
        pool = PoolDeWorkers(config, almacen, ctx)
        pool.iniciar()
        try:
            yield pool
        finally:
            await pool.detener(0.5)
            await cliente.aclose()

    return fabrica


async def esperar_estado(pool: PoolDeWorkers, tarea_id: str, *estados: str,
                         limite: float = 10.0):
    """Espera (sin bloquear) a que la tarea llegue a alguno de esos estados."""
    async with asyncio.timeout(limite):
        while True:
            tarea = pool.almacen.obtener(tarea_id)
            if tarea.estado.value in estados:
                return tarea
            await asyncio.sleep(0.01)
