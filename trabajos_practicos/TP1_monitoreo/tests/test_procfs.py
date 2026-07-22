"""
tests/test_procfs.py

Tests unitarios de las funciones de PARSEO de procfs.py (las que reciben
texto ya leido, no las que abren archivos de /proc). Esto permite
testear la logica de parseo sin depender de que exista un PID real ni
de que el entorno donde corren los tests sea exactamente igual al del
contenedor Docker del TP.

Correr con:  python3 -m pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import procfs  # noqa: E402


def test_parsear_stat_basico():
    # Proceso comun, comm sin espacios ni parentesis.
    linea = "1234 (bash) S 1 1234 1234 34816 1234 4194304 100 0 0 0 50 20 0 0 20 0 1 0 999 " \
            "10000000 500 18446744073709551615 1 1 0 0 0 0 0 0 0 0 0 0 17 0 0 0 0 0 0 " \
            "0 0 0 0 0 0 0"
    datos = procfs.parsear_stat(linea)
    assert datos["pid"] == 1234
    assert datos["comm"] == "bash"
    assert datos["state"] == "S"
    assert datos["ppid"] == 1
    assert datos["utime"] == 50
    assert datos["stime"] == 20
    assert datos["priority"] == 20
    assert datos["nice"] == 0
    assert datos["num_threads"] == 1


def test_parsear_stat_comm_con_espacios_y_parentesis():
    # comm puede tener espacios y parentesis balanceados, ej: "(my (weird) prog)"
    # Se arma 'resto' con exactamente 50 campos (campos 3 a 52 de proc(5))
    # para que rt_priority (campo 40, indice 37) y policy (campo 41,
    # indice 38) caigan en la posicion real.
    resto = ["0"] * 50
    resto[0] = "R"        # state
    resto[1] = "1"        # ppid
    resto[11] = "5"       # utime
    resto[12] = "3"       # stime
    resto[15] = "20"      # priority
    resto[17] = "2"       # num_threads
    resto[37] = "20"      # rt_priority
    resto[38] = "5"       # policy
    linea = "55 (my (weird) prog) " + " ".join(resto)
    datos = procfs.parsear_stat(linea)
    assert datos["comm"] == "my (weird) prog"
    assert datos["state"] == "R"
    assert datos["rt_priority"] == 20
    assert datos["policy"] == 5


def test_parsear_status():
    contenido = (
        "Name:\tbash\n"
        "State:\tS (sleeping)\n"
        "Uid:\t1000\t1000\t1000\t1000\n"
        "Threads:\t1\n"
        "VmRSS:\t   4096 kB\n"
    )
    datos = procfs.parsear_status(contenido)
    assert datos["Name"] == "bash"
    assert procfs.primer_entero(datos["Uid"]) == 1000
    assert procfs.kb(datos["VmRSS"]) == 4096


def test_decodificar_mascara_senales():
    # bit 0 -> señal 1 (SIGHUP), bit 1 -> señal 2 (SIGINT)
    mascara = hex((1 << 0) | (1 << 1))  # 0x3
    nombres = procfs.decodificar_mascara_senales(mascara.replace("0x", ""))
    assert "SIGHUP" in nombres
    assert "SIGINT" in nombres
    assert len(nombres) == 2


def test_decodificar_mascara_vacia():
    assert procfs.decodificar_mascara_senales("0") == []
    assert procfs.decodificar_mascara_senales("") == []


def test_agrupar_segmentos():
    mapeos = [
        {"inicio": 0, "fin": 4096, "tam": 4096, "perms": "r-xp", "pathname": "/usr/bin/bash"},
        {"inicio": 4096, "fin": 8192, "tam": 4096, "perms": "rw-p", "pathname": "[heap]"},
        {"inicio": 8192, "fin": 12288, "tam": 4096, "perms": "rw-p", "pathname": "[stack]"},
        {"inicio": 12288, "fin": 16384, "tam": 4096, "perms": "r-xp", "pathname": "/lib/libc.so.6"},
        {"inicio": 16384, "fin": 20480, "tam": 4096, "perms": "rw-p", "pathname": ""},
    ]
    grupos = procfs.agrupar_segmentos(mapeos)
    assert grupos["texto"] == 4096
    assert grupos["heap"] == 4096
    assert grupos["pila"] == 4096
    assert grupos["compartido"] == 4096
    assert grupos["datos"] == 4096


def test_clasificar_fd():
    assert procfs.clasificar_fd("socket:[12345]") == "socket"
    assert procfs.clasificar_fd("pipe:[6789]") == "pipe"
    assert procfs.clasificar_fd("anon_inode:[eventfd]") == "anon_inode"
    assert procfs.clasificar_fd("/dev/pts/3") == "tty"
    assert procfs.clasificar_fd("/home/user/archivo.txt") == "archivo"
    assert procfs.clasificar_fd("?") == "desconocido"


def test_parsear_maps():
    contenido = (
        "00400000-00452000 r-xp 00000000 08:01 123456 /usr/bin/bash\n"
        "7f0000000000-7f0000021000 rw-p 00000000 00:00 0 [heap]\n"
    )
    mapeos = procfs.parsear_maps(contenido)
    assert len(mapeos) == 2
    assert mapeos[0]["pathname"] == "/usr/bin/bash"
    assert mapeos[0]["tam"] == 0x00452000 - 0x00400000
    assert mapeos[1]["pathname"] == "[heap]"


def test_calcular_cpu_pct():
    # 100 ticks de diferencia (utime+stime) en 1 segundo real, con CLK_TCK
    # ticks por segundo -> deberia dar 100% de un core.
    delta_ticks_para_100pct = procfs.CLK_TCK
    pct = procfs.calcular_cpu_pct(0, 0, 0.0, delta_ticks_para_100pct, 0, 1.0)
    assert abs(pct - 100.0) < 0.01


def test_calcular_cpu_global_pct():
    anterior = {"user": 100, "nice": 0, "system": 50, "idle": 850, "iowait": 0, "irq": 0, "softirq": 0, "steal": 0}
    actual = {"user": 150, "nice": 0, "system": 60, "idle": 950, "iowait": 0, "irq": 0, "softirq": 0, "steal": 0}
    pct = procfs.calcular_cpu_global_pct(anterior, actual)
    # delta total = 50 (user) + 10 (system) + 100 (idle) = 160
    assert abs(pct["user"] - (50 / 160 * 100)) < 0.1
    assert abs(pct["idle"] - (100 / 160 * 100)) < 0.1


def test_sched_policies_conocidas():
    assert procfs.SCHED_POLICIES[0] == "OTHER"
    assert procfs.SCHED_POLICIES[1] == "FIFO"
    assert procfs.SCHED_POLICIES[2] == "RR"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
