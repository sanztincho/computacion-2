#!/usr/bin/env python3
"""
main.py
=======

Punto de entrada del monitor. Arma toda la arquitectura multiproceso:

    Recolector (1 proceso)  ->  compartido['pids']  ->  7 Analizadores (7 procesos)
                                                              |
                                                              v
                                                     cola_agregador (Queue)
                                                              |
                                                              v
                                                  Agregador (1 proceso) -> snapshot (Manager.dict)
                                                                                |
                                                                                v
                                                                 Display / TUI (proceso principal)

Estructuras de IPC usadas y por que cada una:

  - `compartido` (Manager.dict):  el Recolector escribe la lista de pids
    completa en cada ciclo; los 7 analizadores la leen. Uno-a-muchos ->
    memoria compartida, no una Queue.

  - `cola_agregador` (Queue): los 7 analizadores escriben sus resultados;
    un unico proceso (el Agregador) los consume. Muchos-a-uno -> el caso
    de uso tipico de multiprocessing.Queue.

  - `snapshot` (Manager.dict): el Agregador es el UNICO escritor; el
    Display es lector. Se usa Manager (y no Value/Array) porque el
    contenido es heterogeneo y variable (dicts anidados por pid, listas
    de tamaño variable) -- Value/Array solo sirven para tipos ctypes
    homogeneos de tamaño fijo (enteros, floats, arrays de estos).

  - `intervalos[tipo]` (multiprocessing.Value, uno por vista): un unico
    escritor (el Display, cuando el usuario aprieta +/-) y un unico
    lector (el analizador de esa vista, en cada vuelta de su loop). Al
    ser un unico entero/float con un unico lector y un unico escritor,
    Value es mucho mas liviano que pasar por el proceso intermediario
    del Manager (Value vive en memoria compartida real via mmap, sin
    necesidad de un roundtrip de IPC a un proceso servidor).

  - `contador_actualizaciones` (multiprocessing.Value con lock): lo
    incrementan los 7 analizadores. Aca SI hace falta el lock explicito
    del Value (`with contador.get_lock():`) porque hay multiples
    escritores concurrentes sobre el mismo entero -- sin el lock,
    "value += 1" no es atomico (es un read-modify-write) y se pueden
    perder incrementos si dos analizadores lo hacen "al mismo tiempo".

  - `shutdown_event` (multiprocessing.Event): booleano compartido para
    coordinar un apagado limpio de todos los procesos.
"""

import argparse
import curses
import json
import multiprocessing as mp
import signal as signal_module
import sys
import time
from collections import deque

import display
import procfs
import recolector
import agregador
import senales as senales_handlers
from configuracion import cargar_config
from analizadores import resumen, memoria, fds, threads, senales as an_senales, scheduling, sistema

TIPOS = ["resumen", "memoria", "fds", "threads", "senales", "scheduling", "sistema"]

MODULOS = {
    "resumen": resumen,
    "memoria": memoria,
    "fds": fds,
    "threads": threads,
    "senales": an_senales,
    "scheduling": scheduling,
    "sistema": sistema,
}


def parse_args():
    p = argparse.ArgumentParser(description="Monitor de procesos y threads via /proc (Computacion II)")
    p.add_argument("--config", default="config.json", help="Ruta al archivo de configuracion JSON")
    p.add_argument("--dump-dir", default=".", help="Directorio donde guardar los dumps de SIGUSR1")
    p.add_argument("--daemon", metavar="ARCHIVO", default=None,
                    help="Corre sin TUI: loggea snapshots periodicos a ARCHIVO (modo daemon, bonus)")
    p.add_argument("--selftest", action="store_true",
                    help="Arranca el backend (recolector+analizadores+agregador) sin curses, "
                         "imprime un resumen del snapshot a los pocos segundos y termina. "
                         "Util para verificar la arquitectura sin una terminal interactiva.")
    return p.parse_args()


def _armar_contexto(args, config, manager):
    compartido = manager.dict()
    compartido["pids"] = []
    compartido["ts_pids"] = 0.0

    snapshot = manager.dict()
    for tipo in TIPOS:
        snapshot[tipo] = {"data": {}, "ts": 0.0}

    cola_agregador = mp.Queue(maxsize=500)
    shutdown_event = mp.Event()
    verbose_value = mp.Value("i", 1 if config.get("verbose_default") else 0)
    contador_actualizaciones = mp.Value("i", 0)

    intervalos = {}
    for tipo in TIPOS:
        default = config["intervalos"].get(tipo, {}).get("default", 2.0)
        intervalos[tipo] = mp.Value("d", float(default))

    return {
        "compartido": compartido,
        "snapshot": snapshot,
        "cola_agregador": cola_agregador,
        "shutdown_event": shutdown_event,
        "verbose_value": verbose_value,
        "contador_actualizaciones": contador_actualizaciones,
        "intervalos": intervalos,
        "config": config,
        "ruta_config": args.config,
        "dir_dumps": args.dump_dir,
        "ultimas_senales": deque(maxlen=6),
    }


def _crear_procesos(ctx):
    procesos = []

    intervalo_min = min(v.value for v in ctx["intervalos"].values())
    intervalo_recolector = mp.Value("d", max(0.3, intervalo_min / 2))

    p_recolector = mp.Process(
        target=recolector.run,
        args=(ctx["compartido"], intervalo_recolector, ctx["shutdown_event"]),
        name="recolector",
    )
    procesos.append(p_recolector)

    for tipo in TIPOS:
        modulo = MODULOS[tipo]
        kwargs = {"contador_global": ctx["contador_actualizaciones"]}
        if tipo in ("fds", "threads"):
            kwargs["verbose_value"] = ctx["verbose_value"]
        proc = mp.Process(
            target=modulo.run,
            args=(ctx["intervalos"][tipo], ctx["compartido"], ctx["cola_agregador"], ctx["shutdown_event"]),
            kwargs=kwargs,
            name=f"analizador-{tipo}",
        )
        procesos.append(proc)

    p_agregador = mp.Process(
        target=agregador.run,
        args=(ctx["cola_agregador"], ctx["snapshot"], ctx["shutdown_event"]),
        name="agregador",
    )
    procesos.append(p_agregador)

    return procesos, intervalo_recolector


def _cerrar_todo(procesos, ctx, manager):
    ctx["shutdown_event"].set()
    for p in procesos:
        p.join(timeout=2)
    for p in procesos:
        if p.is_alive():
            p.terminate()
    for p in procesos:
        p.join(timeout=1)
    try:
        manager.shutdown()
    except Exception:
        pass


def _correr_daemon(ctx):
    """Bonus: modo daemon. Corre el backend sin TUI y loggea un resumen del
    snapshot a un archivo cada 2 segundos, hasta recibir SIGINT/SIGTERM."""
    ruta_log = ctx["_ruta_daemon"]
    print(f"[daemon] Corriendo sin TUI. Logueando a {ruta_log}. Ctrl+C para salir.")
    manejador = ctx["manejador_senales"]
    with open(ruta_log, "a", encoding="utf-8") as f:
        while not ctx["shutdown_event"].is_set():
            for signum in manejador.leer_pendientes():
                if signum in (signal_module.SIGINT, signal_module.SIGTERM):
                    ctx["shutdown_event"].set()
                elif signum == signal_module.SIGUSR1:
                    ruta = display.volcar_snapshot(ctx)
                    print(f"[daemon] snapshot volcado en {ruta}")
                elif signum == signal_module.SIGHUP:
                    nueva = cargar_config(ctx["ruta_config"])
                    ctx["config"] = nueva
                    for tipo, valor in ctx["intervalos"].items():
                        default = nueva["intervalos"].get(tipo, {}).get("default")
                        if default:
                            valor.value = default
                    print("[daemon] configuracion recargada")
            if ctx["shutdown_event"].is_set():
                break

            resumen_data = ctx["snapshot"].get("resumen", {}).get("data", {})
            sistema_data = ctx["snapshot"].get("sistema", {}).get("data", {}).get(procfs.CLAVE_GLOBAL, {})
            linea = {
                "ts": time.time(),
                "procesos": len(resumen_data),
                "zombies": sistema_data.get("zombies"),
                "threads_totales": sistema_data.get("total_threads"),
                "load": sistema_data.get("loadavg"),
            }
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
            f.flush()
            time.sleep(2)


def _correr_selftest(ctx):
    print("[selftest] Arrancando backend (sin TUI) por 6 segundos...")
    time.sleep(6)
    print("\n[selftest] Estado del snapshot por tipo:")
    for tipo in TIPOS:
        entrada = ctx["snapshot"].get(tipo, {})
        data = entrada.get("data", {})
        print(f"  - {tipo:12s}: {len(data)} entradas, ts={entrada.get('ts', 0):.2f}")
    resumen_data = ctx["snapshot"].get("resumen", {}).get("data", {})
    if resumen_data:
        algun_pid = next(iter(resumen_data))
        print(f"\n[selftest] Ejemplo de proceso (pid={algun_pid}): {resumen_data[algun_pid]}")
    print(f"\n[selftest] Contador de actualizaciones (7 analizadores incrementando con Lock): "
          f"{ctx['contador_actualizaciones'].value}")
    print("[selftest] OK -- la arquitectura multiproceso funciona de punta a punta.")


def main():
    if sys.platform != "linux":
        print("Este monitor solo funciona en Linux (depende de /proc).", file=sys.stderr)
        sys.exit(1)

    args = parse_args()
    config = cargar_config(args.config)

    manager = mp.Manager()
    ctx = _armar_contexto(args, config, manager)

    procesos, intervalo_recolector = _crear_procesos(ctx)
    for p in procesos:
        p.start()

    manejador = senales_handlers.ManejadorSenales()
    manejador.instalar()
    ctx["manejador_senales"] = manejador

    try:
        if args.selftest:
            _correr_selftest(ctx)
        elif args.daemon:
            ctx["_ruta_daemon"] = args.daemon
            _correr_daemon(ctx)
        else:
            curses.wrapper(display.iniciar, ctx)
    finally:
        _cerrar_todo(procesos, ctx, manager)


if __name__ == "__main__":
    mp.set_start_method("fork", force=True)
    main()
