"""
analizadores/sistema.py

Vista 7 (Sistema global): CPU global (user/system/idle/iowait), load
average, memoria total/libre/buffers/cached/swap, cantidad de procesos
totales / por estado / threads totales / zombies, boot time y uptime.

Los "top 3 por CPU y por memoria" NO se calculan aca: 
se derivan en el momento de dibujar la vista, en display.py, leyendo
directamente los datos ya publicados por los analizadores de "resumen" y
"memoria" en el snapshot global.Hacerlo asi es mejor porque el
top-3 es, literalmente, "derivar del snapshot"
y evita que este analizador dependa de los resultados de otros
analizadores.
"""

import time

import procfs
from analizadores import base

_cache_cpu_global = None  # (dict de /proc/stat linea 'cpu', timestamp)


def extraer(pids, **_kwargs):
    global _cache_cpu_global

    stat_global = procfs.leer_stat_global()
    cpu_pct = {}
    if _cache_cpu_global is not None:
        anterior_cpu, _t_prev = _cache_cpu_global
        cpu_pct = procfs.calcular_cpu_global_pct(anterior_cpu, stat_global["cpu"])
    _cache_cpu_global = (stat_global["cpu"], time.time())

    conteo_estados = {}
    total_threads = 0
    zombies = 0
    for pid in pids:
        try:
            st = procfs.leer_stat(pid)
        except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
            continue
        estado = st["state"]
        conteo_estados[estado] = conteo_estados.get(estado, 0) + 1
        total_threads += st["num_threads"]
        if estado == "Z":
            zombies += 1

    datos = {
        "cpu_pct": cpu_pct,
        "loadavg": procfs.leer_loadavg(),
        "meminfo": procfs.leer_meminfo(),
        "uptime": procfs.leer_uptime(),
        "btime": stat_global.get("btime", 0),
        "total_procesos": len(pids),
        "total_threads": total_threads,
        "zombies": zombies,
        "por_estado": conteo_estados,
    }
    return {procfs.CLAVE_GLOBAL: datos}


def run(intervalo_value, compartido, cola_salida, shutdown_event, contador_global=None, **_kwargs):
    base.ejecutar_loop("sistema", intervalo_value, compartido, cola_salida,
                        shutdown_event, extraer, contador_global=contador_global)
