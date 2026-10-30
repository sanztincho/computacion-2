"""Almacén en memoria de las tareas y sus estadísticas.

Es un diccionario `id -> Tarea` más unos contadores que se actualizan en
cada transición de estado, para que GET /estadisticas sea O(1) y no tenga
que recorrer diez mil tareas cada vez que alguien lo consulta.

Toda modificación pasa por `transicion()`, que además publica el evento
para el WebSocket. Así hay un único lugar donde cambia el estado.
"""
from __future__ import annotations

import time
from collections import Counter, defaultdict, deque
from typing import Any, Iterable

from .eventos import BusDeEventos
from .modelos import Estado, Tarea

# Cada cuánto, como mucho, se publica un evento de progreso por tarea.
INTERVALO_PROGRESO = 0.25

# Transiciones válidas. Cualquier otra es un bug y se rechaza.
_TRANSICIONES = {
    Estado.PENDIENTE: {Estado.EJECUTANDO, Estado.CANCELADA, Estado.FALLIDA},
    Estado.EJECUTANDO: {Estado.COMPLETADA, Estado.FALLIDA, Estado.CANCELADA},
}


class Almacen:
    def __init__(self, bus: BusDeEventos, max_historial: int = 20_000) -> None:
        self._tareas: dict[str, Tarea] = {}
        self._terminadas: deque[str] = deque()
        self._max_historial = max_historial
        self.bus = bus

        self.por_estado: Counter[Estado] = Counter()
        self.creadas_total = 0
        self.descartadas_historial = 0
        # Acumuladores por tipo, para los promedios.
        self._suma_duracion: defaultdict[str, float] = defaultdict(float)
        self._cant_duracion: Counter[str] = Counter()
        self._suma_espera = 0.0
        self._cant_espera = 0
        self._ultimo_progreso: dict[str, float] = {}

    # ----------------------------------------------------------- consultas

    def __len__(self) -> int:
        return len(self._tareas)

    def obtener(self, tarea_id: str) -> Tarea | None:
        return self._tareas.get(tarea_id)

    def listar(self, estado: Estado | None = None, tipo: str | None = None,
               limite: int = 100) -> list[Tarea]:
        """Las más nuevas primero."""
        salida = []
        for tarea in reversed(self._tareas.values()):
            if estado is not None and tarea.estado is not estado:
                continue
            if tipo is not None and tarea.tipo != tipo:
                continue
            salida.append(tarea)
            if len(salida) >= limite:
                break
        return salida

    def todas(self) -> Iterable[Tarea]:
        return self._tareas.values()

    # ------------------------------------------------------- modificaciones

    def agregar(self, tarea: Tarea) -> None:
        self._tareas[tarea.id] = tarea
        self.por_estado[tarea.estado] += 1
        self.creadas_total += 1
        self._publicar(tarea)

    def transicion(self, tarea: Tarea, nuevo: Estado, **campos: Any) -> None:
        """Cambia el estado de una tarea, actualiza contadores y avisa.

        No hay ningún `await` acá adentro: para el resto del programa, el
        cambio de estado es atómico (clase 20, "Por qué no hacen falta locks").
        """
        viejo = tarea.estado
        if nuevo not in _TRANSICIONES.get(viejo, set()):
            raise ValueError(f'transición inválida {viejo.value} -> {nuevo.value}')

        ahora = time.time()
        if nuevo is Estado.EJECUTANDO:
            tarea.iniciada = ahora
            self._suma_espera += tarea.espera or 0.0
            self._cant_espera += 1
        if nuevo.terminal:
            tarea.finalizada = ahora
            tarea.progreso = 1.0 if nuevo is Estado.COMPLETADA else tarea.progreso
        for clave, valor in campos.items():
            setattr(tarea, clave, valor)

        tarea.estado = nuevo
        self.por_estado[viejo] -= 1
        self.por_estado[nuevo] += 1

        if nuevo is Estado.COMPLETADA and tarea.duracion is not None:
            self._suma_duracion[tarea.tipo] += tarea.duracion
            self._cant_duracion[tarea.tipo] += 1
        if nuevo.terminal:
            self._ultimo_progreso.pop(tarea.id, None)
            self._terminadas.append(tarea.id)
            self._podar_historial()

        self._publicar(tarea)

    def progreso(self, tarea: Tarea, valor: float) -> None:
        """Actualiza el progreso; publica como mucho cada INTERVALO_PROGRESO."""
        tarea.progreso = max(0.0, min(1.0, valor))
        ahora = time.monotonic()
        if ahora - self._ultimo_progreso.get(tarea.id, 0.0) >= INTERVALO_PROGRESO:
            self._ultimo_progreso[tarea.id] = ahora
            self.bus.publicar({'evento': 'progreso', 'id': tarea.id,
                               'progreso': tarea.progreso})

    def cargar(self, tareas: Iterable[Tarea]) -> None:
        """Solo para tests: meter tareas ya armadas sin pasar por la cola."""
        for tarea in tareas:
            self.agregar(tarea)

    # --------------------------------------------------------- estadísticas

    def promedios(self) -> dict[str, Any]:
        por_tipo = {
            tipo: {
                'completadas': self._cant_duracion[tipo],
                'duracion_promedio': self._suma_duracion[tipo] / self._cant_duracion[tipo],
            }
            for tipo in self._cant_duracion
        }
        total_cant = sum(self._cant_duracion.values())
        total_suma = sum(self._suma_duracion.values())
        return {
            'duracion_promedio': total_suma / total_cant if total_cant else None,
            'espera_promedio_en_cola': (self._suma_espera / self._cant_espera
                                        if self._cant_espera else None),
            'por_tipo': por_tipo,
        }

    # ------------------------------------------------------------- internos

    def _podar_historial(self) -> None:
        while len(self._terminadas) > self._max_historial:
            viejo_id = self._terminadas.popleft()
            # Los contadores por estado NO se tocan: las estadísticas son
            # históricas, aunque el detalle de la tarea ya no esté.
            if self._tareas.pop(viejo_id, None) is not None:
                self.descartadas_historial += 1

    def _publicar(self, tarea: Tarea) -> None:
        self.bus.publicar({'evento': 'tarea', 'tarea': tarea.a_dict()})
