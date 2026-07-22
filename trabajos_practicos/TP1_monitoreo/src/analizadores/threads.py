"""
analizadores/threads.py

Vista 4 (Threads / LWPs): lista de threads de cada proceso
(/proc/<pid>/task/<tid>), su estado, nombre (comm), %CPU individual y
context switches. Estos threads son "Light Weight Processes" para el
kernel: comparten el mismo PID a nivel de proceso pero cada uno tiene un
TID propio -- esto se ve muy claro comparando esta vista con la de
Resumen (donde solo aparece un PID por proceso).
"""

import time

import procfs
from analizadores import base

_cache_cpu_hilos = {}  # (pid, tid) -> (utime, stime, timestamp)


def extraer(pids, verbose_value=None, **_kwargs):
    limite = 200 if (verbose_value is not None and verbose_value.value) else 40
    resultado = {}
    ahora = time.time()
    vivos = set()

    for pid in pids:
        tids = procfs.listar_threads(pid)
        lista = []
        for tid in tids:
            st = procfs.leer_task_stat(pid, tid)
            if st is None:
                continue
            vivos.add((pid, tid))
            status_t = procfs.leer_task_status(pid, tid)

            anterior = _cache_cpu_hilos.get((pid, tid))
            cpu_pct = 0.0
            if anterior is not None:
                cpu_pct = procfs.calcular_cpu_pct(
                    anterior[0], anterior[1], anterior[2],
                    st["utime"], st["stime"], ahora,
                )
            _cache_cpu_hilos[(pid, tid)] = (st["utime"], st["stime"], ahora)

            lista.append({
                "tid": tid,
                "nombre": procfs.leer_task_comm(pid, tid),
                "estado": st["state"],
                "cpu_pct": round(cpu_pct, 1),
                "ctx_vol": procfs.primer_entero(status_t.get("voluntary_ctxt_switches"), 0),
                "ctx_invol": procfs.primer_entero(status_t.get("nonvoluntary_ctxt_switches"), 0),
            })

        resultado[pid] = {
            "cantidad": len(lista),
            "hilos": lista[:limite],
            "truncado": len(lista) > limite,
        }

    for clave in list(_cache_cpu_hilos.keys()):
        if clave not in vivos:
            del _cache_cpu_hilos[clave]

    return resultado


def run(intervalo_value, compartido, cola_salida, shutdown_event, contador_global=None, verbose_value=None, **_kwargs):
    base.ejecutar_loop("threads", intervalo_value, compartido, cola_salida,
                        shutdown_event, extraer, contador_global=contador_global,
                        verbose_value=verbose_value)
