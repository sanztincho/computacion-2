"""Tests del pool: cancelación, timeouts, excepciones, backpressure, apagado."""
from __future__ import annotations

import asyncio
import time

import pytest

from app import pool as modulo_pool
from app.modelos import Estado
from app.pool import ColaLlena, NoAcepta

from .conftest import esperar_estado


async def test_encolar_no_espera_a_la_tarea(crear_pool):
    async with crear_pool() as pool:
        inicio = time.perf_counter()
        tarea = pool.encolar('esperar', {'segundos': 5}, None)
        assert time.perf_counter() - inicio < 0.01
        assert tarea.estado is Estado.PENDIENTE


async def test_tareas_se_completan(crear_pool):
    async with crear_pool() as pool:
        tarea = pool.encolar('esperar', {'segundos': 0.1}, None)
        await esperar_estado(pool, tarea.id, 'completada')
        assert tarea.resultado['durmio_segundos'] >= 0.1
        assert tarea.progreso == 1.0


async def test_workers_trabajan_en_paralelo(crear_pool):
    async with crear_pool(workers=4) as pool:
        inicio = time.perf_counter()
        tareas = [pool.encolar('esperar', {'segundos': 0.3}, None) for _ in range(4)]
        for t in tareas:
            await esperar_estado(pool, t.id, 'completada')
        # 4 de 0.3 s con 4 workers: ~0.3 s, no 1.2 s
        assert time.perf_counter() - inicio < 0.6


async def test_cancelar_pendiente(crear_pool):
    async with crear_pool(workers=1) as pool:
        primera = pool.encolar('esperar', {'segundos': 0.3}, None)
        segunda = pool.encolar('esperar', {'segundos': 0.3}, None)
        await esperar_estado(pool, primera.id, 'ejecutando')
        await pool.cancelar(segunda.id)
        assert segunda.estado is Estado.CANCELADA
        await esperar_estado(pool, primera.id, 'completada')
        # El worker la sacó de la cola, vio que estaba cancelada y la salteó.
        await asyncio.sleep(0.05)
        assert segunda.estado is Estado.CANCELADA
        assert segunda.iniciada is None


async def test_cancelar_en_ejecucion_no_mata_al_worker(crear_pool):
    async with crear_pool(workers=1) as pool:
        larga = pool.encolar('esperar', {'segundos': 30}, None)
        await esperar_estado(pool, larga.id, 'ejecutando')
        inicio = time.perf_counter()
        await pool.cancelar(larga.id)
        assert larga.estado is Estado.CANCELADA
        assert time.perf_counter() - inicio < 0.1
        assert pool.ocupados == 0
        # El único worker sigue vivo y toma la siguiente.
        siguiente = pool.encolar('esperar', {'segundos': 0.05}, None)
        await esperar_estado(pool, siguiente.id, 'completada')


async def test_timeout_pasa_a_fallida_con_motivo(crear_pool):
    async with crear_pool() as pool:
        tarea = pool.encolar('esperar', {'segundos': 5}, 0.2)
        await esperar_estado(pool, tarea.id, 'fallida')
        assert 'timeout' in tarea.error
        assert tarea.duracion == pytest.approx(0.2, abs=0.1)


async def test_excepcion_en_tarea_no_mata_al_worker(crear_pool, monkeypatch):
    async def explota(_params, _ctx):
        await asyncio.sleep(0)
        return 1 / 0

    monkeypatch.setitem(modulo_pool.TIPOS, 'explota', explota)
    async with crear_pool(workers=1) as pool:
        mala = pool.encolar('explota', {}, None)
        await esperar_estado(pool, mala.id, 'fallida')
        assert 'ZeroDivisionError' in mala.error
        buena = pool.encolar('esperar', {'segundos': 0.01}, None)
        await esperar_estado(pool, buena.id, 'completada')
        assert pool.workers_reiniciados == 0


async def test_worker_que_muere_es_reemplazado(crear_pool, monkeypatch):
    async with crear_pool(workers=1) as pool:
        original = pool._correr
        llamadas = 0

        async def correr_con_bug(tarea, wid):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 1:
                raise RuntimeError('bug en el propio worker')
            await original(tarea, wid)

        monkeypatch.setattr(pool, '_correr', correr_con_bug)
        pool.encolar('esperar', {'segundos': 0.01}, None)   # mata al worker
        await asyncio.sleep(0.05)
        assert pool.workers_reiniciados == 1
        tarea = pool.encolar('esperar', {'segundos': 0.01}, None)
        await esperar_estado(pool, tarea.id, 'completada')


async def test_cola_llena_rechaza(crear_pool):
    async with crear_pool(workers=1, max_cola=2) as pool:
        pool.encolar('esperar', {'segundos': 5}, None)
        await asyncio.sleep(0.02)                 # el worker toma la primera
        pool.encolar('esperar', {'segundos': 5}, None)
        pool.encolar('esperar', {'segundos': 5}, None)
        with pytest.raises(ColaLlena):
            pool.encolar('esperar', {'segundos': 5}, None)


async def test_apagado_ordenado(crear_pool):
    async with crear_pool(workers=1) as pool:
        corta = pool.encolar('esperar', {'segundos': 0.1}, None)
        larga = pool.encolar('esperar', {'segundos': 30}, None)
        pendiente = pool.encolar('esperar', {'segundos': 1}, None)
        await esperar_estado(pool, corta.id, 'completada')
        await esperar_estado(pool, larga.id, 'ejecutando')
        await pool.detener(espera=0.2)
        assert larga.estado is Estado.CANCELADA
        assert larga.error == 'apagado del servidor'
        assert pendiente.estado is Estado.PENDIENTE   # queda en el volcado
        with pytest.raises(NoAcepta):
            pool.encolar('esperar', {'segundos': 1}, None)


async def test_estadisticas(crear_pool):
    async with crear_pool() as pool:
        ok = pool.encolar('esperar', {'segundos': 0.05}, None)
        mal = pool.encolar('esperar', {'segundos': 5}, 0.05)
        await esperar_estado(pool, ok.id, 'completada')
        await esperar_estado(pool, mal.id, 'fallida')
        e = pool.estadisticas()
        assert e['por_estado']['completada'] == 1
        assert e['por_estado']['fallida'] == 1
        assert e['tiempos']['por_tipo']['esperar']['completadas'] == 1
        assert e['workers']['ocupados'] == 0
