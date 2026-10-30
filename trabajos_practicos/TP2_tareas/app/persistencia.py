"""Persistencia mínima: volcado del estado a JSON al apagar.

Escribir un archivo es I/O bloqueante (`open`, `write`, `fsync`), así que se
hace con `asyncio.to_thread` (clase 21): aunque sean milisegundos, la regla
es "nada bloqueante adentro de una corrutina", y con diez mil tareas el JSON
puede pesar varios megas.

La escritura es atómica: primero a un archivo temporal y después
`os.replace`, que en Linux es un `rename(2)` (clase de filesystem del bloque
0). Si el proceso muere a mitad de la escritura, no queda un JSON cortado.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

PATRON = 'estado_*.json'


def _escribir(ruta: Path, datos: dict[str, Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix('.json.tmp')
    with open(temporal, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporal, ruta)


async def volcar(directorio: Path, tareas: list[dict[str, Any]],
                 estadisticas: dict[str, Any]) -> Path:
    marca = datetime.now().strftime('%Y%m%d_%H%M%S')
    ruta = directorio / f'estado_{marca}.json'
    datos = {
        'volcado': datetime.now().isoformat(timespec='seconds'),
        'estadisticas': estadisticas,
        'tareas': tareas,
    }
    await asyncio.to_thread(_escribir, ruta, datos)
    return ruta


def _leer_ultimo(directorio: Path) -> tuple[Path, dict[str, Any]] | None:
    if not directorio.is_dir():
        return None
    volcados = sorted(directorio.glob(PATRON))
    if not volcados:
        return None
    ultimo = volcados[-1]
    with open(ultimo, encoding='utf-8') as f:
        return ultimo, json.load(f)


async def reportar_volcado_previo(directorio: Path) -> dict[str, Any] | None:
    """Al arrancar: si hay un volcado anterior, lo informa por log."""
    try:
        encontrado = await asyncio.to_thread(_leer_ultimo, directorio)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning('había un volcado previo pero no se pudo leer: %s', exc)
        return None
    if encontrado is None:
        log.info('no hay volcados previos en %s', directorio)
        return None
    ruta, datos = encontrado
    conteo = Counter(t.get('estado') for t in datos.get('tareas', []))
    resumen = ', '.join(f'{n} {estado}' for estado, n in conteo.most_common()) or 'sin tareas'
    log.info('volcado previo encontrado: %s (del %s): %d tareas — %s',
             ruta.name, datos.get('volcado', '?'), len(datos.get('tareas', [])), resumen)
    pendientes = conteo.get('pendiente', 0) + conteo.get('ejecutando', 0)
    if pendientes:
        log.info('  %d de esas tareas no llegaron a terminar; no se re-encolan '
                 'automáticamente (ver README, limitaciones)', pendientes)
    return {'archivo': ruta.name, 'volcado': datos.get('volcado'),
            'tareas': len(datos.get('tareas', [])), 'por_estado': dict(conteo)}
