# TP N.º 1 — Monitor de Procesos y Threads

**Computación II — Universidad de Mendoza — Martin Sanz — 2026**

Monitor de sistema en tiempo real, estilo `htop`, que lee `/proc` directamente
(sin `psutil`) y expone la anatomía interna de cada proceso — memoria, file
descriptors, threads, señales y scheduling — a través de una arquitectura
**multiproceso** con IPC de `multiprocessing`.

---

## 1. Descripción general

El monitor tiene 7 vistas alternables. Siempre se ve arriba una lista de
procesos (PID, usuario, estado, %CPU, RSS, threads, comando) y abajo un panel
de detalle que cambia según la vista activa:

| Tecla | Vista |
|---|---|
| `1` / `r` | Resumen |
| `2` / `m` | Memoria |
| `3` / `f` | File Descriptors |
| `4` / `t` | Threads (LWPs) |
| `5` / `s` | Señales |
| `6` / `p` | Scheduling |
| `7` / `g` | Sistema Global |

Navegación: flechas `↑`/`↓`, `Enter` para pinear un proceso (el panel de
detalle se queda mostrando ese PID aunque la lista se reordene), `/` para
filtrar por comando, `u` para filtrar por usuario, `c` para ciclar el orden
(`cpu` → `rss` → `pid`), `+`/`-` para ajustar el intervalo de refresco de la
vista activa, `q` para salir, `h`/`?` para la ayuda.

El monitor responde a señales enviadas con `kill -SEÑAL <pid>`:
`SIGINT`/`SIGTERM` (shutdown limpio), `SIGHUP` (recarga `config.json`),
`SIGUSR1` (vuelca el snapshot a `dump_<timestamp>.json`), `SIGUSR2` (toggle
modo verbose) y `SIGWINCH` (repintado tras resize).

## 2. Diagrama de arquitectura

```
                    ┌──────────────────────────────┐
                    │   compartido (Manager.dict)  │
                    │        { "pids": [...] }     │
                    └───────────▲─────────┬────────┘
                     escribe    │         │ leen (7 analizadores)
                     cada ~1s   │         │
              ┌─────────────────┘         │
              │                           │
        ┌─────┴─────┐        ┌────────────┴──────────────────────────┐
        │Recolector │        │                                       │
        │(1 proceso)│   ┌────┴────┐ ┌─────────┐ ┌──────┐  ...  ┌─────┴───┐
        └───────────┘   │ resumen │ │ memoria │ │ fds  │       │ sistema │
                        │  (2s)   │ │  (3s)   │ │ (5s) │       │  (2s)   │
                        └────┬────┘ └────┬────┘ └───┬──┘       └────┬────┘
                             │           │          │               │
                             └───────────┴───┬──────┴───────────────┘
                                             │  put((tipo,data,ts))
                                             ▼
                                   cola_agregador (Queue)
                                             │
                                             ▼
                                      ┌──────────────────┐
                                      │    Agregador     │
                                      │    (1 proceso)   │
                                      └─────────┬────────┘
                                                │ snapshot[tipo] = {...}
                                                ▼
                              ┌────────────────────────────────────┐
                              │   snapshot (Manager.dict)          │
                              │  resumen / memoria / fds / threads │
                              │  senales / scheduling / sistema    │
                              │  cada uno: {"data":{...}, "ts":..} │
                              └────────────────▲───────────────────┘
                                                │ lee
                                                │
                                      ┌─────────┴────────────┐
                                      │  Display / TUI       │
                                      │  (proceso PRINCIPAL) │
                                      │  curses + teclado    │
                                      │  + self-pipe señales │
                                      └──────────────────────┘
```

10 procesos en total corriendo en simultáneo: 1 Recolector + 7 Analizadores +
1 Agregador + el proceso principal (que además de orquestar todo, es el que
corre la TUI). Cada analizador es un `multiprocessing.Process` independiente
con su propio intervalo (`multiprocessing.Value`, ajustable en caliente).

---

## 3. Decisiones de diseño

### 3.1 ¿Por qué cada mecanismo de IPC y no otro?

| Canal | Mecanismo | Por qué |
|---|---|---|
| Recolector → 7 analizadores | `Manager.dict()` (`compartido['pids']`) | Es **uno-a-muchos**: los 7 analizadores necesitan leer el mismo valor las veces que quieran. Una `Queue` no sirve acá porque reparte cada mensaje a un único consumidor (son consumidores en competencia); necesitábamos que los 7 pudieran leer el mismo dato repetidamente. |
| Analizadores → Agregador | `multiprocessing.Queue` | Es **muchos-a-uno**, el caso de uso clásico de `Queue`: 7 productores, 1 consumidor, sin necesidad de que sepan nada unos de otros. |
| Agregador → Display | `Manager.dict()` (`snapshot`) | De nuevo uno-a-muchos (en este caso 1 escritor, 1 lector, pero de tamaño/forma variable e impredecible: dicts anidados por PID, listas de FDs de longitud variable, etc.) — no es un tipo fijo de ctypes, así que no puede ser `Value`/`Array`. |
| Display ↔ Analizador (ajustar intervalo con `+`/`-`) | `multiprocessing.Value('d', ...)`, uno por vista | Acá sí hay un único escritor (Display) y un único lector (el analizador de esa vista), y se lee en *cada vuelta* del loop del analizador (potencialmente muy seguido). Pasar esto por un `Manager` significaría un roundtrip de IPC a un proceso servidor en cada lectura; con `Value` es memoria compartida real via `mmap`, sin ese costo. |
| Contador de actualizaciones | `multiprocessing.Value('i', 0)` con lock | Ver más abajo, sección de race conditions. |
| Coordinación de shutdown | `multiprocessing.Event()` | Es exactamente para esto: un booleano que múltiples procesos pueden `.set()`/`.is_set()` sin carreras. |

### 3.2 ¿Por qué `Manager` y no `Value`/`Array` para el snapshot y la lista de pids?

`Value` y `Array` solo pueden contener tipos `ctypes` de tamaño **fijo y
homogéneo** (enteros, floats, o arrays de estos). El snapshot global es
heterogéneo (un dict por PID con distinta cantidad de claves según la vista,
listas de FDs o de threads de longitud variable) y su tamaño cambia todo el
tiempo (aparecen y desaparecen procesos). Eso solo lo puede manejar el
`Manager().dict()`, que corre un proceso servidor aparte y expone proxies que
serializan (pickle) los objetos Python "normales" que le pasemos.

El costo es que cada operación sobre un `Manager.dict` es una llamada RPC al
proceso del Manager (más lenta que tocar memoria compartida directa). Por eso
reservamos `Manager` solo para los dos canales que realmente necesitan
estructuras variables (`compartido` y `snapshot`), y usamos `Value` liviano
para todo lo demás (intervalos, contador, flags).

### 3.3 ¿Cómo se manejaron las race conditions?

Se identificaron y resolvieron tres escenarios concretos:

1. **Reemplazo atómico en vez de mutación incremental.** Tanto el Recolector
   (`compartido['pids'] = pids`) como el Agregador (`snapshot[tipo] = {"data":
   ..., "ts": ...}`) siempre **reemplazan el valor completo** en una única
   llamada al proxy del Manager, en vez de ir mutando el dict campo por campo.
   Esto es muy importante porque si en cambio hiciéramos algo como
   `snapshot[tipo]['data'][pid] = nuevo_valor` para cada PID uno por uno, un
   lector (el Display) podría leer el dict **a mitad de esa actualización**,
   viendo una mezcla de datos viejos y nuevos de distintos instantes de
   tiempo — race condition de lector/escritor. Al reemplazar el
   objeto entero en una sola operación, el Display siempre ve o el snapshot
   viejo completo, o el nuevo completo.

2. **Un único escritor por canal.** El Agregador es el **único** proceso que
   escribe en `snapshot`; los 7 analizadores nunca escriben ahí directamente
   (le mandan sus datos por `Queue`, y la `Queue` ya serializa el orden de
   llegada). Esto elimina la posibilidad de que dos procesos pisen la
   escritura del otro sobre el mismo dict — no porque haya un lock,
   sino porque la queue garantiza que nunca hay dos escritores
   concurrentes sobre el mismo recurso.

3. **El contador global de actualizaciones necesita un lock explícito.**
   Este es el caso más directo de race condition del proyecto:
   `contador_actualizaciones` (`multiprocessing.Value('i', 0)`) lo incrementan
   los **7 analizadores en simultáneo**, uno por cada ciclo de su loop. Un
   `value += 1` sobre un entero compartido no es atómico: internamente es
   un read-modify-write (leer el valor actual, sumarle 1, escribir el
   resultado). Si dos analizadores hacen esto "al mismo tiempo" sin
   sincronización, puede pasar lo siguiente:

   ```
   Analizador A lee value=41
   Analizador B lee value=41      (todavía no vio el +1 de A)
   Analizador A escribe value=42
   Analizador B escribe value=42  <- se "pisó" el incremento de A, se perdió una actualización
   ```

   La solución es el lock que trae `Value` por defecto
   (`with contador_actualizaciones.get_lock(): contador_actualizaciones.value
   += 1`), que convierte esas tres operaciones en una sección crítica
   atómica. Sin el `with contador_global.get_lock():` en
   `analizadores/base.py`, con 7 procesos incrementando muy seguido, el
   contador que se ve en el pie de pantalla terminaría siendo menor a la cantidad real de actualizaciones
   publicadas.

### 3.4 ¿Por qué esos intervalos por defecto?

Los intervalos (resumen/threads/sistema: 2s, memoria: 3s, fds: 5s,
señales/scheduling: 10s) siguen el costo relativo de cada lectura de `/proc`:

- **Resumen, threads, sistema (2s):** son los datos que más caambian y a
  la vez son livianos de leer (un `/proc/<pid>/stat` y `/proc/<pid>/status`
  por proceso).
- **Memoria (3s):** además de `status`/`stat`, requiere leer y parsear
  `/proc/<pid>/maps` completo (puede tener cientos de líneas en procesos con
  muchas librerías cargadas), así que es más caro por proceso.
- **FDs (5s):** requiere un `os.listdir` + un `os.readlink` **por cada FD
  abierto** de cada proceso — con cientos de procesos y potencialmente miles
  de FDs totales en el sistema, es la vista más pesada de todas.
- **Señales y scheduling (10s):** son datos que cambian poco en cada ciclo
  (máscaras de señales bloqueadas/ignoradas, nice,policy), 
  así que no hace falta refrescarlos tan seguido.

Los mínimos (la mitad del default, aproximadamente) existen para que el
usuario pueda apretar `+`/`-` y exigirle más al monitor si su máquina lo
permite, sin poder llevarlo a un intervalo de 0 que satura la CPU con
lecturas de `/proc` en loop cerrado.

El Recolector corre al doble de frecuencia que el analizador más exigente
(`intervalo_recolector = min(intervalos) / 2`), para asegurarse de que
siempre haya una lista de PIDs relativamente fresca disponible, sin importar
qué tan seguido la estén pidiendo los analizadores.

---

## 4. Conceptos del curso aplicados

- **Clase 3 (Procesos, `/proc`, memoria virtual):** todo `procfs.py` es 
  esto: leer `/proc/<pid>/stat`, `/status`, `/maps` a mano.
  `agrupar_segmentos()` reconstruye la anatomía de memoria virtual de un
  proceso (texto, heap, pila, mapeos compartidos) parseando `/proc/<pid>/maps`
  campo por campo, tal como se vio en la clase.

- **Clase 4 (fork/exec/wait, zombies, COW):** en la vista Sistema, un proceso
  aparece como zombie (`estado == "Z"`) cuando terminó pero su padre todavía
  no llamó a `wait()`/`waitpid()` — el kernel mantiene la entrada en la tabla
  de procesos únicamente para que el padre pueda recoger el código de salida.
  `sistema.py` cuenta estos casos leyendo el campo `State` de
  `/proc/<pid>/stat`.

- **Clase 5 (Pipes, FDs):** la vista de File Descriptors (`analizadores/fds.py`)
  muestra lo que se vio en clase: cada entrada de
  `/proc/<pid>/fd/` es un symlink que apunta a `pipe:[inodo]`, `socket:[inodo]`,
  un archivo real, o un dispositivo tty — `clasificar_fd()` distingue estos
  casos mirando el prefijo del destino del symlink.

- **Clase 6 (Señales, handlers, self-pipe):** `src/senales.py` implementa el
  patrón self-pipe igual a como se vio: el signal handler hace un único
  `os.write()` async-signal-safe de 1 byte (el número de señal) a un pipe no
  bloqueante, y todo el trabajo real (recargar config, volcar el dump,
  togglear verbose) se hace en el loop principal de `display.py`, que lee ese
  pipe de forma no bloqueante en cada vuelta. Además, `analizadores/base.py`
  aplica el concepto de que **las señales del Ctrl+C llegan a todo el
  process group**: por eso cada proceso hijo instala `SIG_IGN` para
  SIGINT/SIGTERM/SIGHUP/SIGUSR1/SIGUSR2 apenas arranca, y deja que sea
  únicamente el proceso principal quien decida cuándo apagar todo
  (coordinado con `shutdown_event`).

- **Clase 7 (mmap y memoria compartida):** `multiprocessing.Value` y
  `multiprocessing.Manager` son, por debajo, esto: `Value` usa
  `mmap` con `MAP_SHARED` para compartir un bloque de memoria entre procesos
  con parentesco (fork); el `Manager` corre un proceso servidor con el que
  los demás se comunican vía sockets/pipes internos y objetos proxy.

- **Clase 8 y 9 (Multiprocessing fundamentos y avanzado — `Process`, `Queue`,
  `Pipe`, `Manager`, `Value`, `Array`):** toda la arquitectura del monitor
  (Recolector + 7 Analizadores + Agregador, ver diagrama arriba) es una
  aplicación directa de estas cuatro bases combinadas: `Process` para
  cada componente, `Queue` para el canal muchos-a-uno hacia el Agregador,
  `Manager().dict()` para el estado compartido de forma/tamaño variable, y
  `Value` para los contadores/flags de tamaño fijo.

- **Clase 10 (Threading, GIL, threads como LWPs):** la vista de Threads
  (`analizadores/threads.py`) hace visible, con datos reales, la diferencia
  entre PID y TID: cada thread de un proceso tiene su propia carpeta en
  `/proc/<pid>/task/<tid>/` con su propio `stat` (su propio `state`, sus
  propios `utime`/`stime`) pero comparte el mismo espacio de memoria — por
  eso en la vista de Threads se ve, por ejemplo, un proceso Python
  multithreaded con varios TIDs cuyo `%CPU` conjunto puede acercarse al de
  varios cores, pese al GIL (que serializa la ejecución de bytecode Python,
  pero no evita que threads en I/O o en extensiones en C liberen el GIL y
  corran en paralelo real).

---

## 5. Decisiones sobre la TUI

Se eligió `curses` (stdlib) por sobre `rich`: sin dependencias externas,
trabajo realizado mas a mano, y porque `curses` obliga a pensar explícitamente 
en el modelo de refresco de pantalla (`erase`/`addstr`/`refresh`) y en el manejo de teclado no bloqueante
(`stdscr.timeout()`).

El layout es fijo (encabezado / lista / panel de detalle / pie), calculado en
cada frame en función de `stdscr.getmaxyx()`, así que el monitor se adapta a
cualquier tamaño de terminal (y reacciona a `SIGWINCH` en un resize).

`stdscr.timeout(150)` hace que `getch()` no bloquee más de 150ms: eso da un
refresco de pantalla fluido y, a la vez, dentro del mismo loop, se chequea el
self-pipe de señales cada 150ms como máximo — buen balance entre
responsividad y no quemar CPU en un loop apretado.

---

## 6. Limitaciones conocidas

- **Visibilidad de procesos del host vs. del contenedor:** `docker-compose.yml`
  usa `pid: host` para que `/proc` muestre los procesos reales de la máquina
  (si no, dentro del contenedor casi no hay nada interesante para monitorear).
  Si el entorno de Docker no permite esa opción (algunos runners de CI la
  bloquean por seguridad), hay que comentarla: el monitor sigue funcionando
  perfectamente, solo que mostrando únicamente los procesos del propio
  contenedor.
- **Permisos:** aun con `pid: host`, el contenedor corre como root pero
  algunos campos de procesos ajenos pueden fallar por restricciones de
  `ptrace_scope` del kernel o namespaces de usuario — esos casos se manejan
  con `try/except` y simplemente el proceso no muestra esa dimensión en ese
  ciclo, no rompe el monitor.
- **`Cpus_allowed_list` puede no existir** en kernels muy viejos o
  configuraciones sin `CONFIG_CPUSETS`; en ese caso se muestra `?`.
- **Terminales muy chicas:** con menos de ~15 filas el panel de detalle puede
  no alcanzar a mostrar todos los campos de una vista; no hay scroll interno
  del panel de detalle (sí lo hay para la lista de procesos).
- **El pin (`Enter`) se pierde si el proceso termina:** al no encontrarse más
  ese PID en `resumen`, el panel de detalle vuelve a seguir a la fila
  seleccionada por el cursor.
- **La decodificación de señales de tiempo real (RT, 32-64)** se muestra
  genéricamente como `SIGRT<n>` porque Python no expone nombres estándar
  fijos para todas ellas (varían según `SIGRTMIN` del kernel).
- **No se probó en macOS/Windows**

---

## 7. Cómo correr y testear

```bash
# Levantar el monitor con Docker (forma normal de uso)
docker compose up --build
docker compose run --rm monitor

# Tests unitarios de parseo de /proc (no requieren un PID real, corren
# sobre strings sintéticas con el formato exacto de /proc/<pid>/stat, etc.)
pip install pytest
python3 -m pytest tests/ -v

# Selftest end-to-end de la arquitectura multiproceso, sin necesitar una
# terminal real (util en CI o para verificar rapido que todo esta bien
# cableado antes de entrar a la TUI)
cd src && python3 main.py --selftest

# Modo daemon (bonus): backend sin TUI, loggeando a un archivo
cd src && python3 main.py --daemon /tmp/monitor.log
```

Todos los tests (`tests/test_procfs.py`, 11 casos) y el `--selftest` fueron
efectivamente corridos durante el desarrollo del TP (no solo escritos):
el selftest confirmó que, en la máquina de desarrollo, el snapshot se pobló
correctamente para las 7 dimensiones sobre ~65 procesos reales del sistema,
y una prueba manual con `kill -USR1/-HUP/-USR2/-TERM` sobre el proceso en
modo `--daemon` confirmó que las 4 señales se procesan correctamente y que el
shutdown no deja procesos huérfanos (verificado con `ps aux` después de
mandar `SIGTERM`).

---

## 8. Lo que aprendí

Separar "leer un archivo de `/proc`" de "parsear su contenido" (funciones
`leer_*` vs `parsear_*` en `procfs.py`) terminó siendo la decisión más
rentable de todo el TP: permitió escribir tests unitarios reales del parseo
(que es donde están los detalles más delicados — el `comm` entre paréntesis
que puede tener espacios, los índices de campos de `/proc/<pid>/stat` que
hay que contar con cuidado contra `man proc(5)`) sin necesitar mockear nada
del sistema de archivos.

El ejercicio de tener que decidir, para cada canal de comunicación entre
procesos, *cuál* mecanismo de IPC usar (y no simplemente "usar `Manager`
para todo porque es lo más fácil") fue lo que más me ayudo a concretar la teoria: al
principio la tentación era meter todo en un único `Manager.dict` gigante,
pero pensar explícitamente en "¿cuántos escritores tiene esto? ¿cuántos
lectores? ¿el tamaño es fijo?" llevó a la arquitectura de
capas (Recolector → analizadores → Agregador → Display) que terminó siendo 
mucho más fácil de razonar sobre las race conditions que una versión
en donde esta todo junto.

Por último, ver en la práctica que `value += 1` sobre un
`multiprocessing.Value` compartido por 7 procesos necesita un lock explícito
—y poder reproducirlo/explicarlo con el ejemplo concreto del contador de
actualizaciones— hizo mucho más tangible algo que en la teoría suena
abstracto ("las race conditions son operaciones no atómicas interrumpidas a
mitad de camino").
