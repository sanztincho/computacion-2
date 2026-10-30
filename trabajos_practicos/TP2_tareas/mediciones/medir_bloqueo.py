#!/usr/bin/env python3
"""Medición 2 — El event loop bloqueado.

Encola una tarea `hashear` pesada y, mientras corre, hace `GET /tareas` en
bucle midiendo cuánto tarda cada respuesta. Lo repite con los tres
ejecutores:

    loop     el cálculo corre DENTRO de la corrutina (sin run_in_executor)
    hilo     asyncio.to_thread  (ThreadPoolExecutor)
    proceso  run_in_executor con ProcessPoolExecutor  (el que usa el sistema)

Al final, una prueba extra: 4 hashes simultáneos con 'hilo' contra
'proceso', para ver el GIL (clase 21).

El modo 'loop' está apagado por defecto. Para esta medición hay que levantar:
    PERMITIR_MODO_BLOQUEANTE=1 docker compose up --build
y después:
    docker compose exec api python mediciones/medir_bloqueo.py
"""
from __future__ import annotations

import argparse
import asyncio
import time

from comun import API, TERMINALES, cliente, crear, esperar, guardar, mediana, percentil


async def sondear(c, tarea_id: str, cada: float) -> tuple[list[float], dict]:
    """GET /tareas en bucle hasta que la tarea termine. Devuelve las latencias."""
    latencias = []
    while True:
        antes = time.perf_counter()
        r = await c.get('/tareas', params={'limite': 20})
        latencias.append(time.perf_counter() - antes)
        tarea = next((t for t in r.json()['tareas'] if t['id'] == tarea_id), None)
        if tarea and tarea['estado'] in TERMINALES:
            return latencias, tarea
        await asyncio.sleep(cada)


async def base(c, n: int = 50) -> list[float]:
    latencias = []
    for _ in range(n):
        antes = time.perf_counter()
        await c.get('/tareas', params={'limite': 20})
        latencias.append(time.perf_counter() - antes)
    return latencias


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--api', default=API)
    p.add_argument('--iteraciones', type=int, default=5_000_000)
    p.add_argument('--cada', type=float, default=0.05, help='pausa entre sondeos (s)')
    p.add_argument('--paralelas', type=int, default=4, help='hashes simultáneos en la prueba del GIL')
    args = p.parse_args()

    resultados: dict = {'iteraciones': args.iteraciones}
    async with cliente(args.api) as c:
        lat = await base(c)
        resultados['sin_carga'] = {'p50': mediana(lat), 'max': max(lat)}
        print(f'GET /tareas sin carga: p50 {mediana(lat) * 1000:.1f} ms, '
              f'máx {max(lat) * 1000:.1f} ms\n')

        print(f'hashear {args.iteraciones:,} iteraciones de SHA-256, sondeando GET /tareas:')
        print(f'{"ejecutor":>9} {"duración":>10} {"sondeos":>8} {"p50":>10} {"p95":>10} {"máximo":>10}')
        for modo in ('loop', 'hilo', 'proceso'):
            r = await c.post('/tareas', json={'tipo': 'hashear', 'timeout': 600, 'params': {
                'texto': 'computacion II', 'iteraciones': args.iteraciones, 'ejecutor': modo}})
            if r.status_code == 400:
                print(f'{modo:>9}  deshabilitado: levantá con PERMITIR_MODO_BLOQUEANTE=1')
                continue
            r.raise_for_status()
            # Damos un instante para que un worker la tome antes de sondear.
            await asyncio.sleep(0.2)
            latencias, tarea = await sondear(c, r.json()['id'], args.cada)
            fila = {'duracion': tarea['duracion'], 'sondeos': len(latencias),
                    'p50': mediana(latencias), 'p95': percentil(latencias, 95),
                    'max': max(latencias), 'hash': tarea['resultado']['hash']}
            resultados[modo] = fila
            print(f'{modo:>9} {fila["duracion"]:>8.2f} s {fila["sondeos"]:>8} '
                  f'{fila["p50"] * 1000:>7.1f} ms {fila["p95"] * 1000:>7.1f} ms '
                  f'{fila["max"] * 1000:>7.1f} ms')
            await asyncio.sleep(0.5)

        hashes = {resultados[m]['hash'] for m in ('loop', 'hilo', 'proceso') if m in resultados}
        print(f'\nLos tres modos dieron el mismo hash: {len(hashes) == 1}')

        print(f'\nGIL: {args.paralelas} hashes de {args.iteraciones // 2:,} iteraciones a la vez')
        for modo in ('hilo', 'proceso'):
            inicio = time.perf_counter()
            ids = [(await crear(c, {'tipo': 'hashear', 'timeout': 600, 'params': {
                'texto': f't{i}', 'iteraciones': args.iteraciones // 2, 'ejecutor': modo}}))['id']
                for i in range(args.paralelas)]
            finales = [await esperar(c, i) for i in ids]
            total = time.perf_counter() - inicio
            resultados[f'gil_{modo}'] = {'total': total,
                                         'duraciones': [f['duracion'] for f in finales]}
            print(f'{modo:>9}: {total:.2f} s en total')

    print('\nGuardado en', guardar('medicion2_bloqueo', resultados))


if __name__ == '__main__':
    asyncio.run(main())
