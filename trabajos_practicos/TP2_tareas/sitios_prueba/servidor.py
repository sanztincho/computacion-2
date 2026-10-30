"""Sitios de prueba: un servidor HTTP con latencia y respuestas controladas.

Las mediciones del README no deberían depender de cómo anda internet ese
día. Este servidor (servicio `sitios` del docker-compose) simula sitios
lentos, caídos, colgados o pesados, así los números son reproducibles.

    GET /demora/{ms}             responde después de `ms` milisegundos
    GET /aleatorio?min=&max=     demora al azar entre min y max ms
    GET /estado/{codigo}         responde con ese código HTTP (404, 500, ...)
    GET /bytes/{n}               devuelve n bytes
    GET /colgado                 no responde nunca (para probar timeouts)
    GET /redirigir               302 hacia /demora/50
"""
from __future__ import annotations

import asyncio
import random

from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse

app = FastAPI(title='Sitios de prueba')

CUERPO = b'<html><body>' + b'x' * 2000 + b'</body></html>'


@app.get('/')
async def raiz():
    return {'rutas': ['/demora/{ms}', '/aleatorio?min=&max=', '/estado/{codigo}',
                      '/bytes/{n}', '/colgado', '/redirigir']}


@app.get('/demora/{ms}')
async def demora(ms: int):
    await asyncio.sleep(ms / 1000)
    return Response(CUERPO, media_type='text/html')


@app.get('/aleatorio')
async def aleatorio(min: int = 100, max: int = 1000):
    ms = random.randint(min, max)
    await asyncio.sleep(ms / 1000)
    return Response(CUERPO, media_type='text/html', headers={'X-Demora-Ms': str(ms)})


@app.get('/estado/{codigo}')
async def estado(codigo: int):
    return Response(f'estado {codigo}'.encode(), status_code=codigo)


@app.get('/bytes/{n}')
async def bytes_(n: int):
    return Response(b'a' * min(n, 50_000_000), media_type='application/octet-stream')


@app.get('/colgado')
async def colgado():
    await asyncio.sleep(3600)
    return {'ok': True}


@app.get('/redirigir')
async def redirigir():
    return RedirectResponse('/demora/50', status_code=302)
