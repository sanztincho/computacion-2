#!/usr/bin/env python3
"""Medición 3 — El techo del pool.

Sube la cantidad de tareas simultáneas hasta que los tiempos se degradan.
Tres partes:

  A. I/O: N tareas `esperar` de 1 s a la vez. Mientras N <= WORKERS todas
     corren juntas y el total es ~1 s; después empiezan a hacer cola.
  B. CPU: N tareas `hashear` (ejecutor proceso) a la vez. El techo acá no son
     los workers sino los PROCESOS del executor (y en el fondo, los cores).
  C. Ráfaga: K tareas cortas de golpe (por defecto 10.000), para ver qué se
     rompe primero: throughput del POST, latencia de la API, memoria.

Uso:
    docker compose exec api python mediciones/medir_techo.py
    WORKERS=2000 docker compose up -d   # y después, para ver el techo del loop:
    docker compose exec api python mediciones/medir_techo.py --partes a --ns 500,1000,2000,4000
"""
from __future__ import annotations

import argparse
import asyncio
import os
import time
from pathlib import Path

from comun import API, cliente, esperar_todas, guardar, mediana, percentil, postear_crudo


def rss_del_servidor() -> float | None:
    """MB de memoria residente del servidor, si el script corre en su contenedor
    (ahí el servidor es el PID 1). Es el VmRSS de /proc, como en el TP1."""
    try:
        for linea in Path(f'/proc/{os.environ.get("PID_SERVIDOR", 1)}/status').read_text().splitlines():
            if linea.startswith('VmRSS:'):
                return int(linea.split()[1]) / 1024
    except OSError:
        pass
    return None


async def lanzar(api: str, cuerpos: list[dict]) -> tuple[list[str], int, float]:
    """POSTea todas "a la vez". Devuelve ids aceptados, cantidad de 503 y duración.

    Usa el cliente HTTP escrito a mano de comun.py y no httpx: con miles de
    POSTs, httpx se volvía el cuello de botella (cliente al 100% de CPU,
    servidor al 20%) y estábamos midiendo al cliente, no al servidor.
    """
    respuestas, duracion = await postear_crudo(api, cuerpos)
    ids = [r['json']['id'] for r in respuestas if r['status'] == 202]
    rechazos = sum(r['status'] == 503 for r in respuestas)
    return ids, rechazos, duracion


def resumir(finales: list[dict]) -> dict:
    inicio = min(t['creada'] for t in finales)
    fin = max(t['finalizada'] for t in finales)
    esperas = [t['espera'] for t in finales if t['espera'] is not None]
    duraciones = [t['duracion'] for t in finales if t['duracion'] is not None]
    return {
        'n': len(finales),
        'total': fin - inicio,
        'espera_prom': sum(esperas) / len(esperas),
        'espera_max': max(esperas),
        'duracion_med': mediana(duraciones),
        'completadas': sum(t['estado'] == 'completada' for t in finales),
    }


async def parte_a(c, api: str, ns: list[int], segundos: float) -> list[dict]:
    stats = (await c.get('/estadisticas')).json()
    workers = stats['workers']['total']
    print(f'\nA. I/O — N tareas `esperar` de {segundos:g} s (WORKERS={workers})')
    print(f'{"N":>6} {"POSTs":>8} {"total":>9} {"ideal":>9} {"espera prom":>12} '
          f'{"espera máx":>11} {"dur. mediana":>13}')
    filas = []
    for n in ns:
        inicio = time.perf_counter()
        ids, _, t_post = await lanzar(api, [{'tipo': 'esperar',
                                             'params': {'segundos': segundos}}] * n)
        # Para N > 1000 los tiempos por tarea salen de las últimas 1000.
        fila = resumir(await esperar_todas(c, ids))
        fila.update({'n': n, 'post': t_post, 'total': time.perf_counter() - inicio,
                     'ideal': -(-n // workers) * segundos})   # ceil(n / workers) tandas
        filas.append(fila)
        print(f'{n:>6} {t_post:>6.2f} s {fila["total"]:>7.2f} s {fila["ideal"]:>7.2f} s '
              f'{fila["espera_prom"]:>10.2f} s {fila["espera_max"]:>9.2f} s '
              f'{fila["duracion_med"]:>11.3f} s')
    return filas


async def parte_b(c, api: str, ns: list[int], iteraciones: int) -> list[dict]:
    stats = (await c.get('/estadisticas')).json()
    print(f'\nB. CPU — N tareas `hashear` de {iteraciones:,} iteraciones '
          f'(PROCESOS={stats["procesos_cpu"]}, WORKERS={stats["workers"]["total"]})')
    print(f'{"N":>6} {"total":>9} {"dur. mediana":>13} {"por tarea":>10}')
    filas = []
    for n in ns:
        cuerpos = [{'tipo': 'hashear', 'timeout': 600,
                    'params': {'texto': f'x{i}', 'iteraciones': iteraciones}} for i in range(n)]
        ids, _, _ = await lanzar(api, cuerpos)
        fila = resumir(await esperar_todas(c, ids))
        filas.append(fila)
        print(f'{n:>6} {fila["total"]:>7.2f} s {fila["duracion_med"]:>11.2f} s '
              f'{fila["total"] / n:>8.2f} s')
    return filas


async def parte_c(c, k: int, api: str) -> dict:
    print(f'\nC. Ráfaga — {k:,} tareas `esperar` de 0 s de golpe')
    rss_antes = rss_del_servidor()
    latencias: list[float] = []
    terminado = asyncio.Event()

    async def sondear():
        # Mientras dura la ráfaga, ¿cuánto tarda la API en contestar? Con un
        # cliente APARTE: si usara `c`, el sondeo haría fila detrás de los
        # POSTs en el pool de conexiones y mediríamos esa fila.
        async with cliente(api, conexiones=1) as propio:
            while not terminado.is_set():
                antes = time.perf_counter()
                await propio.get('/estadisticas')
                latencias.append(time.perf_counter() - antes)
                await asyncio.sleep(0.05)

    sonda = asyncio.create_task(sondear())
    inicio = time.perf_counter()
    ids, rechazos, t_post = await lanzar(api, [{'tipo': 'esperar', 'params': {'segundos': 0}}] * k)
    # De las últimas 1000 encoladas (las que más esperaron) sacamos la espera.
    muestra = await esperar_todas(c, ids)
    vaciado = time.perf_counter() - inicio
    terminado.set()
    await sonda
    rss_despues = rss_del_servidor()
    esperas = [t['espera'] for t in muestra if t['espera'] is not None]
    fila = {'k': k, 'aceptadas': len(ids), 'rechazadas_503': rechazos,
            'post_segundos': t_post, 'post_por_segundo': len(ids) / t_post,
            'hasta_vaciar_segundos': vaciado,
            'espera_max_ultimas_1000': max(esperas) if esperas else None,
            'lat_estadisticas_p50': mediana(latencias),
            'lat_estadisticas_p95': percentil(latencias, 95),
            'lat_estadisticas_max': max(latencias) if latencias else None,
            'rss_antes_mb': rss_antes, 'rss_despues_mb': rss_despues}
    print(f'  aceptadas {len(ids):,}, rechazadas con 503: {rechazos:,}')
    print(f'  POSTs: {t_post:.2f} s  ({fila["post_por_segundo"]:,.0f} tareas/s)')
    print(f'  hasta que no quedó nada en la cola: {vaciado:.2f} s; '
          f'espera máx en cola: {fila["espera_max_ultimas_1000"]:.2f} s')
    print(f'  GET /estadisticas durante la ráfaga: p50 {fila["lat_estadisticas_p50"] * 1000:.1f} ms, '
          f'p95 {fila["lat_estadisticas_p95"] * 1000:.1f} ms, máx {fila["lat_estadisticas_max"] * 1000:.1f} ms')
    if rss_antes is not None:
        print(f'  memoria del servidor: {rss_antes:.0f} MB -> {rss_despues:.0f} MB')
    return fila


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--api', default=API)
    p.add_argument('--partes', default='abc')
    p.add_argument('--ns', default='1,2,4,8,16,32,64,128', help='valores de N para la parte A')
    p.add_argument('--segundos', type=float, default=1.0)
    p.add_argument('--ns-cpu', default='1,2,4,8')
    p.add_argument('--iteraciones', type=int, default=1_000_000)
    p.add_argument('--rafaga', type=int, default=10_000)
    args = p.parse_args()

    resultados: dict = {}
    async with cliente(args.api) as c:
        if 'a' in args.partes:
            resultados['a'] = await parte_a(c, args.api, [int(x) for x in args.ns.split(',')], args.segundos)
        if 'b' in args.partes:
            resultados['b'] = await parte_b(c, args.api, [int(x) for x in args.ns_cpu.split(',')],
                                            args.iteraciones)
        if 'c' in args.partes:
            resultados['c'] = await parte_c(c, args.rafaga, args.api)
    print('\nGuardado en', guardar('medicion3_techo', resultados))


if __name__ == '__main__':
    asyncio.run(main())
