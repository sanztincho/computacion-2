"""Tests de la API HTTP y el WebSocket, con la app completa (lifespan incluido)."""
from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest
from starlette.testclient import TestClient

from app.main import crear_app

from .conftest import config_de_prueba


@pytest.fixture
async def cliente(tmp_path):
    app = crear_app(config_de_prueba(tmp_path, workers=2))
    async with app.router.lifespan_context(app):
        transporte = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transporte, base_url='http://tp2') as c:
            yield c
    # Al salir del lifespan se tuvo que haber volcado el estado.
    assert list(tmp_path.glob('estado_*.json'))


async def _esperar(c: httpx.AsyncClient, tarea_id: str, estado: str) -> dict:
    async with asyncio.timeout(10):
        while True:
            datos = (await c.get(f'/tareas/{tarea_id}')).json()
            if datos['estado'] == estado:
                return datos
            await asyncio.sleep(0.02)


async def test_post_responde_inmediatamente(cliente):
    inicio = time.perf_counter()
    r = await cliente.post('/tareas', json={'tipo': 'esperar', 'params': {'segundos': 3}})
    assert time.perf_counter() - inicio < 0.1
    assert r.status_code == 202
    assert r.json()['estado'] == 'pendiente'
    assert r.headers['location'] == f"/tareas/{r.json()['id']}"


async def test_ciclo_de_vida_completo(cliente):
    r = await cliente.post('/tareas', json={'tipo': 'esperar', 'params': {'segundos': 30}})
    tid = r.json()['id']
    await _esperar(cliente, tid, 'ejecutando')

    lista = (await cliente.get('/tareas', params={'estado': 'ejecutando'})).json()
    assert [t['id'] for t in lista['tareas']] == [tid]

    r = await cliente.delete(f'/tareas/{tid}')
    assert r.status_code == 200 and r.json()['estado'] == 'cancelada'
    assert (await cliente.delete(f'/tareas/{tid}')).status_code == 409

    stats = (await cliente.get('/estadisticas')).json()
    assert stats['por_estado']['cancelada'] == 1
    assert stats['workers']['ocupados'] == 0


async def test_errores_de_validacion(cliente):
    assert (await cliente.get('/tareas/noexiste')).status_code == 404
    assert (await cliente.delete('/tareas/noexiste')).status_code == 404
    assert (await cliente.post('/tareas', json={'tipo': 'otra', 'params': {}})).status_code == 422
    r = await cliente.post('/tareas', json={'tipo': 'descargar', 'params': {'urls': ['no es url']}})
    assert r.status_code == 422
    r = await cliente.post('/tareas', json={'tipo': 'hashear', 'params': {
        'texto': 'x', 'iteraciones': 10, 'ejecutor': 'loop'}})
    assert r.status_code == 400


async def test_timeout_por_api(cliente):
    r = await cliente.post('/tareas', json={'tipo': 'esperar', 'params': {'segundos': 5},
                                            'timeout': 0.2})
    datos = await _esperar(cliente, r.json()['id'], 'fallida')
    assert 'timeout' in datos['error']


async def test_metricas_prometheus(cliente):
    texto = (await cliente.get('/metricas')).text
    assert 'tp2_workers_total 2' in texto
    assert 'tp2_tareas{estado="pendiente"}' in texto


def test_websocket_eventos(tmp_path):
    """El WebSocket manda el estado inicial y después cada cambio."""
    app = crear_app(config_de_prueba(tmp_path))
    with TestClient(app) as c:
        with c.websocket_connect('/eventos') as ws:
            inicial = ws.receive_json()
            assert inicial['evento'] == 'inicial'
            r = c.post('/tareas', json={'tipo': 'esperar', 'params': {'segundos': 0.1}})
            tid = r.json()['id']
            estados = []
            while 'completada' not in estados:
                ev = ws.receive_json()
                if ev['evento'] == 'tarea' and ev['tarea']['id'] == tid:
                    estados.append(ev['tarea']['estado'])
            assert estados == ['pendiente', 'ejecutando', 'completada']
    volcado = json.loads(next(tmp_path.glob('estado_*.json')).read_text())
    assert volcado['tareas'][0]['estado'] == 'completada'
