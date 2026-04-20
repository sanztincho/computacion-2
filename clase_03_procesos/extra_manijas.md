# Clase 3: Procesos - Extra Manijas

Material opcional para profundizar.

---

## El sistema de archivos /proc

Linux expone información de procesos a través de un filesystem virtual montado en `/proc`. No son archivos reales en disco - el kernel los genera dinámicamente cuando los leés.

### Estructura básica

```bash
/proc/
├── 1/                    # PID 1 (init/systemd)
│   ├── cmdline           # Comando con argumentos
│   ├── cwd -> /          # Symlink al directorio de trabajo
│   ├── environ           # Variables de entorno
│   ├── exe -> /sbin/init # Symlink al ejecutable
│   ├── fd/               # Directorio con file descriptors
│   ├── maps              # Mapeo de memoria
│   ├── stat              # Estadísticas (una línea, campos numéricos)
│   ├── status            # Estadísticas (formato legible)
│   └── ...
├── self -> 1234/         # Symlink al proceso actual
├── cpuinfo               # Info de CPU
├── meminfo               # Info de memoria
└── ...
```

### Leyendo información de procesos

```python
import os

def info_proceso(pid):
    """Lee información de un proceso desde /proc."""
    base = f"/proc/{pid}"

    try:
        # Comando
        with open(f"{base}/cmdline", "rb") as f:
            cmdline = f.read().replace(b"\x00", b" ").decode().strip()

        # Estado
        with open(f"{base}/status") as f:
            status = {}
            for linea in f:
                if ":" in linea:
                    k, v = linea.split(":", 1)
                    status[k.strip()] = v.strip()

        # File descriptors
        fds = os.listdir(f"{base}/fd")

        return {
            "pid": pid,
            "cmdline": cmdline,
            "name": status.get("Name"),
            "state": status.get("State"),
            "ppid": status.get("PPid"),
            "threads": status.get("Threads"),
            "memory_vm": status.get("VmSize"),
            "memory_rss": status.get("VmRSS"),
            "open_fds": len(fds),
        }
    except (FileNotFoundError, PermissionError) as e:
        return {"error": str(e)}

# Ejemplo: info del proceso actual
info = info_proceso(os.getpid())
for k, v in info.items():
    print(f"{k}: {v}")
```

### El archivo /proc/[pid]/stat

Este archivo contiene estadísticas en formato compacto (una línea, campos separados por espacios). Es más eficiente que `status` si necesitás procesar muchos procesos:

```python
def leer_stat(pid):
    """Lee /proc/[pid]/stat y retorna campos parseados."""
    with open(f"/proc/{pid}/stat") as f:
        contenido = f.read()

    # El nombre del proceso está entre paréntesis y puede contener espacios
    # Formato: pid (nombre) estado ...
    inicio_nombre = contenido.index("(")
    fin_nombre = contenido.rindex(")")

    pid = int(contenido[:inicio_nombre].strip())
    nombre = contenido[inicio_nombre + 1 : fin_nombre]
    resto = contenido[fin_nombre + 2 :].split()

    return {
        "pid": pid,
        "nombre": nombre,
        "estado": resto[0],
        "ppid": int(resto[1]),
        "pgrp": int(resto[2]),
        "session": int(resto[3]),
        "utime": int(resto[11]),  # Tiempo en modo usuario (jiffies)
        "stime": int(resto[12]),  # Tiempo en modo kernel (jiffies)
        "num_threads": int(resto[17]),
        "starttime": int(resto[19]),  # Tiempo desde boot (jiffies)
    }
```

---

## Señales: comunicación asíncrona

Las señales son notificaciones asíncronas que el kernel envía a procesos. Son el mecanismo más básico de comunicación entre procesos.

### Señales comunes

| Señal | Número | Acción por defecto | Descripción |
|-------|--------|-------------------|-------------|
| SIGTERM | 15 | Terminar | Solicitud de terminación "amable" |
| SIGKILL | 9 | Terminar | Terminación forzosa (no capturable) |
| SIGINT | 2 | Terminar | Ctrl+C en terminal |
| SIGSTOP | 19 | Detener | Pausa el proceso (no capturable) |
| SIGCONT | 18 | Continuar | Reanuda proceso detenido |
| SIGCHLD | 17 | Ignorar | Un hijo cambió de estado |
| SIGHUP | 1 | Terminar | Terminal cerrada |
| SIGUSR1/2 | 10/12 | Terminar | Señales para uso del usuario |

### Enviando señales

```python
import os
import signal

# Enviar señal a un proceso
os.kill(pid, signal.SIGTERM)

# Enviar a todos los procesos del grupo
os.killpg(pgid, signal.SIGTERM)

# Señal a ti mismo
os.kill(os.getpid(), signal.SIGUSR1)
```

### Manejando señales

```python
import signal
import sys

def manejador_sigterm(signum, frame):
    print(f"\nRecibí SIGTERM (señal {signum})")
    print("Limpiando recursos...")
    sys.exit(0)

def manejador_sigint(signum, frame):
    print("\nCtrl+C detectado, pero voy a ignorarlo!")
    print("Usá SIGTERM o SIGKILL para terminarme")

# Registrar manejadores
signal.signal(signal.SIGTERM, manejador_sigterm)
signal.signal(signal.SIGINT, manejador_sigint)

print(f"PID: {os.getpid()}")
print("Esperando señales... (kill -TERM <pid> para terminar)")

# Loop infinito
while True:
    signal.pause()  # Esperar hasta recibir una señal
```

### SIGCHLD y wait no bloqueante

El kernel envía SIGCHLD al padre cuando un hijo cambia de estado. Esto permite evitar zombies sin bloquear:

```python
import os
import signal

def manejador_sigchld(signum, frame):
    """Recoge hijos terminados de forma no bloqueante."""
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break  # No hay más hijos terminados
            print(f"Hijo {pid} terminó con {os.WEXITSTATUS(status)}")
        except ChildProcessError:
            break  # No hay hijos

signal.signal(signal.SIGCHLD, manejador_sigchld)

# Crear varios hijos
for i in range(3):
    if os.fork() == 0:
        import time
        time.sleep(i + 1)
        os._exit(i)

# El padre puede hacer otras cosas mientras espera
import time
for _ in range(5):
    print("Padre trabajando...")
    time.sleep(1)
```

---

## Process groups y sessions

Los procesos se organizan en grupos y sesiones para control de jobs.

```
Session (controlada por terminal)
└── Process Group (foreground)
│   ├── shell (líder del grupo)
│   └── comando1 | comando2 (mismo grupo)
└── Process Group (background job 1)
│   └── sleep 100 &
└── Process Group (background job 2)
    └── find / -name "*.log" &
```

### Consultando grupos

```python
import os

print(f"PID: {os.getpid()}")
print(f"PPID: {os.getppid()}")
print(f"PGID: {os.getpgrp()}")       # Process Group ID
print(f"SID: {os.getsid(0)}")        # Session ID
```

### Creando un nuevo grupo

```python
# El hijo se convierte en líder de su propio grupo
pid = os.fork()
if pid == 0:
    os.setpgrp()  # Crear nuevo grupo con este proceso como líder
    print(f"Hijo: PID={os.getpid()}, PGID={os.getpgrp()}")
    os._exit(0)
else:
    os.wait()
    print(f"Padre: PID={os.getpid()}, PGID={os.getpgrp()}")
```

---

## Demonios (daemons)

Un demonio es un proceso que corre en segundo plano, desconectado de cualquier terminal.

### Pasos para crear un demonio

```python
import os
import sys

def daemonize():
    """Convierte el proceso actual en un demonio."""

    # 1. Fork y terminar padre (desvincularse de terminal)
    pid = os.fork()
    if pid > 0:
        sys.exit(0)  # Padre termina

    # 2. Crear nueva sesión (convertirse en líder)
    os.setsid()

    # 3. Segundo fork (asegurar que no podemos readquirir terminal)
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # 4. Cambiar directorio de trabajo
    os.chdir("/")

    # 5. Resetear umask
    os.umask(0)

    # 6. Cerrar file descriptors heredados
    for fd in range(3, 1024):
        try:
            os.close(fd)
        except OSError:
            pass

    # 7. Redirigir stdin/stdout/stderr a /dev/null
    sys.stdin = open("/dev/null", "r")
    sys.stdout = open("/dev/null", "w")
    sys.stderr = open("/dev/null", "w")

def main():
    daemonize()

    # Escribir PID para poder terminar el demonio después
    with open("/tmp/mi_demonio.pid", "w") as f:
        f.write(str(os.getpid()))

    # El demonio hace su trabajo aquí
    import time
    while True:
        with open("/tmp/mi_demonio.log", "a") as f:
            f.write(f"Demonio vivo: {time.ctime()}\n")
        time.sleep(10)

if __name__ == "__main__":
    main()
```

### La forma moderna: systemd

En sistemas modernos, es mejor dejar que systemd maneje la daemonización:

```ini
# /etc/systemd/system/mi_servicio.service
[Unit]
Description=Mi servicio Python
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/mi_app/main.py
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```

---

## exec con redirección

Antes del exec, podés redirigir los file descriptors del hijo:

```python
import os

def ejecutar_con_salida_a_archivo(comando, args, archivo_salida):
    """Ejecuta un comando redirigiendo stdout a un archivo."""
    pid = os.fork()

    if pid == 0:
        # Abrir archivo para salida
        fd = os.open(archivo_salida, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)

        # Duplicar fd a stdout (fd 1)
        os.dup2(fd, 1)

        # Cerrar el fd original (ya está duplicado)
        os.close(fd)

        # Exec - stdout ahora va al archivo
        os.execvp(comando, [comando] + args)
        os._exit(1)
    else:
        os.wait()

# Uso
ejecutar_con_salida_a_archivo("ls", ["-la"], "/tmp/listado.txt")
```

### Creando un pipe entre procesos

```python
import os

def ejecutar_con_pipe(cmd1, args1, cmd2, args2):
    """Ejecuta cmd1 | cmd2 usando un pipe."""

    # Crear pipe
    r, w = os.pipe()

    # Primer hijo (productor)
    pid1 = os.fork()
    if pid1 == 0:
        os.close(r)          # No necesita leer
        os.dup2(w, 1)        # stdout -> pipe write
        os.close(w)
        os.execvp(cmd1, [cmd1] + args1)
        os._exit(1)

    # Segundo hijo (consumidor)
    pid2 = os.fork()
    if pid2 == 0:
        os.close(w)          # No necesita escribir
        os.dup2(r, 0)        # stdin <- pipe read
        os.close(r)
        os.execvp(cmd2, [cmd2] + args2)
        os._exit(1)

    # Padre cierra ambos extremos y espera
    os.close(r)
    os.close(w)
    os.waitpid(pid1, 0)
    os.waitpid(pid2, 0)

# Equivalente a: ls -la | grep txt
ejecutar_con_pipe("ls", ["-la"], "grep", ["txt"])
```

---

## fork() vs vfork() vs clone()

Linux tiene varias syscalls para crear procesos:

**fork():** Crea una copia del proceso (con COW).

**vfork():** Versión obsoleta que suspendía al padre hasta que el hijo hiciera exec. Ya no es necesaria gracias a COW.

**clone():** La syscall subyacente que permite control fino sobre qué se comparte entre padre e hijo. Es la base de los threads y contenedores.

```c
// fork() es equivalente a:
clone(SIGCHLD, 0)

// Crear un thread (comparte todo):
clone(CLONE_VM | CLONE_FS | CLONE_FILES | CLONE_SIGHAND | CLONE_THREAD, stack)

// Contenedor (nuevo namespace):
clone(CLONE_NEWNS | CLONE_NEWPID | CLONE_NEWNET, 0)
```

---

## Namespaces y contenedores

Los namespaces son la tecnología detrás de Docker y otros contenedores. Permiten que un proceso tenga su propia "vista" de recursos del sistema:

| Namespace | Aísla |
|-----------|-------|
| PID | Tabla de procesos |
| NET | Stack de red |
| MNT | Puntos de montaje |
| UTS | Hostname |
| IPC | IPC (semáforos, memoria compartida) |
| USER | UIDs y GIDs |

```python
# Crear proceso en nuevo namespace PID (requiere root)
import os

CLONE_NEWPID = 0x20000000

# Esto NO funciona directamente en Python - necesita ctypes o extensión C
# Es solo ilustrativo

def unshare_pid():
    """Crea nuevo namespace PID."""
    # En la práctica usarías:
    # - docker/podman
    # - unshare command
    # - ctypes para llamar a clone() directamente
    pass
```

---

## cgroups: límites de recursos

Los cgroups (control groups) permiten limitar y monitorear recursos por grupo de procesos.

```bash
# Ver cgroups del proceso actual
cat /proc/self/cgroup

# Estructura en /sys/fs/cgroup (cgroups v2)
/sys/fs/cgroup/
├── cgroup.controllers
├── cgroup.subtree_control
├── user.slice/
│   └── user-1000.slice/
│       └── session-1.scope/
│           ├── cgroup.procs      # PIDs en este cgroup
│           ├── cpu.stat          # Estadísticas de CPU
│           ├── memory.current    # Memoria usada
│           └── memory.max        # Límite de memoria
```

### Limitando memoria con cgroups

```bash
# Crear cgroup
sudo mkdir /sys/fs/cgroup/mi_grupo

# Setear límite de memoria (100MB)
echo "104857600" | sudo tee /sys/fs/cgroup/mi_grupo/memory.max

# Mover proceso al cgroup
echo $$ | sudo tee /sys/fs/cgroup/mi_grupo/cgroup.procs

# Ahora el proceso tiene límite de 100MB
```

---

## Herramientas de diagnóstico

### strace: seguir syscalls

```bash
# Ver syscalls de un comando
strace ls -la

# Filtrar solo fork/exec/wait
strace -e trace=process ls -la

# Seguir hijos también
strace -f python3 mi_script.py

# Contar syscalls
strace -c python3 -c "import os; os.fork()"
```

### ltrace: seguir llamadas a bibliotecas

```bash
ltrace python3 -c "print('hola')"
```

### perf: profiling de bajo nivel

```bash
# Eventos de scheduling
sudo perf stat -e context-switches,cpu-migrations python3 mi_script.py

# Flamegraph de CPU
sudo perf record -g python3 mi_script.py
sudo perf report
```

---

## Recursos adicionales

- [Linux Programming Interface](https://man7.org/tlpi/) - El libro definitivo sobre programación de sistemas Linux
- [proc(5) man page](https://man7.org/linux/man-pages/man5/proc.5.html) - Documentación completa de /proc
- [credentials(7)](https://man7.org/linux/man-pages/man7/credentials.7.html) - UIDs, GIDs, y capabilities
- [namespaces(7)](https://man7.org/linux/man-pages/man7/namespaces.7.html) - Documentación de namespaces
- [cgroups(7)](https://man7.org/linux/man-pages/man7/cgroups.7.html) - Documentación de cgroups

---

*Computación II - 2026 - Clase 3 - Material opcional*
