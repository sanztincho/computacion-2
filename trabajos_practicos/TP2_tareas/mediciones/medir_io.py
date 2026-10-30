#!/usr/bin/env python3
"""Medición 1 — Concurrencia I/O: 20 chequeos secuenciales contra 20 concurrentes.

Encola dos tareas `descargar` con las MISMAS 20 URLs: una con
`concurrente: false` (un `for` con `await` adentro) y otra con
`concurrente: true` (TaskGroup). Repite varias veces y reporta la mediana.

Por defecto usa el servicio `sitios` del docker-compose, que responde con
una demora conocida (entre 200 y 1000 ms, fija por semilla), para que el
resultado no dependa de cómo anda internet. Con --reales usa URLs públicas.

Uso (desde el host, con el compose levantado):
    docker compose exec api python mediciones/medir_io.py
    docker compose exec api python mediciones/medir_io.py --reales
"""
from __future__ import annotations

import argparse
import asyncio
import random

from comun import API, SITIOS, cliente, crear, esperar, guardar, mediana

REALES = [
    'https://www.python.org', 'https://docs.python.org/3/', 'https://pypi.org',
    'https://fastapi.tiangolo.com', 'https://www.python-httpx.org', 'https://github.com',
    'https://www.wikipedia.org', 'https://www.um.edu.ar', 'https://www.debian.org',
    'https://www.kernel.org', 'https://www.docker.com', 'https://www.mozilla.org',
    'https://www.gnu.org', 'https://www.rust-lang.org', 'https://go.dev',
    'https://nodejs.org', 'https://www.postgresql.org', 'https://redis.io',
    'https://www.sqlite.org', 'https://www.openssl.org',
]


async def una_vuelta(c, urls: list[str]) -> dict:
    fila = {}
    for modo, concurrente in (('secuencial', False), ('concurrente', True)):
        t = await crear(c, {'tipo': 'descargar', 'timeout': 300,
                            'params': {'urls': urls, 'concurrente': concurrente}})
        final = await esperar(c, t['id'])
        if final['estado'] != 'completada':
            raise SystemExit(f'la tarea terminó {final["estado"]}: {final["error"]}')
        fila[modo] = final['resultado']['resumen']
    return fila


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--api', default=API)
    p.add_argument('--sitios', default=SITIOS, help='URL base del servicio sitios, vista DESDE la API')
    p.add_argument('-n', type=int, default=20, help='cantidad de URLs (20)')
    p.add_argument('--repeticiones', type=int, default=5)
    p.add_argument('--reales', action='store_true', help='usar URLs públicas de internet')
    args = p.parse_args()

    if args.reales:
        urls = (REALES * ((args.n // len(REALES)) + 1))[:args.n]
    else:
        azar = random.Random(2026)
        urls = [f'{args.sitios}/demora/{azar.randint(200, 1000)}' for _ in range(args.n)]

    print(f'Medición 1: {args.n} URLs, {args.repeticiones} repeticiones '
          f'({"internet" if args.reales else "sitios de prueba"})\n')
    print(f'{"vuelta":>6} {"secuencial":>12} {"concurrente":>12} {"suma":>10} '
          f'{"más lenta":>10} {"speedup":>8}')
    vueltas = []
    async with cliente(args.api) as c:
        for i in range(args.repeticiones):
            fila = await una_vuelta(c, urls)
            s, k = fila['secuencial'], fila['concurrente']
            speedup = s['tiempo_total_ms'] / k['tiempo_total_ms']
            vueltas.append({**fila, 'speedup': speedup})
            print(f'{i + 1:>6} {s["tiempo_total_ms"]:>9.0f} ms {k["tiempo_total_ms"]:>9.0f} ms '
                  f'{s["suma_tiempos_ms"]:>7.0f} ms {k["mas_lenta_ms"]:>7.0f} ms {speedup:>7.1f}x')

    sec = mediana([v['secuencial']['tiempo_total_ms'] for v in vueltas])
    con = mediana([v['concurrente']['tiempo_total_ms'] for v in vueltas])
    lenta = mediana([v['concurrente']['mas_lenta_ms'] for v in vueltas])
    print(f'\nMediana: secuencial {sec:.0f} ms | concurrente {con:.0f} ms | '
          f'la más lenta {lenta:.0f} ms | speedup {sec / con:.1f}x')
    ok = vueltas[-1]['concurrente']['ok']
    print(f'URLs que respondieron bien en la última vuelta: {ok}/{args.n}')
    print('Guardado en', guardar('medicion1_io', {'urls': urls, 'vueltas': vueltas}))


if __name__ == '__main__':
    asyncio.run(main())
