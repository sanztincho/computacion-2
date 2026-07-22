"""
analizadores/resumen.py

Vista 1 (Resumen): PID, PPID, usuario, estado, %CPU, comando, cantidad de
threads. Es la vista "tipo htop clasico".

El %CPU se calcula con el clasico delta de jiffies entre dos lecturas de
utime+stime (campos 14-15 de /proc/<pid>/stat), por eso este modulo
mantiene un cache propio (_cache_cpu) entre ciclos: como cada analizador
es un proceso independiente y de larga vida, el cache vive tranquilo en
sus variables globales sin necesidad de compartirlo con nadie mas.
"""

import time

import procfs
from analizadores import base

_cache_cpu = {}  # pid -> (utime, stime, timestamp) de la lectura anterior


def extraer(pids, **_kwargs):
    resultado = {}
    ahora = time.time()

    for pid in pids:
        try:
            stat = procfs.leer_stat(pid)
            status = procfs.leer_status(pid)
        except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
            continue

        uid = procfs.primer_entero(status.get("Uid"), 0)
        anterior = _cache_cpu.get(pid)
        cpu_pct = 0.0
        if anterior is not None:
            cpu_pct = procfs.calcular_cpu_pct(
                anterior[0], anterior[1], anterior[2],
                stat["utime"], stat["stime"], ahora,
            )
        _cache_cpu[pid] = (stat["utime"], stat["stime"], ahora)

        comando = procfs.leer_cmdline(pid) or f"[{stat['comm']}]"

        resultado[pid] = {
            "ppid": stat["ppid"],
            "uid": uid,
            "usuario": procfs.nombre_usuario(uid),
            "estado": stat["state"],
            "estado_desc": procfs.ESTADOS.get(stat["state"], stat["state"]),
            "comm": stat["comm"],
            "comando": comando,
            "cpu_pct": round(cpu_pct, 1),
            "threads": procfs.primer_entero(status.get("Threads"), 1),
        }

    # Limpiar del cache los pids que ya no existen (evita perdida de
    # memoria lenta y hace que, si el pid se reusa, no arrastre jiffies
    # de un proceso viejo distinto).
    vivos = set(pids)
    for pid_viejo in list(_cache_cpu.keys()):
        if pid_viejo not in vivos:
            del _cache_cpu[pid_viejo]

    return resultado


def run(intervalo_value, compartido, cola_salida, shutdown_event, contador_global=None, **_kwargs):
    base.ejecutar_loop("resumen", intervalo_value, compartido, cola_salida,
                        shutdown_event, extraer, contador_global=contador_global)
