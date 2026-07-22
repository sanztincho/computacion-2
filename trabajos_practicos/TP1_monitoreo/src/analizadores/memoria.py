"""
analizadores/memoria.py

Vista 2 (Memoria): VmSize/VmRSS/VmHWM/VmSwap/etc. desde /proc/<pid>/status,
minor/major page faults desde /proc/<pid>/stat, y segmentos de memoria
agrupados (texto/datos/heap/pila/compartido) desde /proc/<pid>/maps.
"""

import procfs
from analizadores import base


def extraer(pids, **_kwargs):
    resultado = {}
    for pid in pids:
        try:
            status = procfs.leer_status(pid)
            stat = procfs.leer_stat(pid)
        except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
            continue

        mapeos = procfs.leer_maps(pid)
        segmentos = procfs.agrupar_segmentos(mapeos)

        resultado[pid] = {
            "vmsize": procfs.kb(status.get("VmSize")),
            "vmrss": procfs.kb(status.get("VmRSS")),
            "vmdata": procfs.kb(status.get("VmData")),
            "vmstk": procfs.kb(status.get("VmStk")),
            "vmexe": procfs.kb(status.get("VmExe")),
            "vmlib": procfs.kb(status.get("VmLib")),
            "vmhwm": procfs.kb(status.get("VmHWM")),
            "vmswap": procfs.kb(status.get("VmSwap")),
            "minflt": stat["minflt"],
            "majflt": stat["majflt"],
            "cminflt": stat["cminflt"],
            "cmajflt": stat["cmajflt"],
            "segmentos": segmentos,
            "num_mappings": len(mapeos),
        }
    return resultado


def run(intervalo_value, compartido, cola_salida, shutdown_event, contador_global=None, **_kwargs):
    base.ejecutar_loop("memoria", intervalo_value, compartido, cola_salida,
                        shutdown_event, extraer, contador_global=contador_global)
