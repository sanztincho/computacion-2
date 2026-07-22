"""
analizadores/senales.py

Vista 5 (Señales): decodifica las mascaras hexadecimales de 64 bits que
expone /proc/<pid>/status (SigBlk, SigIgn, SigCgt, SigPnd, ShdPnd) a
nombres de señal legibles (SIGINT, SIGTERM, etc.), usando
procfs.decodificar_mascara_senales().

Nota importante: este archivo es el ANALIZADOR de la vista de señales. 
El manejo de señales *del propio monitor*
(SIGINT/SIGTERM/SIGHUP/SIGUSR1/SIGUSR2/SIGWINCH) vive en src/senales.py,
un modulo distinto con otra responsabilidad.
"""

import procfs
from analizadores import base


def extraer(pids, **_kwargs):
    resultado = {}
    for pid in pids:
        try:
            status = procfs.leer_status(pid)
        except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
            continue
        if not status:
            continue
        resultado[pid] = {
            "bloqueadas": procfs.decodificar_mascara_senales(status.get("SigBlk", "0")),
            "ignoradas": procfs.decodificar_mascara_senales(status.get("SigIgn", "0")),
            "con_handler": procfs.decodificar_mascara_senales(status.get("SigCgt", "0")),
            "pendientes_proceso": procfs.decodificar_mascara_senales(status.get("SigPnd", "0")),
            "pendientes_grupo": procfs.decodificar_mascara_senales(status.get("ShdPnd", "0")),
        }
    return resultado


def run(intervalo_value, compartido, cola_salida, shutdown_event, contador_global=None, **_kwargs):
    base.ejecutar_loop("senales", intervalo_value, compartido, cola_salida,
                        shutdown_event, extraer, contador_global=contador_global)
