"""
analizadores/fds.py

Vista 3 (File Descriptors): lista de FDs abiertos por proceso, su destino
(via readlink de /proc/<pid>/fd/<n>) y un tipo inferido (socket/pipe/tty/
archivo/anon_inode).

En modo verbose (SIGUSR2) se muestran mas FDs por proceso en el detalle.
"""

import procfs
from analizadores import base

LIMITE_NORMAL = 25
LIMITE_VERBOSE = 300


def extraer(pids, verbose_value=None, **_kwargs):
    limite = LIMITE_VERBOSE if (verbose_value is not None and verbose_value.value) else LIMITE_NORMAL
    resultado = {}
    for pid in pids:
        fds = procfs.listar_fds(pid)
        por_tipo = {}
        for f in fds:
            por_tipo[f["tipo"]] = por_tipo.get(f["tipo"], 0) + 1
        resultado[pid] = {
            "cantidad": len(fds),
            "detalle": fds[:limite],
            "truncado": len(fds) > limite,
            "por_tipo": por_tipo,
        }
    return resultado


def run(intervalo_value, compartido, cola_salida, shutdown_event, contador_global=None, verbose_value=None, **_kwargs):
    base.ejecutar_loop("fds", intervalo_value, compartido, cola_salida,
                        shutdown_event, extraer, contador_global=contador_global,
                        verbose_value=verbose_value)
