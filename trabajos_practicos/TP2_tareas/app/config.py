"""Configuración de la plataforma, leída de variables de entorno.

Todo tiene un valor por defecto razonable, así que `docker compose up` anda
sin tocar nada. Para cambiar algo alcanza con una variable de entorno, por
ejemplo `WORKERS=16 docker compose up`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _crudo(nombre: str) -> str | None:
    """Una variable vacía (`PROCESOS=`) cuenta como no definida."""
    valor = os.environ.get(nombre, '').strip()
    return valor or None


def _entero(nombre: str, defecto: int) -> int:
    valor = _crudo(nombre)
    return int(valor) if valor is not None else defecto


def _real(nombre: str, defecto: float) -> float:
    valor = _crudo(nombre)
    return float(valor) if valor is not None else defecto


def _booleano(nombre: str, defecto: bool) -> bool:
    valor = _crudo(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in {'1', 'true', 'si', 'sí', 'yes', 'on'}


@dataclass(frozen=True)
class Config:
    # --- Servidor HTTP ---
    host: str = field(default_factory=lambda: os.environ.get('HOST', '0.0.0.0'))
    puerto: int = field(default_factory=lambda: _entero('PUERTO', 8000))

    # --- Pool de workers (corrutinas que consumen la asyncio.Queue) ---
    workers: int = field(default_factory=lambda: _entero('WORKERS', 8))
    # Tamaño máximo de la cola: es backpressure (clase 21). Si se llena,
    # POST /tareas responde 503 en vez de aceptar trabajo que no vamos a poder hacer.
    max_cola: int = field(default_factory=lambda: _entero('MAX_COLA', 10_000))

    # --- Executor para CPU-bound ---
    # Por defecto, un proceso por core: más procesos que cores no suma
    # paralelismo, solo cambios de contexto.
    procesos: int = field(default_factory=lambda: _entero('PROCESOS', os.cpu_count() or 2))
    # Iteraciones de SHA-256 que hace cada viaje al executor. Es la
    # granularidad de la cancelación de `hashear` (ver tareas/hashear.py).
    bloque_hash: int = field(default_factory=lambda: _entero('BLOQUE_HASH', 100_000))
    # Habilita `ejecutor: "loop"` en hashear: corre el cálculo DENTRO del event
    # loop. Existe solo para la medición 2 del README. Apagado por defecto.
    permitir_modo_bloqueante: bool = field(
        default_factory=lambda: _booleano('PERMITIR_MODO_BLOQUEANTE', False))

    # --- Timeouts ---
    timeout_defecto: float = field(default_factory=lambda: _real('TIMEOUT_DEFECTO', 60.0))
    timeout_maximo: float = field(default_factory=lambda: _real('TIMEOUT_MAXIMO', 3600.0))

    # --- Chequeo de URLs ---
    timeout_http: float = field(default_factory=lambda: _real('TIMEOUT_HTTP', 10.0))
    max_conexiones_http: int = field(default_factory=lambda: _entero('MAX_CONEXIONES_HTTP', 200))
    # Tope de bytes que leemos por URL: un monitor no necesita bajar una ISO
    # entera para saber si el sitio está vivo.
    max_bytes_descarga: int = field(default_factory=lambda: _entero('MAX_BYTES_DESCARGA', 5_000_000))

    # --- Historial ---
    # Cuántas tareas TERMINADAS se guardan. Las más viejas se descartan para
    # que la memoria no crezca sin límite.
    max_historial: int = field(default_factory=lambda: _entero('MAX_HISTORIAL', 20_000))

    # --- Apagado y persistencia ---
    espera_apagado: float = field(default_factory=lambda: _real('ESPERA_APAGADO', 10.0))
    dir_volcados: Path = field(
        default_factory=lambda: Path(os.environ.get('DIR_VOLCADOS', 'volcados')))

    nivel_log: str = field(default_factory=lambda: os.environ.get('NIVEL_LOG', 'INFO'))
