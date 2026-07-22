"""
display.py
===========

La Interfaz de Texto (TUI), implementada con `curses` (stdlib, sin
dependencias externas). Corre en el PROCESO PRINCIPAL (no es un proceso
hijo separado): este modulo es el mas complejo y el que maneja todo 
-- lee el snapshot que arma el Agregador, dibuja la vista activa, 
atiende el teclado y procesa lasseñales que le llegan al monitor via el self-pipe de senales.py.

Estructura de la pantalla (siempre igual, cambia el panel de detalle):

    fila 0        : encabezado (titulo, vista activa, intervalo, reloj)
    filas 1..N    : lista de procesos (comun a las 7 vistas)
    filas N+1..M  : panel de detalle especifico de la vista activa
    ultima fila   : barra de estado / ayuda rapida / ultimo mensaje
"""

import curses
import json
import os
import signal
import time
from collections import deque

import procfs

VISTAS = [
    ("resumen", "1", "r", "Resumen"),
    ("memoria", "2", "m", "Memoria"),
    ("fds", "3", "f", "File Descriptors"),
    ("threads", "4", "t", "Threads"),
    ("senales", "5", "s", "Señales"),
    ("scheduling", "6", "p", "Scheduling"),
    ("sistema", "7", "g", "Sistema Global"),
]

_TECLA_A_VISTA = {}
for _tipo, _n, _letra, _titulo in VISTAS:
    _TECLA_A_VISTA[ord(_n)] = _tipo
    _TECLA_A_VISTA[ord(_letra)] = _tipo

_TITULOS = {t: titulo for t, _n, _l, titulo in VISTAS}

ORDENES = ["cpu", "rss", "pid"]


class EstadoTUI:
    def __init__(self, config):
        self.vista_activa = "resumen"
        self.seleccion = 0
        self.pin = None
        self.filtro_cmd = config.get("filtro_default", "") or ""
        self.filtro_usuario = config.get("usuario_default", "") or ""
        self.orden = config.get("orden_default", "cpu") or "cpu"
        self.mostrar_ayuda = False
        self.mensaje = ("", 0.0)
        self.salir = False


# Entrada principal (llamada por curses.wrapper desde main.py)

def iniciar(stdscr, ctx):
    curses.curs_set(0)
    stdscr.timeout(150)
    _configurar_colores()

    estado = EstadoTUI(ctx["config"])

    while not ctx["shutdown_event"].is_set():
        for signum in ctx["manejador_senales"].leer_pendientes():
            _procesar_senal(signum, ctx, estado)
            if ctx["shutdown_event"].is_set():
                break
        if ctx["shutdown_event"].is_set():
            break

        try:
            _dibujar(stdscr, ctx, estado)
        except curses.error:
            pass

        try:
            tecla = stdscr.getch()
        except curses.error:
            tecla = -1

        if tecla != -1:
            _manejar_tecla(tecla, ctx, estado, stdscr)
            if estado.salir:
                ctx["shutdown_event"].set()
                break


def _configurar_colores():
    curses.start_color()
    try:
        curses.use_default_colors()
        fondo = -1
    except curses.error:
        fondo = curses.COLOR_BLACK
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)   # fila seleccionada
    curses.init_pair(2, curses.COLOR_GREEN, fondo)               # running / ok
    curses.init_pair(3, curses.COLOR_YELLOW, fondo)              # warning / sleeping
    curses.init_pair(4, curses.COLOR_RED, fondo)                 # zombie / critico
    curses.init_pair(5, curses.COLOR_CYAN, fondo)                # titulos
    curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE)   # encabezado


# Manejo de señales (llega desde el self-pipe de src/senales.py)

def _procesar_senal(signum, ctx, estado):
    ahora = time.time()
    try:
        nombre_senal = signal.Signals(signum).name
    except ValueError:
        nombre_senal = f"SIG{signum}"
    ctx["ultimas_senales"].appendleft((nombre_senal, ahora))

    if signum in (signal.SIGINT, signal.SIGTERM):
        estado.mensaje = ("Señal de terminación recibida, cerrando de forma limpia...", ahora)
        ctx["shutdown_event"].set()
    elif signum == signal.SIGHUP:
        _recargar_configuracion(ctx, estado)
        estado.mensaje = ("Configuración recargada desde " + ctx["ruta_config"], ahora)
    elif signum == signal.SIGUSR1:
        ruta = volcar_snapshot(ctx)
        estado.mensaje = (f"Snapshot volcado en {ruta}", ahora)
    elif signum == signal.SIGUSR2:
        with ctx["verbose_value"].get_lock():
            ctx["verbose_value"].value = 0 if ctx["verbose_value"].value else 1
        modo = "ON" if ctx["verbose_value"].value else "OFF"
        estado.mensaje = (f"Modo verbose: {modo}", ahora)
    elif signum == signal.SIGWINCH:
        try:
            curses.update_lines_cols()
        except curses.error:
            pass
        estado.mensaje = ("Terminal redimensionada", ahora)


def _recargar_configuracion(ctx, estado):
    from configuracion import cargar_config
    nueva = cargar_config(ctx["ruta_config"])
    ctx["config"] = nueva
    for tipo, valor in ctx["intervalos"].items():
        default = nueva["intervalos"].get(tipo, {}).get("default")
        if default:
            valor.value = default
    estado.filtro_cmd = nueva.get("filtro_default", "") or ""
    estado.filtro_usuario = nueva.get("usuario_default", "") or ""
    estado.orden = nueva.get("orden_default", "cpu") or "cpu"


def volcar_snapshot(ctx):
    """Handler de SIGUSR1: vuelca snapshot actual a dump_<timestamp>.json"""
    ts = time.strftime("%Y%m%d_%H%M%S")
    nombre = f"dump_{ts}.json"
    directorio = ctx.get("dir_dumps", ".") or "."
    try:
        os.makedirs(directorio, exist_ok=True)
    except OSError:
        directorio = "."
    ruta = os.path.join(directorio, nombre)

    plano = {}
    try:
        items = list(ctx["snapshot"].items())
    except (BrokenPipeError, EOFError, OSError):
        items = []

    for tipo, contenido in items:
        datos = contenido.get("data", {}) if isinstance(contenido, dict) else {}
        datos_str = {str(k): v for k, v in datos.items()}
        plano[tipo] = {"ts": contenido.get("ts", 0) if isinstance(contenido, dict) else 0, "data": datos_str}

    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(plano, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
    return ruta


# Teclado

def _manejar_tecla(tecla, ctx, estado, stdscr):
    if estado.mostrar_ayuda:
        estado.mostrar_ayuda = False
        return

    if tecla in _TECLA_A_VISTA:
        estado.vista_activa = _TECLA_A_VISTA[tecla]
        estado.seleccion = 0
        return

    if tecla == curses.KEY_UP:
        estado.seleccion = max(0, estado.seleccion - 1)
        return
    if tecla == curses.KEY_DOWN:
        estado.seleccion += 1
        return
    if tecla in (curses.KEY_ENTER, 10, 13):
        filas = _construir_filas(ctx, estado)
        if filas:
            idx = min(estado.seleccion, len(filas) - 1)
            pid_actual = filas[idx]["pid"]
            estado.pin = None if estado.pin == pid_actual else pid_actual
        return

    try:
        ch = chr(tecla)
    except ValueError:
        return

    if ch == "/":
        estado.filtro_cmd = _pedir_texto(stdscr, "Filtrar por comando: ")
        estado.seleccion = 0
    elif ch == "u":
        estado.filtro_usuario = _pedir_texto(stdscr, "Filtrar por usuario: ")
        estado.seleccion = 0
    elif ch == "c":
        idx = ORDENES.index(estado.orden) if estado.orden in ORDENES else 0
        estado.orden = ORDENES[(idx + 1) % len(ORDENES)]
    elif ch in ("+", "="):
        _ajustar_intervalo(ctx, estado, +1)
    elif ch == "-":
        _ajustar_intervalo(ctx, estado, -1)
    elif ch == "q":
        estado.salir = True
    elif ch in ("h", "?"):
        estado.mostrar_ayuda = True


def _ajustar_intervalo(ctx, estado, direccion):
    tipo = estado.vista_activa
    valor = ctx["intervalos"][tipo]
    minimo = ctx["config"]["intervalos"].get(tipo, {}).get("min", 0.5)
    paso = 0.5
    nuevo = round(valor.value + direccion * paso, 2)
    valor.value = max(minimo, nuevo)


def _pedir_texto(stdscr, prompt):
    alto, _ancho = stdscr.getmaxyx()
    fila = alto - 1
    try:
        stdscr.move(fila, 0)
        stdscr.clrtoeol()
        stdscr.addstr(fila, 0, prompt)
        curses.echo()
        curses.curs_set(1)
        stdscr.timeout(-1)
        texto = stdscr.getstr(fila, len(prompt), 60).decode("utf-8", errors="ignore")
    except curses.error:
        texto = ""
    finally:
        curses.noecho()
        curses.curs_set(0)
        stdscr.timeout(150)
    return texto.strip()


# Construccion de filas (lista de procesos) a partir del snapshot

def _obtener_dato(ctx, tipo):
    try:
        entrada = ctx["snapshot"].get(tipo)
    except (BrokenPipeError, EOFError, OSError):
        return {}, 0.0
    if not entrada:
        return {}, 0.0
    return entrada.get("data", {}), entrada.get("ts", 0.0)


def _construir_filas(ctx, estado):
    resumen_data, _ = _obtener_dato(ctx, "resumen")
    memoria_data, _ = _obtener_dato(ctx, "memoria")

    filas = []
    for pid, info in resumen_data.items():
        fila = dict(info)
        fila["pid"] = pid
        fila["vmrss_kb"] = memoria_data.get(pid, {}).get("vmrss", 0)
        filas.append(fila)

    filtro_cmd = (estado.filtro_cmd or "").lower()
    filtro_usr = (estado.filtro_usuario or "").lower()
    if filtro_cmd:
        filas = [f for f in filas if filtro_cmd in f.get("comando", "").lower()
                 or filtro_cmd in f.get("comm", "").lower()]
    if filtro_usr:
        filas = [f for f in filas if filtro_usr in f.get("usuario", "").lower()]

    if estado.orden == "cpu":
        filas.sort(key=lambda f: f.get("cpu_pct", 0), reverse=True)
    elif estado.orden == "rss":
        filas.sort(key=lambda f: f.get("vmrss_kb", 0), reverse=True)
    else:
        filas.sort(key=lambda f: f.get("pid", 0))

    return filas


# Dibujado

def _addstr(stdscr, y, x, texto, attr=0):
    alto, ancho = stdscr.getmaxyx()
    if y < 0 or y >= alto or x >= ancho:
        return
    try:
        stdscr.addstr(y, x, texto[:max(0, ancho - x - 1)], attr)
    except curses.error:
        pass


def _dibujar(stdscr, ctx, estado):
    stdscr.erase()
    alto, ancho = stdscr.getmaxyx()

    if estado.mostrar_ayuda:
        _dibujar_ayuda(stdscr, ancho, alto)
        stdscr.refresh()
        return

    _dibujar_encabezado(stdscr, ctx, estado, ancho)

    filas = _construir_filas(ctx, estado)
    if filas:
        estado.seleccion = min(estado.seleccion, len(filas) - 1)
    else:
        estado.seleccion = 0

    alto_lista = max(3, min(len(filas) + 2, alto // 2))
    _dibujar_lista_procesos(stdscr, ctx, estado, filas, fila_inicio=1, alto_disp=alto_lista, ancho=ancho)

    fila_detalle = 1 + alto_lista
    alto_detalle = alto - fila_detalle - 1
    pid_detalle = None
    if estado.pin is not None and any(f["pid"] == estado.pin for f in filas):
        pid_detalle = estado.pin
    elif filas:
        pid_detalle = filas[estado.seleccion]["pid"]

    _dibujar_panel_detalle(stdscr, ctx, estado, pid_detalle, fila_detalle, alto_detalle, ancho)

    _dibujar_pie(stdscr, ctx, estado, alto - 1, ancho)

    stdscr.refresh()


def _dibujar_encabezado(stdscr, ctx, estado, ancho):
    tipo = estado.vista_activa
    intervalo = ctx["intervalos"][tipo].value
    verbose = "VERBOSE" if ctx["verbose_value"].value else ""
    reloj = time.strftime("%H:%M:%S")
    titulo = f" Monitor de Procesos (Comp II) | Vista: {_TITULOS[tipo]} ({intervalo:.1f}s) {verbose} "
    linea = titulo + " " * max(0, ancho - len(titulo) - len(reloj) - 1) + reloj
    _addstr(stdscr, 0, 0, linea.ljust(ancho), curses.color_pair(6) | curses.A_BOLD)


COLUMNAS = [
    ("PID", 7), ("USUARIO", 10), ("ST", 3), ("%CPU", 6),
    ("RSS(MB)", 9), ("THR", 4), ("COMANDO", None),
]


def _dibujar_lista_procesos(stdscr, ctx, estado, filas, fila_inicio, alto_disp, ancho):
    y = fila_inicio
    encabezado = ""
    for nombre, ancho_col in COLUMNAS:
        encabezado += nombre.ljust(ancho_col) if ancho_col else nombre
    _addstr(stdscr, y, 0, encabezado.ljust(ancho), curses.A_BOLD | curses.A_UNDERLINE)
    y += 1

    if not filas:
        _addstr(stdscr, y, 2, "(cargando datos de /proc... el recolector y analizadores estan arrancando)")
        return

    filas_visibles = alto_disp - 1
    inicio_scroll = max(0, estado.seleccion - filas_visibles + 1)
    for i, fila in enumerate(filas[inicio_scroll:inicio_scroll + filas_visibles]):
        idx_real = inicio_scroll + i
        estado_proc = fila.get("estado", "?")
        marca_pin = "*" if fila["pid"] == estado.pin else " "
        texto = (
            marca_pin + str(fila["pid"]).ljust(6)
            + str(fila.get("usuario", "?"))[:10].ljust(10)
            + str(estado_proc).ljust(3)
            + f"{fila.get('cpu_pct', 0):5.1f} "
            + f"{fila.get('vmrss_kb', 0) / 1024:8.1f} "
            + str(fila.get("threads", 1)).ljust(4)
            + str(fila.get("comando", ""))[:max(0, ancho - 45)]
        )
        attr = 0
        if estado_proc == "Z":
            attr = curses.color_pair(4) | curses.A_BOLD
        elif estado_proc == "R":
            attr = curses.color_pair(2)
        if idx_real == estado.seleccion:
            attr = curses.color_pair(1) | curses.A_BOLD
        _addstr(stdscr, y, 0, texto.ljust(ancho), attr)
        y += 1


# Paneles de detalle, uno por vista

def _dibujar_panel_detalle(stdscr, ctx, estado, pid, fila_inicio, alto_disp, ancho):
    tipo = estado.vista_activa
    _addstr(stdscr, fila_inicio, 0, ("-" * ancho)[:ancho], curses.color_pair(5))
    y = fila_inicio + 1

    if tipo == "sistema":
        _panel_sistema(stdscr, ctx, y, alto_disp, ancho)
        return

    if pid is None:
        _addstr(stdscr, y, 2, "No hay proceso seleccionado.")
        return

    data, ts = _obtener_dato(ctx, tipo)
    info = data.get(pid)
    edad = time.time() - ts if ts else None
    encabezado = f"PID {pid}"
    if edad is not None:
        encabezado += f"  (datos de hace {edad:.1f}s)"
    _addstr(stdscr, y, 2, encabezado, curses.A_BOLD)
    y += 1

    if info is None:
        _addstr(stdscr, y, 2, "(sin datos todavia para este proceso en esta vista)")
        return

    if tipo == "memoria":
        _panel_memoria(stdscr, info, y, alto_disp, ancho)
    elif tipo == "fds":
        _panel_fds(stdscr, info, y, alto_disp, ancho)
    elif tipo == "threads":
        _panel_threads(stdscr, info, y, alto_disp, ancho)
    elif tipo == "senales":
        _panel_senales(stdscr, info, y, alto_disp, ancho)
    elif tipo == "scheduling":
        _panel_scheduling(stdscr, info, y, alto_disp, ancho)
    elif tipo == "resumen":
        _panel_resumen(stdscr, info, y, alto_disp, ancho)


def _panel_resumen(stdscr, info, y, _alto, ancho):
    _addstr(stdscr, y, 2, f"PPID: {info.get('ppid')}   UID: {info.get('uid')} ({info.get('usuario')})")
    _addstr(stdscr, y + 1, 2, f"Estado: {info.get('estado')} - {info.get('estado_desc')}")
    _addstr(stdscr, y + 2, 2, f"Threads: {info.get('threads')}   %CPU: {info.get('cpu_pct')}")
    _addstr(stdscr, y + 3, 2, f"Comando: {info.get('comando', '')[:ancho - 15]}")


def _panel_memoria(stdscr, info, y, _alto, ancho):
    _addstr(stdscr, y, 2, f"VmSize: {info.get('vmsize')} kB    VmRSS: {info.get('vmrss')} kB    VmHWM: {info.get('vmhwm')} kB")
    _addstr(stdscr, y + 1, 2, f"VmData: {info.get('vmdata')} kB   VmStk: {info.get('vmstk')} kB   VmExe: {info.get('vmexe')} kB   VmLib: {info.get('vmlib')} kB")
    _addstr(stdscr, y + 2, 2, f"VmSwap: {info.get('vmswap')} kB")
    _addstr(stdscr, y + 3, 2, f"Page faults -> minor: {info.get('minflt')}  major: {info.get('majflt')}  (hijos: {info.get('cminflt')}/{info.get('cmajflt')})")
    seg = info.get("segmentos", {})
    _addstr(stdscr, y + 4, 2, "Segmentos (KB): " + "  ".join(f"{k}={v // 1024}" for k, v in seg.items()))
    _addstr(stdscr, y + 5, 2, f"Cantidad de mappings en /proc/pid/maps: {info.get('num_mappings')}")


def _panel_fds(stdscr, info, y, alto, ancho):
    _addstr(stdscr, y, 2, f"Cantidad de FDs abiertos: {info.get('cantidad')}")
    por_tipo = info.get("por_tipo", {})
    _addstr(stdscr, y + 1, 2, "Por tipo: " + ", ".join(f"{k}={v}" for k, v in por_tipo.items()))
    fila = y + 2
    for fd in info.get("detalle", [])[:max(0, alto - 3)]:
        _addstr(stdscr, fila, 2, f"  fd {fd['fd']:>3} [{fd['tipo']:<10}] -> {fd['destino']}"[:ancho - 3])
        fila += 1
    if info.get("truncado"):
        _addstr(stdscr, fila, 2, "  ... (lista truncada, activar modo verbose con SIGUSR2 para ver mas)")


def _panel_threads(stdscr, info, y, alto, ancho):
    _addstr(stdscr, y, 2, f"Cantidad de threads (LWPs): {info.get('cantidad')}")
    encabezado = "  TID".ljust(8) + "NOMBRE".ljust(16) + "ST".ljust(4) + "%CPU".ljust(7) + "CTX(vol/invol)"
    _addstr(stdscr, y + 1, 2, encabezado, curses.A_UNDERLINE)
    fila = y + 2
    for h in info.get("hilos", [])[:max(0, alto - 4)]:
        linea = (
            f"  {h['tid']}".ljust(8) + str(h["nombre"])[:15].ljust(16)
            + str(h["estado"]).ljust(4) + f"{h['cpu_pct']:5.1f}  "
            + f"{h['ctx_vol']}/{h['ctx_invol']}"
        )
        _addstr(stdscr, fila, 2, linea[:ancho - 3])
        fila += 1


def _panel_senales(stdscr, info, y, _alto, ancho):
    def fmt(lista):
        return ", ".join(lista) if lista else "(ninguna)"
    _addstr(stdscr, y, 2, f"Bloqueadas (SigBlk):  {fmt(info.get('bloqueadas'))}"[:ancho - 3])
    _addstr(stdscr, y + 1, 2, f"Ignoradas (SigIgn):   {fmt(info.get('ignoradas'))}"[:ancho - 3])
    _addstr(stdscr, y + 2, 2, f"Con handler (SigCgt): {fmt(info.get('con_handler'))}"[:ancho - 3])
    _addstr(stdscr, y + 3, 2, f"Pendientes proceso:   {fmt(info.get('pendientes_proceso'))}"[:ancho - 3])
    _addstr(stdscr, y + 4, 2, f"Pendientes grupo:     {fmt(info.get('pendientes_grupo'))}"[:ancho - 3])


def _panel_scheduling(stdscr, info, y, _alto, ancho):
    _addstr(stdscr, y, 2, f"Policy: {info.get('policy')}   Nice: {info.get('nice')}   Priority: {info.get('priority')}   RT Priority: {info.get('rt_priority')}")
    _addstr(stdscr, y + 1, 2, f"CPU affinity: {info.get('cpus_allowed')}")
    _addstr(stdscr, y + 2, 2, f"Context switches -> voluntarios: {info.get('ctx_vol')}   involuntarios: {info.get('ctx_invol')}")
    _addstr(stdscr, y + 3, 2, f"utime: {info.get('utime')} ticks   stime: {info.get('stime')} ticks")
    _addstr(stdscr, y + 4, 2, f"SID (sesion): {info.get('sid')}   PGID (grupo de procesos): {info.get('pgid')}")


def _panel_sistema(stdscr, ctx, y, alto, ancho):
    data, ts = _obtener_dato(ctx, "sistema")
    info = data.get(procfs.CLAVE_GLOBAL, {})
    if not info:
        _addstr(stdscr, y, 2, "(esperando primer muestreo del analizador de sistema...)")
        return

    edad = time.time() - ts if ts else None
    if edad is not None:
        _addstr(stdscr, y, 2, f"(datos de hace {edad:.1f}s)")
    y += 1

    cpu_pct = info.get("cpu_pct", {})
    if cpu_pct:
        _addstr(stdscr, y, 2, "CPU global: " + "  ".join(f"{k}={v}%" for k, v in cpu_pct.items()))
    else:
        _addstr(stdscr, y, 2, "CPU global: (calculando, necesita 2 muestras)")
    y += 1

    load = info.get("loadavg", {})
    _addstr(stdscr, y, 2, f"Load average: {load.get('load1')} {load.get('load5')} {load.get('load15')}   "
                          f"en ejecucion: {load.get('en_ejecucion')}/{load.get('total_procs_kernel')}")
    y += 1

    mem = info.get("meminfo", {})
    total = mem.get("MemTotal", 0)
    libre = mem.get("MemFree", 0)
    disponible = mem.get("MemAvailable", 0)
    buffers = mem.get("Buffers", 0)
    cached = mem.get("Cached", 0)
    swap_total = mem.get("SwapTotal", 0)
    swap_libre = mem.get("SwapFree", 0)
    _addstr(stdscr, y, 2, f"Memoria: total={total // 1024}MB  libre={libre // 1024}MB  disponible={disponible // 1024}MB  "
                          f"buffers={buffers // 1024}MB  cache={cached // 1024}MB")
    y += 1
    _addstr(stdscr, y, 2, f"Swap: total={swap_total // 1024}MB  libre={swap_libre // 1024}MB")
    y += 1

    uptime_s = info.get("uptime", 0)
    dias = int(uptime_s // 86400)
    horas = int((uptime_s % 86400) // 3600)
    minutos = int((uptime_s % 3600) // 60)
    btime = info.get("btime", 0)
    boot_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(btime)) if btime else "?"
    _addstr(stdscr, y, 2, f"Uptime: {dias}d {horas}h {minutos}m   Boot time: {boot_str}")
    y += 1

    por_estado = info.get("por_estado", {})
    resumen_estados = ", ".join(f"{procfs.ESTADOS.get(k, k)}={v}" for k, v in por_estado.items())
    _addstr(stdscr, y, 2, f"Procesos: {info.get('total_procesos')}   Threads totales: {info.get('total_threads')}   "
                          f"Zombies: {info.get('zombies')}")
    y += 1
    _addstr(stdscr, y, 2, f"Por estado: {resumen_estados}"[:ancho - 3])
    y += 2

    # Top 3 por CPU y por memoria, derivados de otras entradas del snapshot
    resumen_data, _ = _obtener_dato(ctx, "resumen")
    memoria_data, _ = _obtener_dato(ctx, "memoria")
    if resumen_data:
        top_cpu = sorted(resumen_data.items(), key=lambda kv: kv[1].get("cpu_pct", 0), reverse=True)[:3]
        _addstr(stdscr, y, 2, "Top 3 CPU: " + "  ".join(
            f"{pid}:{d.get('comm', '?')}({d.get('cpu_pct', 0)}%)" for pid, d in top_cpu)[:ancho - 3])
        y += 1
    if memoria_data and resumen_data:
        top_mem = sorted(memoria_data.items(), key=lambda kv: kv[1].get("vmrss", 0), reverse=True)[:3]
        _addstr(stdscr, y, 2, "Top 3 MEM: " + "  ".join(
            f"{pid}:{resumen_data.get(pid, {}).get('comm', '?')}({d.get('vmrss', 0) // 1024}MB)"
            for pid, d in top_mem)[:ancho - 3])


# Pie de pantalla y ayuda

def _dibujar_pie(stdscr, ctx, estado, fila, ancho):
    mensaje_txt, ts_msg = estado.mensaje
    if mensaje_txt and time.time() - ts_msg < 5:
        _addstr(stdscr, fila, 0, mensaje_txt.ljust(ancho), curses.A_BOLD | curses.color_pair(3))
        return

    filtro_info = ""
    if estado.filtro_cmd:
        filtro_info += f" cmd~'{estado.filtro_cmd}'"
    if estado.filtro_usuario:
        filtro_info += f" user~'{estado.filtro_usuario}'"

    ultimas = list(ctx["ultimas_senales"])[:3]
    senales_txt = ""
    if ultimas:
        senales_txt = " | señales: " + ", ".join(f"{n}@{time.strftime('%H:%M:%S', time.localtime(t))}" for n, t in ultimas)

    contador = ctx["contador_actualizaciones"].value
    pie = (f"[1-7/rmftspg] vista  [↑↓] navegar  [Enter] pin  [/] filtro-cmd  [u] filtro-user  "
           f"[c] orden={estado.orden}  [+-] intervalo  [q] salir  [h] ayuda"
           f"{filtro_info} | actualizaciones:{contador}{senales_txt}")
    _addstr(stdscr, fila, 0, pie.ljust(ancho), curses.A_REVERSE)


def _dibujar_ayuda(stdscr, ancho, alto):
    lineas = [
        "AYUDA - Monitor de Procesos y Threads (Computacion II)",
        "",
        "Vistas:",
        "  1 / r  Resumen        2 / m  Memoria         3 / f  File Descriptors",
        "  4 / t  Threads        5 / s  Señales         6 / p  Scheduling",
        "  7 / g  Sistema Global",
        "",
        "Navegacion:",
        "  Flechas arriba/abajo   Moverse por la lista de procesos",
        "  Enter                  Pinear/despinear el proceso seleccionado",
        "  /                      Filtrar por nombre de comando",
        "  u                      Filtrar por usuario",
        "  c                      Ciclar orden: cpu -> rss -> pid",
        "  + / -                  Ajustar el intervalo de refresco de la vista activa",
        "  q                      Salir limpiamente",
        "  h / ?                  Esta ayuda",
        "",
        "Señales que entiende el monitor (mandalas con `kill -SEÑAL <pid>`):",
        "  SIGINT / SIGTERM   Shutdown limpio de todos los procesos",
        "  SIGHUP             Recargar config.json",
        "  SIGUSR1            Volcar snapshot actual a dump_<timestamp>.json",
        "  SIGUSR2            Toggle de modo verbose",
        "  SIGWINCH           Repintar tras resize de la terminal",
        "",
        "Presione cualquier tecla para volver...",
    ]
    for i, linea in enumerate(lineas):
        if i >= alto:
            break
        _addstr(stdscr, i, 2, linea, curses.A_BOLD if i == 0 else 0)
