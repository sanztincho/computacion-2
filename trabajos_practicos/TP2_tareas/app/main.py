"""API HTTP (FastAPI) de la plataforma de tareas.

Endpoints:

    GET    /                 página de monitoreo en vivo (static/index.html)
    POST   /tareas           encola una tarea; responde 202 al instante
    GET    /tareas           lista, con filtros ?estado=&tipo=&limite=
    GET    /tareas/{id}      estado y resultado
    DELETE /tareas/{id}      cancela (pendiente o en ejecución)
    GET    /estadisticas     totales por estado, tiempos promedio, workers ocupados
    GET    /metricas         lo mismo en formato Prometheus (bonus 5)
    WS     /eventos          cambios de estado en tiempo real (bonus 1)

Todos los endpoints son `async def` y ninguno hace nada bloqueante: corren
en el event loop de uvicorn, el mismo que ejecuta a los workers (clase 19,
"Dónde está el event loop").
"""
from __future__ import annotations

import asyncio
import logging
import multiprocessing
import ssl
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import Body, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from . import persistencia
from .almacen import Almacen
from .config import Config
from .eventos import FIN, BusDeEventos
from .modelos import Estado, NuevaTarea
from .pool import ColaLlena, NoAcepta, PoolDeWorkers
from .tareas import Contexto
from .tareas.hashear import hash_iterado

log = logging.getLogger('tp2')
ESTATICOS = Path(__file__).parent / 'static'


def configurar_logs(nivel: str = 'INFO') -> None:
    logging.basicConfig(
        level=nivel,
        format='%(asctime)s %(levelname)-7s %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )


def _contextos_ssl() -> tuple[ssl.SSLContext, ssl.SSLContext]:
    # Bloqueante: lee el almacén de CAs del disco. Se llama con to_thread.
    verificado = ssl.create_default_context()
    sin_verificar = ssl.create_default_context()
    sin_verificar.check_hostname = False
    sin_verificar.verify_mode = ssl.CERT_NONE
    return verificado, sin_verificar


def crear_app(config: Config | None = None) -> FastAPI:
    config = config or Config()

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        # ------------------------------------------------------------ arranque
        configurar_logs(config.nivel_log)
        await persistencia.reportar_volcado_previo(config.dir_volcados)

        bus = BusDeEventos()
        almacen = Almacen(bus, config.max_historial)
        cliente = httpx.AsyncClient(
            timeout=config.timeout_http,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=config.max_conexiones_http,
                                max_keepalive_connections=config.max_conexiones_http // 2),
            headers={'User-Agent': 'tp2-monitor-de-sitios/1.0'},
        )
        # 'spawn' y no 'fork': hacer fork() de un proceso que ya tiene un event
        # loop, threads y sockets abiertos copia todo ese estado al hijo (clase
        # 3). Con spawn cada proceso arranca un intérprete limpio.
        pool_procesos = ProcessPoolExecutor(
            max_workers=config.procesos, mp_context=multiprocessing.get_context('spawn'))
        loop = asyncio.get_running_loop()
        # Calentamiento: levantar los procesos ahora (tarda ~0.1-0.3 s cada
        # uno) y no en la primera tarea, que si no mediría el arranque.
        await asyncio.gather(*(loop.run_in_executor(pool_procesos, hash_iterado, b'', 1)
                               for _ in range(config.procesos)))
        ssl_ok, ssl_no = await asyncio.to_thread(_contextos_ssl)

        ctx = Contexto(config, cliente, pool_procesos, ssl_ok, ssl_no)
        pool = PoolDeWorkers(config, almacen, ctx)
        pool.iniciar()
        app.state.pool = pool
        app.state.almacen = almacen
        app.state.bus = bus
        log.info('escuchando en http://%s:%d  (UI en /, docs en /docs)',
                 config.host, config.puerto)
        try:
            yield
        finally:
            # ----------------------------------------------- apagado ordenado
            senal = getattr(app.state, 'senal', None)
            log.info('apagado ordenado iniciado%s', f' por {senal}' if senal else '')
            pool.aceptando = False                       # 1. no aceptar más
            await pool.detener(config.espera_apagado)    # 2. esperar con límite
            bus.cerrar_todos()
            await cliente.aclose()                       # 3. liberar recursos
            await asyncio.to_thread(pool_procesos.shutdown, wait=True, cancel_futures=True)
            ruta = await persistencia.volcar(            # 4. volcar el estado
                config.dir_volcados,
                [t.a_dict() for t in almacen.todas()],
                pool.estadisticas(),
            )
            log.info('estado volcado en %s (%d tareas)', ruta, len(almacen))

    app = FastAPI(
        title='TP2 — Monitor de sitios',
        description='Plataforma de tareas distribuidas con asyncio (Computación II, 2026)',
        version='1.0',
        lifespan=ciclo_de_vida,
    )
    app.state.config = config

    def _pool(request: Request) -> PoolDeWorkers:
        return request.app.state.pool

    # ------------------------------------------------------------ errores

    @app.exception_handler(ColaLlena)
    async def _cola_llena(_req: Request, exc: ColaLlena):
        return JSONResponse(status_code=503, content={'detail': str(exc)},
                            headers={'Retry-After': '5'})

    @app.exception_handler(NoAcepta)
    async def _no_acepta(_req: Request, exc: NoAcepta):
        return JSONResponse(status_code=503, content={'detail': str(exc)})

    # ------------------------------------------------------------- rutas

    @app.get('/', include_in_schema=False)
    async def inicio():
        return FileResponse(ESTATICOS / 'index.html')

    @app.post('/tareas', status_code=202)
    async def crear_tarea(request: Request, nueva: NuevaTarea = Body(...)):
        pool = _pool(request)
        params = nueva.params.model_dump(mode='json')
        if (nueva.tipo == 'hashear' and params['ejecutor'] == 'loop'
                and not config.permitir_modo_bloqueante):
            raise HTTPException(400, "ejecutor 'loop' bloquea el event loop; solo se "
                                     'habilita con PERMITIR_MODO_BLOQUEANTE=1')
        tarea = pool.encolar(nueva.tipo, params, nueva.timeout)
        return JSONResponse(
            status_code=202,
            content={'id': tarea.id, 'tipo': tarea.tipo, 'estado': tarea.estado.value,
                     'timeout': tarea.timeout, 'creada': tarea.creada},
            headers={'Location': f'/tareas/{tarea.id}'},
        )

    @app.get('/tareas')
    async def listar_tareas(
        request: Request,
        estado: Estado | None = None,
        tipo: str | None = None,
        # Tope en 1000: serializar el listado es CPU puro y corre EN el loop.
        # Medido: 1.000 tareas ~80 ms, 10.000 tareas ~500 ms con todo congelado
        # (ver README, "dónde podría bloquearse el event loop").
        limite: int = Query(100, ge=1, le=1000),
    ):
        tareas = request.app.state.almacen.listar(estado, tipo, limite)
        return {'cantidad': len(tareas), 'tareas': [t.a_dict() for t in tareas]}

    @app.get('/tareas/{tarea_id}')
    async def ver_tarea(request: Request, tarea_id: str):
        tarea = request.app.state.almacen.obtener(tarea_id)
        if tarea is None:
            raise HTTPException(404, 'no existe esa tarea')
        return tarea.a_dict()

    @app.delete('/tareas/{tarea_id}')
    async def cancelar_tarea(request: Request, tarea_id: str):
        tarea = request.app.state.almacen.obtener(tarea_id)
        if tarea is None:
            raise HTTPException(404, 'no existe esa tarea')
        if tarea.estado.terminal:
            raise HTTPException(409, f'la tarea ya está {tarea.estado.value}')
        await _pool(request).cancelar(tarea_id)
        return tarea.a_dict()

    @app.get('/estadisticas')
    async def estadisticas(request: Request):
        return _pool(request).estadisticas()

    @app.get('/metricas', response_class=PlainTextResponse)
    async def metricas(request: Request):
        return _formato_prometheus(_pool(request).estadisticas())

    # --------------------------------------------------------- websocket

    @app.websocket('/eventos')
    async def eventos(ws: WebSocket):
        await ws.accept()
        pool: PoolDeWorkers = ws.app.state.pool
        almacen: Almacen = ws.app.state.almacen
        cola = almacen.bus.suscribir()
        try:
            await ws.send_json({
                'evento': 'inicial',
                'tareas': [t.a_dict() for t in almacen.listar(limite=200)],
                'estadisticas': pool.estadisticas(),
            })
            # Dos corrutinas: una manda eventos, otra solo escucha para
            # enterarse si el cliente se fue. La que termina primero corta.
            emisor = asyncio.create_task(_emitir(ws, cola, pool))
            receptor = asyncio.create_task(_esperar_desconexion(ws))
            _hechas, pendientes = await asyncio.wait(
                {emisor, receptor}, return_when=asyncio.FIRST_COMPLETED)
            for t in pendientes:
                t.cancel()
            await asyncio.gather(*pendientes, return_exceptions=True)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            almacen.bus.desuscribir(cola)

    return app


async def _emitir(ws: WebSocket, cola: asyncio.Queue, pool: PoolDeWorkers) -> None:
    loop = asyncio.get_running_loop()
    ultimas_estadisticas = loop.time()
    while True:
        # Como mucho un segundo esperando eventos: haya o no novedades, las
        # estadísticas se mandan una vez por segundo para el panel de arriba.
        restante = max(0.0, 1.0 - (loop.time() - ultimas_estadisticas))
        try:
            evento = await asyncio.wait_for(cola.get(), timeout=restante)
        except TimeoutError:
            evento = None
        if evento is FIN:
            await ws.close(code=1001)
            return
        if evento is not None:
            await ws.send_json(evento)
        if loop.time() - ultimas_estadisticas >= 1.0:
            await ws.send_json({'evento': 'estadisticas', 'estadisticas': pool.estadisticas()})
            ultimas_estadisticas = loop.time()


async def _esperar_desconexion(ws: WebSocket) -> None:
    while True:
        mensaje = await ws.receive()
        if mensaje['type'] == 'websocket.disconnect':
            return


def _formato_prometheus(e: dict[str, Any]) -> str:
    lineas = [
        '# HELP tp2_tareas Tareas por estado (histórico).',
        '# TYPE tp2_tareas gauge',
        *(f'tp2_tareas{{estado="{k}"}} {v}' for k, v in e['por_estado'].items()),
        '# HELP tp2_tareas_creadas_total Tareas creadas desde el arranque.',
        '# TYPE tp2_tareas_creadas_total counter',
        f"tp2_tareas_creadas_total {e['total']}",
        '# TYPE tp2_workers_total gauge',
        f"tp2_workers_total {e['workers']['total']}",
        '# TYPE tp2_workers_ocupados gauge',
        f"tp2_workers_ocupados {e['workers']['ocupados']}",
        '# TYPE tp2_workers_reiniciados_total counter',
        f"tp2_workers_reiniciados_total {e['workers']['reiniciados']}",
        '# TYPE tp2_cola_en_espera gauge',
        f"tp2_cola_en_espera {e['cola']['en_espera']}",
        '# TYPE tp2_cola_capacidad gauge',
        f"tp2_cola_capacidad {e['cola']['capacidad']}",
        '# TYPE tp2_duracion_promedio_segundos gauge',
        *(f'tp2_duracion_promedio_segundos{{tipo="{tipo}"}} {d["duracion_promedio"]:.6f}'
          for tipo, d in e['tiempos']['por_tipo'].items()),
    ]
    espera = e['tiempos']['espera_promedio_en_cola']
    if espera is not None:
        lineas += ['# TYPE tp2_espera_promedio_segundos gauge',
                   f'tp2_espera_promedio_segundos {espera:.6f}']
    return '\n'.join(lineas) + '\n'


app = crear_app()
