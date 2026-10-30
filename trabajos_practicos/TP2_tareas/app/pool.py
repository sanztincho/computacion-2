"""Pool de workers: la cola, los workers, la cancelación y los timeouts.

Es el corazón del TP. El flujo de una tarea es:

    POST /tareas ──> encolar() ──> asyncio.Queue ──> _worker() ──> _ejecutar()
                      (put_nowait)    (maxsize)        (N corrutinas)    │
                                                                         ├─ I/O: await directo
                                                                         └─ CPU: run_in_executor

Cada worker es un bucle infinito que saca IDs de la cola. Para cada tarea
crea una `asyncio.Task` HIJA que la ejecuta, y espera a que termine. Esa
separación worker/hija es la que permite:

* **Cancelar una tarea en ejecución** sin matar al worker: DELETE cancela la
  hija, y el worker sigue vivo para la próxima.
* **Aislar las excepciones**: si la tarea explota, la excepción queda guardada
  en la hija; el worker la lee, marca la tarea como fallida y sigue.
"""
from __future__ import annotations

import asyncio
import logging
import time
import traceback
from typing import Any

from .almacen import Almacen
from .config import Config
from .modelos import Estado, Tarea
from .tareas import TIPOS, Contexto

log = logging.getLogger(__name__)


class ColaLlena(Exception):
    """La cola llegó a maxsize: backpressure, se responde 503."""


class NoAcepta(Exception):
    """El servidor se está apagando: no se aceptan tareas nuevas."""


class PoolDeWorkers:
    def __init__(self, config: Config, almacen: Almacen, ctx: Contexto) -> None:
        self.config = config
        self.almacen = almacen
        self.ctx = ctx
        self.cola: asyncio.Queue[str] = asyncio.Queue(maxsize=config.max_cola)
        self._workers: dict[int, asyncio.Task] = {}
        # id de tarea -> asyncio.Task hija que la está ejecutando.
        self._en_curso: dict[str, asyncio.Task] = {}
        self._deteniendo = False
        self.aceptando = True
        self.inicio = time.time()
        self.workers_reiniciados = 0

    # ------------------------------------------------------------ ciclo de vida

    def iniciar(self) -> None:
        for wid in range(self.config.workers):
            self._lanzar_worker(wid)
        log.info('pool iniciado: %d workers, cola de %d, %d procesos para CPU',
                 self.config.workers, self.config.max_cola, self.config.procesos)

    def _lanzar_worker(self, wid: int) -> None:
        tarea = asyncio.create_task(self._worker(wid), name=f'worker-{wid}')
        # Guardamos la referencia: el loop solo guarda referencias débiles a
        # las tasks, y una task sin referencia puede ser recolectada a mitad
        # de camino (está en la documentación de create_task).
        self._workers[wid] = tarea
        tarea.add_done_callback(self._vigilar_worker)

    def _vigilar_worker(self, tarea: asyncio.Task) -> None:
        """Supervisor: si un worker muere por un bug, se lanza otro.

        No debería pasar nunca (el worker atrapa todo lo que viene de la
        tarea), pero si pasa, sin esto el pool se va achicando en silencio:
        es el "bug silencioso" de los futures de la clase 22.
        """
        wid = int(tarea.get_name().split('-')[1])
        if self._deteniendo or tarea.cancelled():
            return
        exc = tarea.exception()
        log.error('worker %d murió: %r. Se lanza un reemplazo.', wid, exc,
                  exc_info=exc)
        self.workers_reiniciados += 1
        self._lanzar_worker(wid)

    async def detener(self, espera: float) -> None:
        """Apagado ordenado: no aceptar más, esperar con límite, cancelar el resto."""
        self.aceptando = False
        self._deteniendo = True

        en_curso = list(self._en_curso.values())
        if en_curso:
            log.info('apagado: esperando hasta %.0fs a %d tareas en ejecución',
                     espera, len(en_curso))
            _hechas, pendientes = await asyncio.wait(en_curso, timeout=espera)
            if pendientes:
                log.warning('apagado: se cancelan %d tareas que no terminaron a tiempo',
                            len(pendientes))
                for tarea_id, hija in list(self._en_curso.items()):
                    if hija in pendientes:
                        registro = self.almacen.obtener(tarea_id)
                        if registro:
                            registro.motivo_cancelacion = 'apagado del servidor'
                        hija.cancel()
                await asyncio.wait(pendientes)

        # Los workers que quedan están esperando en cola.get(): se cancelan.
        # Las tareas que siguen 'pendiente' en la cola quedan así en el volcado.
        for w in self._workers.values():
            w.cancel()
        await asyncio.gather(*self._workers.values(), return_exceptions=True)
        log.info('pool detenido (quedaron %d tareas pendientes sin ejecutar)',
                 self.almacen.por_estado.get(Estado.PENDIENTE, 0))

    # ------------------------------------------------------------- operaciones

    def encolar(self, tipo: str, params: dict[str, Any], timeout: float | None) -> Tarea:
        """Registra la tarea y la mete en la cola. NO espera a que se ejecute.

        Es sincrónica a propósito (no tiene ningún await): por eso el POST
        responde en microsegundos, tarde lo que tarde la tarea.
        """
        if not self.aceptando:
            raise NoAcepta('el servidor se está apagando')
        timeout = min(timeout or self.config.timeout_defecto, self.config.timeout_maximo)
        tarea = Tarea(tipo=tipo, params=params, timeout=timeout)
        try:
            # put_nowait y no `await put()`: si la cola está llena preferimos
            # rechazar enseguida (503) antes que dejar colgado el pedido HTTP.
            self.cola.put_nowait(tarea.id)
        except asyncio.QueueFull:
            raise ColaLlena(f'la cola tiene {self.cola.qsize()} tareas, reintentá más tarde')
        self.almacen.agregar(tarea)
        return tarea

    async def cancelar(self, tarea_id: str, espera: float = 5.0) -> Tarea | None:
        """Cancela una tarea pendiente o en ejecución.

        * Pendiente: se marca cancelada y listo. Sigue estando en la
          asyncio.Queue (no se puede sacar un elemento del medio), pero cuando
          un worker la saque va a ver que está cancelada y la va a saltear.
        * Ejecutando: se cancela la Task hija. El CancelledError aparece en su
          próximo `await`, corren sus `finally`/`async with` (que cierran
          sockets y conexiones) y el worker la marca como cancelada.
        """
        tarea = self.almacen.obtener(tarea_id)
        if tarea is None or tarea.estado.terminal:
            return tarea
        if tarea.estado is Estado.PENDIENTE:
            self.almacen.transicion(tarea, Estado.CANCELADA, error='cancelada por el usuario')
            return tarea

        hija = self._en_curso.get(tarea_id)
        if hija is not None:
            tarea.motivo_cancelacion = 'cancelada por el usuario'
            hija.cancel()
            # Esperamos (con límite) a que la cancelación se complete, así el
            # DELETE puede devolver el estado final. asyncio.wait NO propaga
            # el CancelledError de la hija ni la cancela si vence el timeout.
            await asyncio.wait([hija], timeout=espera)
        return tarea

    # ------------------------------------------------------------------ workers

    async def _worker(self, wid: int) -> None:
        while True:
            tarea_id = await self.cola.get()
            try:
                if self._deteniendo:
                    break
                tarea = self.almacen.obtener(tarea_id)
                if tarea is None or tarea.estado is not Estado.PENDIENTE:
                    continue        # cancelada mientras esperaba: se saltea
                await self._correr(tarea, wid)
            finally:
                # En un finally: si no, cola.join() esperaría para siempre
                # cuando algo falla (clase 21, "task_done y join").
                self.cola.task_done()

    async def _correr(self, tarea: Tarea, wid: int) -> None:
        self.almacen.transicion(tarea, Estado.EJECUTANDO, worker=wid, progreso=0.0)
        hija = asyncio.create_task(self._ejecutar(tarea), name=f'tarea-{tarea.id}')
        self._en_curso[tarea.id] = hija
        try:
            # asyncio.wait y no `await hija`: así, si la hija termina con
            # excepción o cancelada, el worker NO la recibe como propia.
            await asyncio.wait([hija])
        except asyncio.CancelledError:
            # Cancelaron AL WORKER (apagado forzado), no a la tarea: hay que
            # cancelar también a la hija y esperarla, para no dejarla huérfana.
            hija.cancel()
            await asyncio.wait([hija])
            self._registrar_final(tarea, hija)
            raise                   # SIEMPRE relanzar el CancelledError (clase 20)
        finally:
            self._en_curso.pop(tarea.id, None)
        self._registrar_final(tarea, hija)

    async def _ejecutar(self, tarea: Tarea) -> Any:
        funcion = TIPOS[tarea.tipo]
        ctx = self.ctx.para(lambda p: self.almacen.progreso(tarea, p))
        # El timeout es un caso particular de cancelación (clase 20): al vencer,
        # asyncio.timeout() cancela esta corrutina y convierte el
        # CancelledError en TimeoutError al salir del bloque.
        limite = asyncio.timeout(tarea.timeout)
        try:
            async with limite:
                return await funcion(tarea.params, ctx)
        except TimeoutError:
            if limite.expired():
                raise _Vencida(tarea.timeout) from None
            raise

    def _registrar_final(self, tarea: Tarea, hija: asyncio.Task) -> None:
        if tarea.estado.terminal:
            return
        if hija.cancelled():
            self.almacen.transicion(
                tarea, Estado.CANCELADA,
                error=tarea.motivo_cancelacion or 'cancelada')
            return
        exc = hija.exception()
        if exc is None:
            self.almacen.transicion(tarea, Estado.COMPLETADA, resultado=hija.result())
        elif isinstance(exc, _Vencida):
            self.almacen.transicion(tarea, Estado.FALLIDA, error=str(exc))
        else:
            log.warning('tarea %s (%s) falló: %r\n%s', tarea.id, tarea.tipo, exc,
                        ''.join(traceback.format_exception(exc)).rstrip())
            self.almacen.transicion(tarea, Estado.FALLIDA,
                                    error=f'{type(exc).__name__}: {exc}')

    # ------------------------------------------------------------ estadísticas

    @property
    def ocupados(self) -> int:
        return len(self._en_curso)

    def estadisticas(self) -> dict[str, Any]:
        por_estado = {e.value: self.almacen.por_estado.get(e, 0) for e in Estado}
        return {
            'por_estado': por_estado,
            'total': self.almacen.creadas_total,
            'workers': {
                'total': self.config.workers,
                'ocupados': self.ocupados,
                'libres': self.config.workers - self.ocupados,
                'reiniciados': self.workers_reiniciados,
            },
            'cola': {'en_espera': self.cola.qsize(), 'capacidad': self.config.max_cola},
            'tiempos': self.almacen.promedios(),
            'procesos_cpu': self.config.procesos,
            'aceptando': self.aceptando,
            'clientes_ws': self.almacen.bus.cantidad,
            'uptime_segundos': round(time.time() - self.inicio, 1),
        }


class _Vencida(Exception):
    def __init__(self, segundos: float) -> None:
        super().__init__(f'timeout: no terminó en {segundos:g}s')
