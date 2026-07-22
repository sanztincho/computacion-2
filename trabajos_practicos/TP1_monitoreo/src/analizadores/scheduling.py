"""
analizadores/scheduling.py

Vista 6 (Scheduling): nice, priority, politica de scheduling (OTHER/FIFO/
RR/BATCH/IDLE), RT priority, afinidad de CPU, context switches voluntarios
e involuntarios, utime/stime, sesion (SID) y grupo de procesos (PGID).
"""

import procfs
from analizadores import base


def extraer(pids, **_kwargs):
    resultado = {}
    for pid in pids:
        try:
            stat = procfs.leer_stat(pid)
            status = procfs.leer_status(pid)
        except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
            continue

        resultado[pid] = {
            "nice": stat["nice"],
            "priority": stat["priority"],
            "rt_priority": stat["rt_priority"],
            "policy_num": stat["policy"],
            "policy": procfs.SCHED_POLICIES.get(stat["policy"], f"desconocida({stat['policy']})"),
            "cpus_allowed": status.get("Cpus_allowed_list", "?"),
            "ctx_vol": procfs.primer_entero(status.get("voluntary_ctxt_switches"), 0),
            "ctx_invol": procfs.primer_entero(status.get("nonvoluntary_ctxt_switches"), 0),
            "utime": stat["utime"],
            "stime": stat["stime"],
            "sid": stat["session"],
            "pgid": stat["pgrp"],
        }
    return resultado


def run(intervalo_value, compartido, cola_salida, shutdown_event, contador_global=None, **_kwargs):
    base.ejecutar_loop("scheduling", intervalo_value, compartido, cola_salida,
                        shutdown_event, extraer, contador_global=contador_global)
