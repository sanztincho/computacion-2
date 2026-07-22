"""
procfs.py
=========

Helpers para leer y parsear el filesystem /proc de Linux a mano, sin
psutil ni ninguna libreria que abstraiga el acceso al kernel.

Todas las funciones estan separadas en dos capas:
  - funciones `leer_*`  -> abren un archivo real de /proc y devuelven texto/bytes
  - funciones `parsear_*` -> reciben ese texto ya leido y devuelven datos
    estructurados (dicts, listas)

Esta separacion permite testear el parseo (tests/test_procfs.py) sin
depender de que exista un PID real en el sistema donde se corren los tests.
"""

import os
import pwd
import signal as _signal

# Clave que usamos quando un "dato" no es por-proceso sino global al sistema
# (lo usa el analizador de sistema para poder devolver su info con la misma
# forma {clave: {...}} que el resto de los analizadores).
CLAVE_GLOBAL = "global"

# jiffies por segundo del kernel (necesario para transformar utime/stime,
# expresados en "clock ticks", a segundos reales).
CLK_TCK = os.sysconf("SC_CLK_TCK")

ESTADOS = {
    "R": "Ejecutando",
    "S": "Durmiendo (interrumpible)",
    "D": "Espera no interrumpible (I/O)",
    "T": "Detenido (stopped)",
    "t": "Detenido por tracer (ptrace)",
    "Z": "Zombie",
    "X": "Muerto",
    "I": "Idle (kernel thread)",
}

# Ver include/linux/sched.h del kernel para los numeros de politica de scheduling.
SCHED_POLICIES = {
    0: "OTHER",
    1: "FIFO",
    2: "RR",
    3: "BATCH",
    4: "ISO",
    5: "IDLE",
    6: "DEADLINE",
}

# Utilidades de parseo de valores sueltos

def kb(valor):
    """Convierte un valor tipo '1234 kB' (como aparecen en /proc/*/status y
    /proc/meminfo) a un entero de kilobytes. Tolera valores vacios o mal
    formados devolviendo 0."""
    if not valor:
        return 0
    try:
        return int(str(valor).split()[0])
    except (ValueError, IndexError):
        return 0


def primer_entero(valor, default=0):
    """Extrae el primer entero de una cadena tipo '1000 1000 1000 1000'
    (como Uid/Gid en /proc/*/status)."""
    if valor is None:
        return default
    try:
        return int(str(valor).split()[0])
    except (ValueError, IndexError):
        return default


# Tabla de señales (para decodificar las mascaras hexadecimales SigBlk, etc.)

def _construir_tabla_senales():
    tabla = {}
    for i in range(1, 65):
        try:
            tabla[i] = _signal.Signals(i).name
        except ValueError:
            # Señales de tiempo real (RT) u otras sin nombre estandar asignado
            tabla[i] = f"SIGRT{i}"
    return tabla


TABLA_SENALES = _construir_tabla_senales()


def decodificar_mascara_senales(hexstr):
    """Devuelve la lista de nombres de señales activas en la mascara."""
    try:
        mascara = int(str(hexstr), 16)
    except (ValueError, TypeError):
        return []
    activas = []
    for bit in range(64):
        if mascara & (1 << bit):
            numero = bit + 1
            activas.append(TABLA_SENALES.get(numero, f"SIG{numero}"))
    return activas


# Listado de procesos

def listar_pids():
    try:
        return [int(nombre) for nombre in os.listdir("/proc") if nombre.isdigit()]
    except OSError:
        return []


def leer_cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return ""
    if not contenido:
        return ""
    return contenido.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()


# /proc/<pid>/stat

def parsear_stat(contenido):
    """Parsea el contenido de /proc/<pid>/stat (o /proc/<pid>/task/<tid>/stat,
    que tiene el mismo formato).

    El campo 'comm' (nombre del comando) esta entre parentesis y puede
    contener espacios o incluso parentesis balanceados, por eso se ubica
    con index()/rindex() en lugar de un simple split().
    """
    inicio = contenido.index("(")
    fin = contenido.rindex(")")
    pid_str = contenido[:inicio].strip()
    comm = contenido[inicio + 1:fin]
    resto = contenido[fin + 1:].strip().split()

    campos = {
        "pid": int(pid_str),
        "comm": comm,
        # A partir de aca, resto[i] corresponde al campo (i+3) de proc(5),
        # porque los campos 1 y 2 (pid, comm) ya se sacaron aparte.
        "state": resto[0],
        "ppid": int(resto[1]),
        "pgrp": int(resto[2]),
        "session": int(resto[3]),
        "tty_nr": int(resto[4]),
        "tpgid": int(resto[5]),
        "flags": int(resto[6]),
        "minflt": int(resto[7]),
        "cminflt": int(resto[8]),
        "majflt": int(resto[9]),
        "cmajflt": int(resto[10]),
        "utime": int(resto[11]),
        "stime": int(resto[12]),
        "cutime": int(resto[13]),
        "cstime": int(resto[14]),
        "priority": int(resto[15]),
        "nice": int(resto[16]),
        "num_threads": int(resto[17]),
        "itrealvalue": int(resto[18]),
        "starttime": int(resto[19]),
        "vsize": int(resto[20]),
        "rss": int(resto[21]),
    }
    # rt_priority (campo 40) y policy (campo 41) -> indices 37 y 38 en 'resto'
    if len(resto) > 38:
        campos["rt_priority"] = int(resto[37])
        campos["policy"] = int(resto[38])
    else:
        campos["rt_priority"] = 0
        campos["policy"] = 0
    return campos


def leer_stat(pid):
    with open(f"/proc/{pid}/stat", "r") as f:
        return parsear_stat(f.read())


# /proc/<pid>/status

def parsear_status(contenido):
    datos = {}
    for linea in contenido.splitlines():
        if ":" not in linea:
            continue
        clave, _, valor = linea.partition(":")
        datos[clave.strip()] = valor.strip()
    return datos


def leer_status(pid):
    with open(f"/proc/{pid}/status", "r") as f:
        return parsear_status(f.read())


# /proc/<pid>/maps

def parsear_maps(contenido):
    mapeos = []
    for linea in contenido.splitlines():
        partes = linea.split(None, 5)
        if len(partes) < 5:
            continue
        rango, perms, _offset, _dev, _inode = partes[:5]
        pathname = partes[5].strip() if len(partes) > 5 else ""
        try:
            ini_str, fin_str = rango.split("-")
            inicio, fin = int(ini_str, 16), int(fin_str, 16)
        except ValueError:
            continue
        mapeos.append({
            "inicio": inicio, "fin": fin, "tam": fin - inicio,
            "perms": perms, "pathname": pathname,
        })
    return mapeos


def leer_maps(pid):
    try:
        with open(f"/proc/{pid}/maps", "r") as f:
            return parsear_maps(f.read())
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return []


def agrupar_segmentos(mapeos):
    """Agrupa los mappings de memoria de un proceso en categorias legibles,
    sumando bytes por categoria: texto, datos, heap, pila, compartido, otro."""
    grupos = {"texto": 0, "datos": 0, "heap": 0, "pila": 0, "compartido": 0, "otro": 0}
    for m in mapeos:
        p = m["pathname"]
        perms = m["perms"]
        if p == "[heap]":
            grupos["heap"] += m["tam"]
        elif p.startswith("[stack"):
            grupos["pila"] += m["tam"]
        elif p in ("[vdso]", "[vvar]", "[vsyscall]"):
            grupos["otro"] += m["tam"]
        elif ".so" in p:
            grupos["compartido"] += m["tam"]
        elif p and "x" in perms:
            grupos["texto"] += m["tam"]
        else:
            grupos["datos"] += m["tam"]
    return grupos


# /proc/<pid>/fd/*

def clasificar_fd(destino):
    if destino.startswith("socket:["):
        return "socket"
    if destino.startswith("pipe:["):
        return "pipe"
    if destino.startswith("anon_inode:"):
        return "anon_inode"
    if destino.startswith("/dev/pts/") or destino.startswith("/dev/tty"):
        return "tty"
    if destino == "?":
        return "desconocido"
    return "archivo"


def listar_fds(pid):
    base = f"/proc/{pid}/fd"
    resultado = []
    try:
        entradas = os.listdir(base)
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return resultado
    for fd in entradas:
        try:
            destino = os.readlink(f"{base}/{fd}")
        except OSError:
            destino = "?"
        try:
            numero_fd = int(fd)
        except ValueError:
            continue
        resultado.append({"fd": numero_fd, "destino": destino, "tipo": clasificar_fd(destino)})
    return sorted(resultado, key=lambda x: x["fd"])


# /proc/<pid>/task/<tid>/*  (threads / LWPs)

def listar_threads(pid):
    try:
        return sorted(int(t) for t in os.listdir(f"/proc/{pid}/task"))
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return []


def leer_task_comm(pid, tid):
    try:
        with open(f"/proc/{pid}/task/{tid}/comm", "r") as f:
            return f.read().strip()
    except OSError:
        return "?"


def leer_task_stat(pid, tid):
    try:
        with open(f"/proc/{pid}/task/{tid}/stat", "r") as f:
            return parsear_stat(f.read())
    except (OSError, ValueError):
        return None


def leer_task_status(pid, tid):
    try:
        with open(f"/proc/{pid}/task/{tid}/status", "r") as f:
            return parsear_status(f.read())
    except OSError:
        return {}


# Datos globales del sistema

def parsear_stat_global(contenido):
    resultado = {"cpu": {}}
    claves_cpu = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal", "guest", "guest_nice"]
    for linea in contenido.splitlines():
        if linea.startswith("cpu "):
            partes = linea.split()[1:]
            resultado["cpu"] = {claves_cpu[i]: int(partes[i]) for i in range(min(len(claves_cpu), len(partes)))}
        elif linea.startswith("btime"):
            resultado["btime"] = int(linea.split()[1])
        elif linea.startswith("processes"):
            resultado["processes_creados"] = int(linea.split()[1])
    return resultado


def leer_stat_global():
    with open("/proc/stat", "r") as f:
        return parsear_stat_global(f.read())


def calcular_cpu_global_pct(anterior, actual):
    """Calcula el % de CPU global (user/system/idle/iowait/...) a partir de
    dos lecturas de /proc/stat, usando el delta de jiffies de cada campo
    sobre el delta total (la tecnica clasica que usa top/htop)."""
    claves = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"]
    deltas = {k: actual.get(k, 0) - anterior.get(k, 0) for k in claves}
    total = sum(deltas.values())
    if total <= 0:
        return {k: 0.0 for k in claves}
    return {k: round(100.0 * v / total, 1) for k, v in deltas.items()}


def leer_loadavg():
    with open("/proc/loadavg", "r") as f:
        partes = f.read().split()
    ejec, total_kernel = partes[3].split("/")
    return {
        "load1": float(partes[0]), "load5": float(partes[1]), "load15": float(partes[2]),
        "en_ejecucion": int(ejec), "total_procs_kernel": int(total_kernel),
    }


def leer_meminfo():
    datos = {}
    with open("/proc/meminfo", "r") as f:
        for linea in f:
            clave, _, valor = linea.partition(":")
            datos[clave.strip()] = kb(valor.strip())
    return datos


def leer_uptime():
    with open("/proc/uptime", "r") as f:
        return float(f.read().split()[0])


# Usuarios

_cache_usuarios = {}


def nombre_usuario(uid):
    if uid in _cache_usuarios:
        return _cache_usuarios[uid]
    try:
        nombre = pwd.getpwuid(uid).pw_name
    except (KeyError, OverflowError):
        nombre = str(uid)
    _cache_usuarios[uid] = nombre
    return nombre


# Calculo de %CPU por proceso/thread (delta de jiffies entre dos lecturas)

def calcular_cpu_pct(utime_prev, stime_prev, t_prev, utime_now, stime_now, t_now):
    delta_ticks = (utime_now - utime_prev) + (stime_now - stime_prev)
    delta_tiempo = t_now - t_prev
    if delta_tiempo <= 0:
        return 0.0
    return 100.0 * (delta_ticks / CLK_TCK) / delta_tiempo
