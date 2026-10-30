"""Modelos de datos: el registro interno de una tarea y los cuerpos de la API."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, HttpUrl


class Estado(str, Enum):
    PENDIENTE = 'pendiente'
    EJECUTANDO = 'ejecutando'
    COMPLETADA = 'completada'
    FALLIDA = 'fallida'
    CANCELADA = 'cancelada'

    @property
    def terminal(self) -> bool:
        """Un estado terminal ya no cambia más."""
        return self in (Estado.COMPLETADA, Estado.FALLIDA, Estado.CANCELADA)


@dataclass
class Tarea:
    """Registro de una tarea. Vive en memoria, en el diccionario del Almacen.

    No tiene lock: solo lo modifica código que corre en el event loop, y
    ninguna modificación tiene un `await` en el medio (ver README, 3.5).
    """
    tipo: str
    params: dict[str, Any]
    timeout: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    estado: Estado = Estado.PENDIENTE
    creada: float = field(default_factory=time.time)
    iniciada: float | None = None
    finalizada: float | None = None
    worker: int | None = None
    progreso: float | None = None
    resultado: Any = None
    error: str | None = None
    # Lo pide DELETE: sirve para distinguir "me cancelaron porque el usuario
    # lo pidió" de "me cancelaron porque se apaga el servidor".
    motivo_cancelacion: str | None = None

    @property
    def espera(self) -> float | None:
        """Segundos que pasó en la cola antes de que un worker la tome."""
        if self.iniciada is None:
            return None
        return self.iniciada - self.creada

    @property
    def duracion(self) -> float | None:
        """Segundos de ejecución (desde que la tomó un worker hasta que terminó)."""
        if self.iniciada is None or self.finalizada is None:
            return None
        return self.finalizada - self.iniciada

    def a_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'tipo': self.tipo,
            'estado': self.estado.value,
            'params': self.params,
            'timeout': self.timeout,
            'creada': self.creada,
            'iniciada': self.iniciada,
            'finalizada': self.finalizada,
            'espera': self.espera,
            'duracion': self.duracion,
            'worker': self.worker,
            'progreso': self.progreso,
            'resultado': self.resultado,
            'error': self.error,
        }


# ---------------------------------------------------------------------------
# Cuerpos de POST /tareas
#
# Es una unión discriminada por `tipo`: Pydantic mira ese campo y valida
# `params` con el modelo que corresponde. Un pedido mal formado se rechaza
# con 422 antes de llegar a la cola.
# ---------------------------------------------------------------------------

class ParamsDescargar(BaseModel):
    urls: list[HttpUrl] = Field(min_length=1, max_length=200,
                                description='URLs a chequear')
    concurrente: bool = Field(True, description='false = una por una (para la medición 1)')
    max_concurrencia: int = Field(20, ge=1, le=200,
                                  description='Cuántas URLs de ESTA tarea a la vez (semáforo)')


class ParamsHashear(BaseModel):
    texto: str = Field(max_length=10_000)
    iteraciones: int = Field(ge=1, le=200_000_000)
    ejecutor: Literal['proceso', 'hilo', 'loop'] = Field(
        'proceso',
        description="'proceso' = ProcessPoolExecutor (correcto), 'hilo' = to_thread, "
                    "'loop' = dentro del event loop (solo para medir, ver README)")


class ParamsEsperar(BaseModel):
    segundos: float = Field(ge=0, le=86_400)


class ParamsChequearSSL(BaseModel):
    hosts: list[str] = Field(min_length=1, max_length=100,
                             description="Hostnames, opcionalmente 'host:puerto'")
    puerto: int = Field(443, ge=1, le=65535)


class _Base(BaseModel):
    timeout: float | None = Field(None, gt=0, description='Segundos. Si se pasa, la tarea falla')


class NuevaDescargar(_Base):
    tipo: Literal['descargar']
    params: ParamsDescargar


class NuevaHashear(_Base):
    tipo: Literal['hashear']
    params: ParamsHashear


class NuevaEsperar(_Base):
    tipo: Literal['esperar']
    params: ParamsEsperar


class NuevaChequearSSL(_Base):
    tipo: Literal['chequear_ssl']
    params: ParamsChequearSSL


NuevaTarea = Annotated[
    Union[NuevaDescargar, NuevaHashear, NuevaEsperar, NuevaChequearSSL],
    Field(discriminator='tipo'),
]
