"""Tarea `hashear`: CPU-bound. Aplica SHA-256 N veces sobre un texto.

Es la tarea que demuestra que asyncio NO sirve para calcular: el event loop
corre en un solo hilo, así que una corrutina que calcula sin hacer `await`
congela a todas las demás (clase 18 y 21).

La solución es sacar el cálculo del loop con `run_in_executor` hacia un
`ProcessPoolExecutor`. Pero en vez de mandar las N iteraciones de una sola
vez, se mandan en **bloques** de `BLOQUE_HASH` iteraciones. ¿Por qué?

* Un trabajo que ya arrancó en un executor **no se puede cancelar**:
  `Future.cancel()` solo funciona si todavía no empezó (clase 22). Si
  mandáramos 50 millones de iteraciones juntas, un DELETE dejaría al proceso
  calculando durante un minuto para nada.
* Con bloques, entre bloque y bloque hay un `await`: un punto donde puede
  entrar el CancelledError. Lo que se desperdicia al cancelar es, como mucho,
  un bloque (~0.1 s), y el proceso queda libre para la próxima tarea.
* De paso, entre bloques podemos reportar el progreso.

El costo es un viaje de ida y vuelta al proceso por bloque (se picklean 32
bytes de digest y un entero), que es despreciable frente a 100.000 hashes.
"""
from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import Contexto


class ModoBloqueanteDeshabilitado(RuntimeError):
    pass


def hash_iterado(dato: bytes, iteraciones: int) -> bytes:
    """Función pura y a nivel de módulo: se puede picklear y mandar a otro
    proceso (una lambda o una función anidada no podrían, clase 22)."""
    for _ in range(iteraciones):
        dato = hashlib.sha256(dato).digest()
    return dato


async def ejecutar(params: dict[str, Any], ctx: 'Contexto') -> dict[str, Any]:
    texto: str = params['texto']
    total: int = int(params['iteraciones'])
    modo: str = params.get('ejecutor', 'proceso')
    dato = texto.encode()

    if modo == 'loop':
        # ¡ESTO ES EL BUG A PROPÓSITO! Solo para la medición 2 del README.
        # El cálculo corre en el hilo del event loop: mientras dura, uvicorn no
        # acepta conexiones, ningún endpoint responde, ningún timeout vence y
        # ni siquiera se puede cancelar esta tarea (no hay ningún await).
        if not ctx.config.permitir_modo_bloqueante:
            raise ModoBloqueanteDeshabilitado(
                "ejecutor 'loop' deshabilitado (PERMITIR_MODO_BLOQUEANTE=0)")
        digest = hash_iterado(dato, total)
        return {'hash': digest.hex(), 'iteraciones': total, 'ejecutor': modo, 'bloques': 1}

    loop = asyncio.get_running_loop()
    bloque = max(1, ctx.config.bloque_hash)
    hechas = 0
    bloques = 0
    while hechas < total:
        n = min(bloque, total - hechas)
        if modo == 'proceso':
            # Paralelismo real: otro intérprete, otro GIL.
            dato = await loop.run_in_executor(ctx.pool_procesos, hash_iterado, dato, n)
        else:
            # 'hilo': libera al loop, pero comparte el GIL con él (ver README,
            # medición 2): el loop sigue respondiendo, aunque con algo de atraso.
            dato = await asyncio.to_thread(hash_iterado, dato, n)
        hechas += n
        bloques += 1
        ctx.reportar(hechas / total)

    return {'hash': dato.hex(), 'iteraciones': total, 'ejecutor': modo, 'bloques': bloques}
