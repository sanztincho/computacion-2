# Referencia Rápida: mmap y Memoria Compartida

## Tabla de Contenidos
1. [mmap - Operaciones Básicas](#mmap---operaciones-básicas)
2. [struct - Empaquetado Binario](#struct---empaquetado-binario)
3. [multiprocessing - Compartición](#multiprocessing---compartición)
4. [Snippets Útiles](#snippets-útiles)

---

## mmap - Operaciones Básicas

### Abrir y Cerrar

```python
import mmap

# Archivo existente - escritura+lectura
with open("archivo.bin", "r+b") as f:
    mm = mmap.mmap(f.fileno(), 0)  # 0 = tamaño del archivo
    # ... usar ...
    mm.close()  # O simplemente salir del with

# Archivo nuevo - crear con tamaño
with open("archivo.bin", "wb") as f:
    f.write(b'\x00' * 1024)  # Preallocar 1KB

with open("archivo.bin", "r+b") as f:
    mm = mmap.mmap(f.fileno(), 1024)
```

### Modos de Acceso

```python
mmap.mmap(fd, 0)                           # read+write (default)
mmap.mmap(fd, 0, access=mmap.ACCESS_READ)  # solo lectura
mmap.mmap(fd, 0, access=mmap.ACCESS_WRITE) # write (requiere r+ o w+b)
mmap.mmap(fd, 0, access=mmap.ACCESS_COPY)  # copy-on-write (eficiente)
```

### Operaciones de Lectura

```python
mm[0:10]           # Leer bytes 0-9
mm[:]              # Todo el contenido
mm[0]              # Byte individual (0-255)
mm.size()          # Tamaño total
mm.seek(pos)       # Mover cursor a posición
mm.tell()          # Posición actual
mm.readline()      # Próxima línea
mm.read(n)         # Leer n bytes desde posición actual
```

### Operaciones de Escritura

```python
mm[0:4] = b'TEST'          # Sobrescribir bytes
mm.write(b"datos")         # Escribir en posición actual
mm.seek(100)
mm.write(b"en offset 100")
```

### Búsqueda

```python
mm.find(b"texto")          # Primera ocurrencia (-1 si no existe)
mm.find(b"texto", 10)      # Buscar después del byte 10
mm.find(b"texto", 10, 100) # Buscar entre bytes 10-99

# Buscar todas las ocurrencias
pos = 0
while True:
    pos = mm.find(b"patrón", pos)
    if pos == -1:
        break
    print(f"Encontrado en {pos}")
    pos += 1
```

### Anónimo (sin archivo)

```python
# Crear memoria 100% anónima (se hereda con fork)
mm = mmap.mmap(-1, 1024)

# Después de fork(), ambos procesos ven los mismos datos
pid = os.fork()
if pid == 0:
    mm[0] = 42  # El padre lo verá
else:
    os.wait()
    assert mm[0] == 42
```

---

## struct - Empaquetado Binario

### Formatos Comunes

```
Character  Type      Size   Rango
-----------+----------+------+---------------------------
'i'        int       4      -2^31 a 2^31-1
'I'        uint      4      0 a 2^32-1
'f'        float     4      4-byte IEEE 754
'd'        double    8      8-byte IEEE 754
'b'        signed    1      -128 a 127
'B'        unsigned  1      0 a 255
'?'        bool      1      0 o 1
'20s'      string    20     Cadena de 20 bytes
'16p'      pstring   16     Pascal string (len + cadena)
```

### Pack (escritura)

```python
import struct

# Simple
packed = struct.pack('i', 42)                    # 4 bytes

# Múltiple
packed = struct.pack('i f 20s', 42, 3.14, b'Hola')  # 28 bytes

# Directo a buffer (MÁS EFICIENTE)
struct.pack_into('i f 20s', buffer, offset=0, 42, 3.14, b'Hola')
```

### Unpack (lectura)

```python
i_value, = struct.unpack('i', bytes)            # El , desempacha tupla

i_value, f_value, s_value = struct.unpack('i f 20s', bytes)

i_value, f_value = struct.unpack_from('i f', buffer, offset=10)
```

### Size Calculation

```python
tamaño = struct.calcsize('i f 20s')  # 28
```

### Alineamiento

```python
struct.pack('i b f', ...)    # Ineficiente: 1 byte entre 4 bytes
struct.pack('i f b', ...)    # Mejor: agrupa tipos iguales

# Especificar alineamiento explícito
struct.pack('=i f b', ...)   # = native (default)
struct.pack('<i f b', ...)   # < little-endian (Intel)
struct.pack('>i f b', ...)   # > big-endian (Motorola)
```

---

## multiprocessing - Compartición

### Value (una variable compartida)

```python
from multiprocessing import Value, Process, Lock

# Crear
contador = Value('i', 10)  # int inicializado a 10
suma = Value('d', 0.0)     # double inicializado a 0.0

# Acceder
print(contador.value)       # Leer
contador.value = 42         # Escribir

# SEGURO: con Lock
lock = Lock()
with lock:
    contador.value += 1  # Operaciones compuestas

# INSEGURO: sin Lock
contador.value += 1  # RACE CONDITION ⚠️
```

### Array (array compartido)

```python
from multiprocessing import Array, Process

# Crear
datos = Array('d', 100)  # 100 floats
numeros = Array('i', [1, 2, 3, 4, 5])  # Con valores iniciales

# Acceder como lista normal
datos[0] = 3.14
print(datos[0])

# Iterar
for valor in datos:
    print(valor)

# Slicing
subarray = [datos[i] for i in range(10)]
```

### SharedMemory (bajo nivel)

```python
from multiprocessing import shared_memory

# Creador
shm = shared_memory.SharedMemory(create=True, size=1024)
nombre_shm = shm.name  # "psm_abc123..."

# Consumidor
shm2 = shared_memory.SharedMemory(name=nombre_shm)
shm2.buf[0:10]  # Acceso directo

# Limpieza (UNO SOLO DEBE HACERLO)
shm.close()
shm.unlink()  # Destruir
```

### ShareableList (lista compartida)

```python
from multiprocessing import shared_memory

# Crear
sl = shared_memory.ShareableList([0, 3.14, "texto      ", True])

# Acceder
sl[0] = 42
sl[2] = "actualizado"

# Los tipos se fijan en creación - error si cambias tipo
# sl[0] = 3.14  # TypeError: no se puede poner float en int

# Limpieza
sl.shm.close()
sl.shm.unlink()
```

### Process

```python
from multiprocessing import Process

def worker(nombre):
    print(f"Hola {nombre}")

p = Process(target=worker, args=("Alice",))
p.start()   # Iniciar
p.join()    # Esperar
p.is_alive()       # Aún ejecutando?
p.terminate()      # Terminar (SIGTERM)
p.kill()           # Matar (SIGKILL)
```

---

## Snippets Útiles

### Contador Seguro

```python
def incrementar_seguro(contador, lock, n):
    for _ in range(n):
        with lock:
            contador.value += 1
```

### Computación Data-Parallel

```python
from multiprocessing import Process, Array
import math

def calcular_rango(resultado, inicio, fin):
    for i in range(inicio, fin):
        resultado[i] = math.sin(i * 0.01)

# 4 procesos calculan en paralelo
arr = Array('d', 1000)
procesos = []
chunk = 250

for i in range(4):
    p = Process(target=calcular_rango, args=(arr, i*chunk, (i+1)*chunk))
    p.start()
    procesos.append(p)

for p in procesos:
    p.join()
```

### Comunicación Padre-Hijo con mmap

```python
import os, struct, mmap

mm = mmap.mmap(-1, 256)

pid = os.fork()
if pid == 0:
    # HIJO
    struct.pack_into('i', mm, 0, 42)
    os._exit(0)
else:
    # PADRE
    os.wait()
    valor = struct.unpack_from('i', mm, 0)[0]
    print(f"Recibí: {valor}")
    mm.close()
```

### Dump Hexadecimal

```python
def hex_dump(data, width=16):
    for i in range(0, len(data), width):
        chunk = data[i:i+width]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"{i:04x}: {hex_str:<{width*3}} {ascii_str}")

mm.seek(0)
hex_dump(mm[:64])
```

### Verificar Integridad

```python
import struct

FORMATO = 'i f 20s'
TAMAÑO = struct.calcsize(FORMATO)

# Escribir
for i in range(10):
    offset = i * TAMAÑO
    struct.pack_into(FORMATO, mm, offset, i, float(i), b"nombre")

# Verificar
for i in range(10):
    offset = i * TAMAÑO
    id_val, valor, _ = struct.unpack_from(FORMATO, mm, offset)
    assert id_val == i
    assert abs(valor - float(i)) < 1e-6
    print(f"✓ Registro {i} OK")
```

### Profiling

```python
import time

inicio = time.time()
# ... operación ...
duracion = time.time() - inicio

print(f"Duración: {duracion:.4f}s")
print(f"Operaciones/seg: {N / duracion:.0f}")
```

---

## Decisión Rápida: ¿Qué Use?

```
¿Necesitas leer/escribir un archivo grande?
  → mmap

¿Un contador compartido entre procesos?
  → Value('i', 0)

¿Un array de números compartido?
  → Array('d', N)

¿Máxima compatibilidad con C/C++?
  → SharedMemory

¿Datos mixtos (int, float, string)?
  → ShareableList O mmap + struct

¿Comunicación padre-hijo con fork()?
  → mmap(-1, N) anónimo

¿Máximo rendimiento?
  → mmap + struct

¿Máxima facilidad de uso?
  → Value/Array de multiprocessing

¿Sincronización compleja?
  → Lock() + Semaphore()
```

---

## Errores Comunes y Soluciones

| Error | Causa | Solución |
|-------|-------|----------|
| `ValueError: mmap length is negative` | Archivo vacío | Preallocar: `f.write(b'\x00' * tamaño)` |
| `TypeError: cannot unpack 5 to sequence` | Formato struct incorrecto | Contar campos: `'i f 20s'` = 3 valores |
| Race condition en suma | Sin sincronización | Usar Lock o sumarizar localmente |
| Memory leak (SharedMemory) | Olvidó unlink() | Siempre: `shm.unlink()` después de close() |
| `PermissionError` en /tmp | Permisos insuficientes | Usar `/dev/shm/` o directorio local |
| Proceso cuelga indefinidamente | Deadlock | Revisar locks y esperas |

---

## Test Rápido

```bash
# Copiar y pegar en terminal para verificar setup

python3 -c "import mmap; print('mmap: OK')"
python3 -c "import struct; print('struct: OK')"
python3 -c "import multiprocessing; print('multiprocessing: OK')"
python3 -c "from multiprocessing import shared_memory; print('shared_memory: OK')"
```

Si todos dicen OK, estás listo para ejecutar los ejercicios.

---

**Última actualización**: 12 de mayo de 2026
