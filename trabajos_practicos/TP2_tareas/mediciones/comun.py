"""Utilidades compartidas por los scripts de medición.

Los scripts son clientes asíncronos (httpx.AsyncClient): para medir un
servidor concurrente hace falta un cliente que también lo sea.
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

API = os.environ.get('API', 'http://localhost:8000')
SITIOS = os.environ.get('SITIOS', 'http://sitios:8001')
TERMINALES = {'completada', 'fallida', 'cancelada'}
RESULTADOS = Path(__file__).parent / 'resultados'


def cliente(api: str = API, conexiones: int = 100) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=api, timeout=600,
        limits=httpx.Limits(max_connections=conexiones, max_keepalive_connections=conexiones),
        trust_env=False)


async def crear(c: httpx.AsyncClient, cuerpo: dict[str, Any]) -> dict[str, Any]:
    r = await c.post('/tareas', json=cuerpo)
    r.raise_for_status()
    return r.json()


async def esperar(c: httpx.AsyncClient, tarea_id: str, cada: float = 0.05) -> dict[str, Any]:
    while True:
        datos = (await c.get(f'/tareas/{tarea_id}')).json()
        if datos['estado'] in TERMINALES:
            return datos
        await asyncio.sleep(cada)


async def esperar_vaciado(c: httpx.AsyncClient, cada: float = 0.05) -> None:
    """Espera a que el servidor no tenga nada pendiente ni ejecutando.
    Supone que el script es el único cliente."""
    while True:
        e = (await c.get('/estadisticas')).json()['por_estado']
        if e['pendiente'] == 0 and e['ejecutando'] == 0:
            return
        await asyncio.sleep(cada)


async def esperar_todas(c: httpx.AsyncClient, ids: list[str]) -> list[dict]:
    """Espera el vaciado y trae el detalle de esas tareas (como mucho las
    últimas 1000: GET /tareas no deja pedir más, ver README)."""
    await esperar_vaciado(c)
    r = await c.get('/tareas', params={'limite': min(len(ids), 1000)})
    por_id = {t['id']: t for t in r.json()['tareas']}
    return [por_id[i] for i in ids if i in por_id]


async def postear_crudo(api: str, cuerpos: list[dict[str, Any]],
                        conexiones: int = 50) -> tuple[list[dict], float]:
    """Manda muchos POST /tareas con un cliente HTTP/1.1 escrito a mano.

    Para la ráfaga de la medición 3 httpx resultó ser el cuello de botella:
    el proceso cliente se iba al 100% de CPU mientras el servidor estaba al
    20% (ver README). Este cliente es lo mínimo indispensable: `conexiones`
    sockets keep-alive (clase 19) que sacan cuerpos de una asyncio.Queue
    compartida (productor-consumidor, clase 21), y leen la respuesta con el
    framing por Content-Length (clase 13).

    Devuelve las respuestas (status + JSON) en el orden de `cuerpos`.
    """
    partes = urlsplit(api)
    host, puerto = partes.hostname, partes.port or 80
    pendientes: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue()
    for i, cuerpo in enumerate(cuerpos):
        pendientes.put_nowait((i, json.dumps(cuerpo).encode()))
    respuestas: list[dict] = [{}] * len(cuerpos)

    async def conexion() -> None:
        reader, writer = await asyncio.open_connection(host, puerto)
        try:
            while True:
                try:
                    i, datos = pendientes.get_nowait()
                except asyncio.QueueEmpty:
                    return
                writer.write(
                    b'POST /tareas HTTP/1.1\r\n'
                    b'Host: ' + host.encode() + b'\r\n'
                    b'Content-Type: application/json\r\n'
                    b'Content-Length: ' + str(len(datos)).encode() + b'\r\n\r\n' + datos)
                await writer.drain()
                cabecera = await reader.readuntil(b'\r\n\r\n')
                lineas = cabecera.decode('latin-1').split('\r\n')
                status = int(lineas[0].split()[1])
                largo = next(int(l.split(':', 1)[1]) for l in lineas
                             if l.lower().startswith('content-length:'))
                cuerpo = await reader.readexactly(largo)
                respuestas[i] = {'status': status, 'json': json.loads(cuerpo)}
        finally:
            writer.close()
            await writer.wait_closed()

    inicio = time.perf_counter()
    async with asyncio.TaskGroup() as grupo:
        for _ in range(conexiones):
            grupo.create_task(conexion())
    return respuestas, time.perf_counter() - inicio


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return float('nan')
    ordenados = sorted(valores)
    k = min(len(ordenados) - 1, max(0, round(p / 100 * (len(ordenados) - 1))))
    return ordenados[k]


def mediana(valores: list[float]) -> float:
    return statistics.median(valores) if valores else float('nan')


def guardar(nombre: str, datos: Any) -> Path:
    RESULTADOS.mkdir(exist_ok=True)
    ruta = RESULTADOS / f'{nombre}_{datetime.now():%Y%m%d_%H%M%S}.json'
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False))
    return ruta


def ms(segundos: float) -> str:
    return f'{segundos * 1000:8.1f} ms'


class Cronometro:
    def __enter__(self):
        self.inicio = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.segundos = time.perf_counter() - self.inicio
