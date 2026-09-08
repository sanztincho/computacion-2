# Clase 3: Procesos - Ejercicios Prácticos

## Ejercicio 1: Explorando procesos desde la terminal

Antes de escribir código, familiarizate con las herramientas del sistema para observar procesos.

### 1.1 Identificando tu proceso actual

Abrí una terminal y ejecutá:

```bash
echo $$
```

Ese número es el PID de tu shell actual. Ahora ejecutá:

```bash
ps -p $$
```

Deberías ver información sobre tu shell. El comando `ps` es tu ventana al mundo de los procesos.

### 1.2 Observando la jerarquía

Ejecutá `pstree -p` para ver el árbol de procesos con PIDs. Encontrá tu shell en el árbol. ¿Quién es su padre? ¿Y el padre de ese padre?

Ahora ejecutá:

```bash
ps -ef | head -20
```

La columna PPID muestra el Parent PID. Seguí la cadena desde tu shell hasta PID 1.

### 1.3 Creando y observando procesos

En una terminal, ejecutá:

```bash
sleep 300 &
echo "PID del sleep: $!"
```

En otra terminal (o en la misma), usá `ps aux | grep sleep` para encontrar tu proceso. Observá:
- El estado (STAT): debería ser 'S' (sleeping)
- El tiempo de CPU: casi 0 porque sleep no hace nada

Matá el proceso con `kill <PID>` cuando termines.

### 1.4 Observando un zombie

Ejecutá este script que crea un zombie temporal:

```bash
python3 -c "
import os, time
pid = os.fork()
if pid == 0:
    os._exit(0)  # Hijo termina inmediatamente
else:
    print(f'Hijo terminado, padre durmiendo...')
    time.sleep(30)  # Padre no hace wait
" &
```

Rápidamente ejecutá `ps aux | grep Z` - deberías ver un proceso zombie (estado Z).

---

## Ejercicio 2: Tu primer fork en Python

### 2.1 Fork básico

Creá el archivo `fork_basico.py`:

```python
#!/usr/bin/env python3
"""Mi primer fork."""
import os

print(f"Proceso original: PID={os.getpid()}")

pid = os.fork()

if pid == 0:
    print(f"Soy el HIJO: PID={os.getpid()}, PPID={os.getppid()}")
else:
    print(f"Soy el PADRE: PID={os.getpid()}, hijo={pid}")

print(f"Este mensaje lo imprime PID={os.getpid()}")
```

Ejecutalo varias veces. Observá:
- ¿Siempre se imprimen los mensajes en el mismo orden?
- ¿Por qué el último mensaje aparece dos veces?

### 2.2 Agregando wait

Modificá el código para que el padre espere al hijo:

```python
#!/usr/bin/env python3
"""Fork con wait."""
import os

print(f"Proceso original: PID={os.getpid()}")

pid = os.fork()

if pid == 0:
    print(f"Hijo trabajando...")
    # Simulá trabajo
    for i in range(3):
        print(f"  Hijo: paso {i+1}")
    print(f"Hijo terminando con código 42")
    os._exit(42)
else:
    print(f"Padre esperando al hijo {pid}...")
    _, status = os.wait()

    if os.WIFEXITED(status):
        codigo = os.WEXITSTATUS(status)
        print(f"Padre: hijo terminó con código {codigo}")
```

**Pregunta:** ¿Qué pasa si cambiás `os._exit(42)` por `os._exit(0)`?

### 2.3 Múltiples hijos

Creá un programa que genere 3 hijos, cada uno con comportamiento diferente:

```python
#!/usr/bin/env python3
"""Múltiples hijos."""
import os
import time

def trabajo_hijo(numero, duracion):
    """Trabajo que hace cada hijo."""
    print(f"Hijo {numero} (PID {os.getpid()}): iniciando, durará {duracion}s")
    time.sleep(duracion)
    print(f"Hijo {numero}: terminando")
    os._exit(numero)  # Salir con código = número de hijo

# Configuración de hijos: (duración en segundos)
hijos_config = [2, 1, 3]
hijos_pids = []

# Crear los hijos
for i, duracion in enumerate(hijos_config):
    pid = os.fork()
    if pid == 0:
        trabajo_hijo(i, duracion)
        # Nunca llegamos aquí por el _exit
    else:
        hijos_pids.append(pid)
        print(f"Padre: creado hijo {i} con PID {pid}")

# Esperar a todos los hijos
print(f"\nPadre: esperando a {len(hijos_pids)} hijos...")
while hijos_pids:
    pid, status = os.wait()
    codigo = os.WEXITSTATUS(status)
    hijos_pids.remove(pid)
    print(f"Padre: hijo PID {pid} terminó con código {codigo}")

print("Padre: todos los hijos terminaron")
```

**Observación importante:** Los hijos no terminan en el orden en que fueron creados, sino en el orden en que completan su trabajo.

---

## Ejercicio 3: Fork + Exec

### 3.1 Ejecutando un comando externo

```python
#!/usr/bin/env python3
"""Fork + exec para ejecutar ls."""
import os

print(f"Padre (PID {os.getpid()}): voy a ejecutar 'ls -la'")

pid = os.fork()

if pid == 0:
    # Hijo: transformarse en ls
    print(f"Hijo (PID {os.getpid()}): haciendo exec...")
    os.execlp("ls", "ls", "-la", "/tmp")
    # Si llegamos aquí, exec falló
    print("ERROR: exec falló")
    os._exit(1)
else:
    # Padre: esperar
    _, status = os.wait()
    codigo = os.WEXITSTATUS(status)
    print(f"\nPadre: ls terminó con código {codigo}")
```

### 3.2 Función reutilizable

Creá una función que encapsule el patrón fork+exec+wait:

```python
#!/usr/bin/env python3
"""Función para ejecutar comandos."""
import os
import sys

def ejecutar(comando, args=None):
    """
    Ejecuta un comando y retorna su código de salida.

    Args:
        comando: nombre del programa a ejecutar
        args: lista de argumentos (sin incluir el comando)

    Returns:
        código de salida del comando
    """
    if args is None:
        args = []

    pid = os.fork()

    if pid == 0:
        try:
            os.execvp(comando, [comando] + args)
        except OSError as e:
            print(f"Error: {e}", file=sys.stderr)
            os._exit(127)
    else:
        _, status = os.wait()
        return os.WEXITSTATUS(status)

# Probar la función
if __name__ == "__main__":
    print("=== Ejecutando ls ===")
    codigo = ejecutar("ls", ["-la", "/tmp"])
    print(f"Código de salida: {codigo}\n")

    print("=== Ejecutando comando inexistente ===")
    codigo = ejecutar("comando_que_no_existe")
    print(f"Código de salida: {codigo}\n")

    print("=== Ejecutando echo ===")
    codigo = ejecutar("echo", ["Hola", "desde", "exec"])
    print(f"Código de salida: {codigo}")
```

---

## Ejercicio 4: Mini-shell (ejercicio guiado)

Vamos a construir un shell minimalista paso a paso.

### 4.1 El loop básico

```python
#!/usr/bin/env python3
"""Mini-shell: paso 1 - loop básico."""
import os

def main():
    while True:
        try:
            linea = input("minish$ ")
        except EOFError:
            print("\nChau!")
            break

        if not linea.strip():
            continue

        if linea.strip() == "exit":
            break

        print(f"Comando recibido: {linea}")

if __name__ == "__main__":
    main()
```

### 4.2 Agregando fork+exec

```python
#!/usr/bin/env python3
"""Mini-shell: paso 2 - fork+exec."""
import os

def main():
    while True:
        try:
            linea = input("minish$ ")
        except EOFError:
            print("\nChau!")
            break

        linea = linea.strip()
        if not linea:
            continue

        if linea == "exit":
            break

        # Parsear comando y argumentos
        partes = linea.split()
        comando = partes[0]
        args = partes[1:]

        # Fork + exec
        pid = os.fork()

        if pid == 0:
            try:
                os.execvp(comando, [comando] + args)
            except OSError as e:
                print(f"minish: {comando}: {e}")
                os._exit(127)
        else:
            _, status = os.wait()
            # Opcional: mostrar código si no es 0
            codigo = os.WEXITSTATUS(status)
            if codigo != 0:
                print(f"[código {codigo}]")

if __name__ == "__main__":
    main()
```

### 4.3 Comandos internos

El comando `cd` no puede ser externo (¿por qué?). Agregá soporte para `cd`:

```python
#!/usr/bin/env python3
"""Mini-shell: paso 3 - comandos internos."""
import os

def cmd_cd(args):
    """Implementación del comando cd."""
    if not args:
        destino = os.environ.get("HOME", "/")
    else:
        destino = args[0]

    try:
        os.chdir(destino)
    except OSError as e:
        print(f"cd: {e}")

def main():
    # Comandos internos
    internos = {
        "cd": cmd_cd,
    }

    while True:
        # Mostrar directorio actual en el prompt
        cwd = os.getcwd()
        try:
            linea = input(f"minish:{cwd}$ ")
        except EOFError:
            print("\nChau!")
            break

        linea = linea.strip()
        if not linea:
            continue

        if linea == "exit":
            break

        partes = linea.split()
        comando = partes[0]
        args = partes[1:]

        # ¿Es comando interno?
        if comando in internos:
            internos[comando](args)
            continue

        # Comando externo: fork + exec
        pid = os.fork()

        if pid == 0:
            try:
                os.execvp(comando, [comando] + args)
            except OSError as e:
                print(f"minish: {comando}: {e}")
                os._exit(127)
        else:
            _, status = os.wait()
            codigo = os.WEXITSTATUS(status)
            if codigo != 0:
                print(f"[código {codigo}]")

if __name__ == "__main__":
    main()
```

**Pregunta para pensar:** ¿Por qué `cd` debe ser un comando interno del shell y no un programa externo?

---

## Ejercicio 5: Procesamiento paralelo (Obligatorio)

### Objetivo

Crear un programa `paralelo.py` que ejecute múltiples comandos en paralelo y reporte el tiempo total.

### Especificación

```bash
# Uso
python3 paralelo.py "comando1" "comando2" "comando3" ...

# Ejemplo
python3 paralelo.py "sleep 2" "sleep 3" "echo hola"
```

El programa debe:
1. Ejecutar todos los comandos simultáneamente (no secuencialmente)
2. Esperar a que todos terminen
3. Mostrar el PID de cada comando al iniciarlo
4. Mostrar cuando cada comando termina y su código de salida
5. Al final, mostrar el tiempo total de ejecución

### Ejemplo de salida esperada

```
$ python3 paralelo.py "sleep 2" "sleep 1" "echo test"
[1234] Iniciado: sleep 2
[1235] Iniciado: sleep 1
[1236] Iniciado: echo test
test
[1236] Terminado: echo test (código: 0)
[1235] Terminado: sleep 1 (código: 0)
[1234] Terminado: sleep 2 (código: 0)

Resumen:
- Comandos ejecutados: 3
- Exitosos: 3
- Fallidos: 0
- Tiempo total: 2.01s
```

Observá que el tiempo total es ~2 segundos (el máximo), no 3+ segundos (la suma).

### Esqueleto

```python
#!/usr/bin/env python3
"""
Ejecutor de comandos en paralelo.
Uso: python3 paralelo.py "cmd1" "cmd2" ...
"""
import os
import sys
import time

def main():
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} comando1 [comando2 ...]")
        sys.exit(1)

    comandos = sys.argv[1:]
    # TODO: implementar

if __name__ == "__main__":
    main()
```

### Pistas

1. Usá un diccionario para trackear PIDs y sus comandos
2. Recordá que `os.wait()` retorna el PID del hijo que terminó
3. Para el tiempo, usá `time.time()` antes y después
4. Para parsear el comando en programa + args, usá `.split()`

---

## Ejercicio 6: Comparando con subprocess

Después de implementar el ejercicio 5 manualmente, implementá lo mismo usando `subprocess`:

```python
#!/usr/bin/env python3
"""Versión con subprocess para comparar."""
import subprocess
import sys
import time

def main():
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} comando1 [comando2 ...]")
        sys.exit(1)

    comandos = sys.argv[1:]
    inicio = time.time()

    # Iniciar todos los procesos
    procesos = []
    for cmd in comandos:
        proc = subprocess.Popen(cmd, shell=True)
        print(f"[{proc.pid}] Iniciado: {cmd}")
        procesos.append((proc, cmd))

    # Esperar a todos
    resultados = []
    for proc, cmd in procesos:
        codigo = proc.wait()
        print(f"[{proc.pid}] Terminado: {cmd} (código: {codigo})")
        resultados.append(codigo)

    duracion = time.time() - inicio

    exitosos = sum(1 for c in resultados if c == 0)
    print(f"\nResumen:")
    print(f"- Comandos ejecutados: {len(comandos)}")
    print(f"- Exitosos: {exitosos}")
    print(f"- Fallidos: {len(comandos) - exitosos}")
    print(f"- Tiempo total: {duracion:.2f}s")

if __name__ == "__main__":
    main()
```

**Reflexión:** ¿Qué versión es más simple? ¿Cuál te da más control? ¿Cuándo usarías cada una?

---

## Ejercicios adicionales

### 6.1 Contador de procesos

Creá un programa que muestre cuántos procesos están corriendo en el sistema. Pista: contá las entradas en `/proc` que son números.

### 6.2 Información de proceso

Dado un PID, mostrá información del proceso leyendo archivos de `/proc/<PID>/`:
- `cmdline`: comando completo
- `status`: estado, memoria, etc.
- `fd/`: file descriptors abiertos

### 6.3 Árbol de procesos

Implementá tu propia versión simplificada de `pstree` que muestre la jerarquía de procesos.

---

## Verificación de ejercicios obligatorios

### Ejercicio 5: paralelo.py

Verificá que tu implementación:

- [ ] Ejecuta comandos en paralelo (no secuencialmente)
- [ ] Muestra PID al iniciar cada comando
- [ ] Muestra cuando termina cada comando
- [ ] Reporta código de salida de cada comando
- [ ] Muestra tiempo total (debe ser menor que la suma de tiempos individuales)
- [ ] Maneja correctamente comandos que fallan

---

*Computación II - 2026 - Clase 3*
