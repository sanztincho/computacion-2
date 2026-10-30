"""Tarea `descargar`: chequeo de disponibilidad de URLs (I/O-bound).

Para cada URL devuelve el código de estado, el tamaño del cuerpo y el tiempo
de respuesta: lo que necesita un monitor de sitios para decir "está vivo",
"está caído" o "está lento".

Las URLs de una misma tarea se chequean **concurrentemente** con un
`TaskGroup` acotado por un `Semaphore` (clases 20 y 21), así que 20 URLs
tardan lo que la más lenta y no la suma. Con `concurrente: false` se hacen
con un `for` + `await`, una detrás de otra: es la versión secuencial que
pide la medición 1, y la respuesta a "¿qué diferencia hay entre gather y un
for con await adentro?".

Usamos **httpx** en modo async (ver README, decisión 3.6).
"""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from . import Contexto


async def chequear_url(cliente: httpx.AsyncClient, url: str, max_bytes: int) -> dict[str, Any]:
    """Pide una URL y mide. Nunca lanza excepciones de red: las informa.

    El cuerpo se lee en streaming y con tope. Además, el `async with` del
    stream es lo que hace limpia la cancelación: si llega un CancelledError
    a mitad de la descarga, al salir del bloque httpx cierra la respuesta y
    devuelve (o descarta) la conexión del pool. No queda un socket colgado.
    """
    inicio = time.perf_counter()
    try:
        async with cliente.stream('GET', url) as resp:
            tamanio = 0
            truncado = False
            async for trozo in resp.aiter_bytes():
                tamanio += len(trozo)
                if tamanio >= max_bytes:
                    truncado = True
                    break
            resultado: dict[str, Any] = {
                'url': url,
                'ok': resp.status_code < 400,
                'codigo': resp.status_code,
                'tamanio': tamanio,
                'truncado': truncado,
                'tiempo_ms': round((time.perf_counter() - inicio) * 1000, 1),
                'http': resp.http_version,
            }
            if str(resp.url) != url:
                resultado['url_final'] = str(resp.url)
            return resultado
    except httpx.HTTPError as exc:
        # Timeout de conexión, DNS que no resuelve, conexión rechazada, TLS
        # inválido... Para un monitor eso no es un error de la tarea: es el
        # dato que vinimos a buscar ("el sitio está caído").
        return {
            'url': url,
            'ok': False,
            'codigo': None,
            'tamanio': 0,
            'tiempo_ms': round((time.perf_counter() - inicio) * 1000, 1),
            'error': f'{type(exc).__name__}: {exc}' if str(exc) else type(exc).__name__,
        }


async def ejecutar(params: dict[str, Any], ctx: 'Contexto') -> dict[str, Any]:
    urls: list[str] = [str(u) for u in params['urls']]
    concurrente: bool = params.get('concurrente', True)
    limite: int = params.get('max_concurrencia', 20)
    max_bytes = ctx.config.max_bytes_descarga

    resultados: list[dict[str, Any] | None] = [None] * len(urls)
    hechas = 0

    async def una(i: int, url: str) -> None:
        nonlocal hechas
        resultados[i] = await chequear_url(ctx.cliente_http, url, max_bytes)
        hechas += 1            # sin lock: entre leer y escribir no hay await
        ctx.reportar(hechas / len(urls))

    inicio = time.perf_counter()
    if concurrente:
        sem = asyncio.Semaphore(limite)

        async def acotada(i: int, url: str) -> None:
            async with sem:
                await una(i, url)

        # TaskGroup y no gather: si esta tarea se cancela (DELETE o timeout),
        # el grupo cancela a TODAS sus hijas y espera a que terminen antes de
        # propagar. No quedan descargas huérfanas (clase 21).
        async with asyncio.TaskGroup() as grupo:
            for i, url in enumerate(urls):
                grupo.create_task(acotada(i, url))
    else:
        for i, url in enumerate(urls):
            await una(i, url)
    total_ms = (time.perf_counter() - inicio) * 1000

    tiempos = [r['tiempo_ms'] for r in resultados if r]
    caidas = [r['url'] for r in resultados if r and not r['ok']]
    return {
        'resumen': {
            'total': len(urls),
            'ok': len(urls) - len(caidas),
            'caidas': len(caidas),
            'modo': 'concurrente' if concurrente else 'secuencial',
            'tiempo_total_ms': round(total_ms, 1),
            'suma_tiempos_ms': round(sum(tiempos), 1),
            'mas_lenta_ms': max(tiempos) if tiempos else None,
        },
        'urls': resultados,
    }
