"""Tarea `esperar`: I/O simulado. Duerme N segundos.

Sirve para probar cancelación, timeouts y ver el estado en vivo. Es la
tarea más simple, y justamente por eso muestra la regla de la clase 18:
`asyncio.sleep` cede el control al loop; `time.sleep` lo congelaría entero.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import Contexto


async def ejecutar(params: dict[str, Any], ctx: 'Contexto') -> dict[str, Any]:
    segundos = float(params['segundos'])
    loop = asyncio.get_running_loop()
    inicio = loop.time()
    fin = inicio + segundos
    # Dormimos en pasos para poder reportar progreso. Cada paso es un punto
    # de suspensión: si llega un cancel(), el CancelledError aparece acá.
    paso = max(0.25, segundos / 20)
    while (restante := fin - loop.time()) > 0:
        await asyncio.sleep(min(paso, restante))
        if segundos:
            ctx.reportar((loop.time() - inicio) / segundos)
    return {'durmio_segundos': round(loop.time() - inicio, 3)}
