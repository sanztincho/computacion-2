# Documentación: Ejercicios de mmap y Memoria Compartida

## Índice
1. [Conceptos Fundamentales](#conceptos-fundamentales)
2. [Ejercicio 1: mmap sobre Archivos](#ejercicio-1-mmap-sobre-archivos)
3. [Ejercicio 2: mmap como Estructura Binaria](#ejercicio-2-mmap-como-estructura-binaria)
4. [Ejercicio 3: mmap Anónimo entre Procesos](#ejercicio-3-mmap-anonimo-entre-procesos)
5. [Ejercicio 4: mmap con multiprocessing](#ejercicio-4-mmap-con-multiprocessing)
6. [Ejercicio 5: Value y Array Compartidos](#ejercicio-5-value-y-array-compartidos)
7. [Ejercicio 6: SharedMemory y ShareableList](#ejercicio-6-sharedmemory-y-shareablelist)
8. [Comparación de Tecnologías](#comparacion-de-tecnologias)
9. [Mejores Prácticas](#mejores-practicas)

---

## Conceptos Fundamentales

### ¿Qué es mmap?

**mmap** (memory mapping) es una técnica que permite mapear archivos (o regiones de memoria) en el espacio de direcciones de un proceso. En lugar de leer/escribir usando syscalls tradicionales, el contenido del archivo aparece como si fuera memoria normal.

**Ventajas:**
- Acceso transparente como memoria normal
- No requiere llamadas al sistema por cada acceso
- Permite compartir datos entre procesos
- Muy eficiente para archivos grandes
- Sincronización automática con el archivo

**Características clave:**
```python
mmap.mmap(fileno, length, flags=MAP_SHARED, prot=PROT_READ|PROT_WRITE, access=ACCESS_WRITE)
```

- `fileno`: File descriptor (-1 para anónimo)
- `length`: Bytes a mapear (0 = tamaño del archivo)
- `access`: ACCESS_READ (solo lectura), ACCESS_WRITE (lectura/escritura), ACCESS_COPY (copy-on-write)

### Procesos e IPC

**IPC (Inter-Process Communication)** es el mecanismo para que procesos independientes se comuniquen:

1. **Pipes**: Unidireccionales, basados en flujo
2. **Sockets**: Red-based, bidireccionales
3. **Memoria compartida**: Acceso directo a la misma región de memoria
4. **Archivos**: Persistencia, lentitud
5. **Message Queues**: Sistema de colas

---

## Ejercicio 1: mmap sobre Archivos

### Descripción

Este ejercicio introduce mmap con archivos reales en disco:

1. **Lectura completa** del archivo mapeado
2. **Lectura línea por línea** usando `readline()`
3. **Búsqueda** de texto con `find()`
4. **Modificación** in-situ del contenido
5. **Modo solo-lectura** con `ACCESS_READ`

### Archivo: `ejercicio_1_mmap_basico.py`

### Conceptos Clave

#### Creación del mmap
```python
with open(archivo, "r+b") as f:
    mm = mmap.mmap(f.fileno(), 0)  # 0 = tamaño del archivo
    # ... usar mm ...
    mm.close()
```

#### Operaciones principales
```python
# Lectura
contenido = mm[:]           # Todo el contenido
linea = mm.readline()       # Próxima línea
mm.seek(posicion)           # Mover cursor

# Búsqueda
pos = mm.find(b"texto")     # Encontrar primera ocurrencia

# Escritura (requiere r+b, no rb)
mm[pos:pos+4] = b"TEST"    # Sobrescribir in-situ
mm.write(b"datos")         # Escribir en posición actual

# Acceso controlado
mm.ACCESS_READ              # Solo lectura (error al escribir)
mm.ACCESS_WRITE             # Lectura y escritura
mm.ACCESS_COPY              # Copy-on-write
```

### Flujo de Ejecución

```
1. Crear archivo con 5 líneas de texto
   └─> /tmp/ejercicio1_archivo.txt (100 bytes aprox.)

2. Mapear con r+b → lectura y escritura
   └─> mm = mmap.mmap(f.fileno(), 0)

3. Leer línea por línea
   └─> Mostrar cada línea usando readline()

4. Buscar palabra específica
   └─> Encontrar posición con find()

5. Reemplazar palabra
   └─> Sobrescribir bytes en la posición encontrada
   └─> Verificar cambio con cat

6. Mapear en READ-ONLY
   └─> Intentar escribir → TypeError ✓
```

### Observaciones Importantes

- El cambio en el mmap **se refleja inmediatamente en el archivo**
- No hay buffer: el archivo cambia en tiempo real
- Con `ACCESS_READ`: intentar escribir lanza `TypeError`
- `readline()` incluye el `\n` en el resultado
- Mejor usar con archivos de **tamaño conocido y fijo**

---

## Ejercicio 2: mmap como Estructura Binaria

### Descripción

Este ejercicio demuestra mmap como almacenamiento estructurado usando `struct`:

1. Definir un "registro" con múltiples campos
2. Escribir registros en formato binario
3. Leer y acceder a los campos
4. Modificar registros individuales

### Archivo: `ejercicio_2_mmap_binario.py`

### Concepto: struct.pack_into() y unpack_from()

```python
import struct

# Pack: escribir valores en binario en posición específica
# Formato: 'i' (int, 4 bytes) + 'f' (float, 4 bytes) + '20s' (string, 20 bytes)
struct.pack_into('i f 20s', mm, offset, 42, 3.14, b'texto   ')

# Unpack: leer valores binarios desde posición
id_val, nota, nombre = struct.unpack_from('i f 20s', mm, offset)
```

### Estructura de Registro

```
┌─────────────────────────────────────────────────┐
│ REGISTRO (28 bytes)                             │
├────────────┬────────────┬──────────────────────┤
│ ID (int)   │ Nota (f)   │ Nombre (20s)        │
│ 4 bytes    │ 4 bytes    │ 20 bytes            │
└────────────┴────────────┴──────────────────────┘

Offset:  0         4         8                    28
```

### Flujo de Ejecución

```
1. Crear archivo binario
   └─> Tamaño = 5 registros × 28 bytes = 140 bytes

2. Mapear archivo en r+b
   └─> mm = mmap.mmap(fd, 140)

3. Escribir 5 registros
   FOR i = 0 to 4:
      offset = i * 28
      struct.pack_into('i f 20s', mm, offset, id, nota, nombre)

4. Leer registros
   FOR i = 0 to 4:
      offset = i * 28
      id, nota, nombre = struct.unpack_from('i f 20s', mm, offset)

5. Modificar un registro
   offset = 2 * 28
   Escribir nueva nota en ese offset
```

### Ventajas

- **Acceso directo O(1)**: sin necesidad de parsear
- **Compacto**: formato binario = menor tamaño
- **Rápido**: acceso mediante cálculo simple de offset
- **Estructurado**: formato fijo y predecible

### Consideraciones

- Los strings se rellenan con `\x00` si son más cortos
- El alineamiento es importante para portabilidad
- Usar `'='` en el formato para alineamiento específico de la plataforma

---

## Ejercicio 3: mmap Anónimo entre Procesos

### Descripción

Demuestra la comunicación padre-hijo mediante mmap **anónimo** (sin archivo):

1. **3.1**: Comunicación simple padre-hijo
2. **3.2 Mejorado**: Múltiples hijos calculan sumas en paralelo

### Archivo: `ejercicio_3_mmap_anonimo.py`

### mmap Anónimo vs mmap en Archivo

```python
# Archivo (persistente)
mm = mmap.mmap(fd, tamaño)    # fd > 0

# Anónimo (solo en memoria, heredado por fork)
mm = mmap.mmap(-1, tamaño)    # fd = -1
```

**Características del anónimo:**
- `-1` como descriptor de archivo → sin archivo en disco
- Solo existe en memoria RAM
- Se hereda automáticamente con `fork()`
- Se destruye al cerrar el proceso raíz
- Perfecto para IPC entre padre-hijo
- NO se puede compartir con `exec()`

### Flujo: Ejercicio 3.1

```
PROCESO PADRE
  ├─ mm = mmap.mmap(-1, 256)    [Memoria anónima]
  ├─ pid = fork()
  │
  ├─ if pid > 0:  [PADRE]
  │    ├─ wait()              [Esperar hijo]
  │    └─ Leer datos de mm    [ID 0, largo 4, mensaje en mm[8:]]
  │
  └─ else:        [HIJO, pid == 0]
       ├─ Escribir ID en mm[0:4]
       ├─ struct.pack_into('i', mm, 4, len(msg))
       ├─ mm[8:8+len(msg)] = mensaje
       └─ _exit(0)
```

### Flujo: Ejercicio 3.2 (Suma de Rangos)

```
PADRE:
  ├─ mm = mmap.mmap(-1, TAMAÑO_TOTAL)
  ├─ PARA i = 0 a 3:
  │   ├─ fork()
  │   └─ if HIJO:
  │        ├─ offset = i * TAMAÑO_POR_HIJO
  │        ├─ inicio = i * RANGO_TOTAL/4 + 1
  │        ├─ suma = sum(range(inicio, fin))
  │        ├─ Escribir ID, PID, rango, SUMA en mm[offset]
  │        └─ _exit(0)
  │
  └─ Esperar a todos, leer sumas, sumarlas

RESULTADO: Suma total = suma del padre
```

### Observaciones Clave

```python
# Herencia automática con fork()
mm = mmap.mmap(-1, 1024)
pid = fork()
# Ahora AMBOS procesos ven los MISMOS datos en mm

# Pero con exec(), se pierde (descriptores no heredados)
# Para ejecutables separados, usar mmap en archivo shared
```

---

## Ejercicio 4: mmap con multiprocessing

### Descripción

Usa `multiprocessing.Process` con mmap basado en **archivos compartidos**:

1. Crear archivo compartido
2. Cada proceso abre el mismo archivo
3. Escribir en regiones diferentes
4. Padre lee resultados

### Archivo: `ejercicio_4_mmap_multiprocessing.py`

### Por qué archivos en MultiProcessing

Con `fork()`, el mmap se hereda. Pero `multiprocessing.Process` usa:
- **En Unix/Linux**: `fork()` (sí hereda)
- **En Windows**: `spawn()` (NO hereda)

Para portabilidad, mejor abrir el archivo en cada proceso:

```python
def worker(archivo, offset, datos):
    # Cada proceso abre el archivo independientemente
    with open(archivo, "r+b") as f:
        mm = mmap.mmap(f.fileno(), tamaño)
        # Escribir en mm[offset:offset+len]...
        mm.close()
```

### Flujo de Ejecución

```
PADRE:
  ├─ Crear /tmp/mmap_mp.bin (256 bytes)
  ├─ PARA 4 procesos:
  │   └─ p = Process(target=escribir, args=(archivo, offset_i, msg_i))
  │
  ├─ Todos escriben en regiones diferentes
  │   P0: mm[0:64]    = datos_0
  │   P1: mm[64:128]  = datos_1
  │   P2: mm[128:192] = datos_2
  │   P3: mm[192:256] = datos_3
  │
  └─ PADRE abre y lee todos los datos
```

### Sincronización Implícita

```python
for p in procesos:
    p.join()  # Esperar a que terminen todos
```

Sin sincronización explícita, el padre debe esperar a que todos escriban antes de leer.

### Variación: Escrituras Intercaladas

En lugar de regiones contiguas, cada proceso escribe en posiciones intercaladas:
- P0 escribe en posiciones 0, 16, 32, ...
- P1 escribe en posiciones 4, 20, 36, ...
- Etc.

Útil para reproducibilidad y cache locality.

---

## Ejercicio 5: Value y Array Compartidos

### Descripción

Usa el módulo `multiprocessing.Value` y `Array` para compartir datos simples.

### Archivo: `ejercicio_5_value_array.py`

### Value: Contador Compartido

```python
from multiprocessing import Value, Process

contador = Value('i', 0)  # Shared int, initialized to 0

def incrementar(contador):
    contador.value += 1  # Acceso sincronizado por bajo nivel

# Pero:
for _ in range(1000):
    contador.value += 1  # RACE CONDITION!
```

### El Problema: Race Condition

```
Operación: contador.value += 1

Sin sincronización:
  TIEMPO | PROCESO A        | PROCESO B        | CONTADOR
  -------|------------------|------------------|--------
    1    | Lee: 10          |                  | 10
    2    |                  | Lee: 10          | 10
    3    | Escribe: 11      |                  | 11
    4    |                  | Escribe: 11      | 11 ✗ (Debería ser 12!)

Con Lock:
  t1     | Adquire lock     |                  |
  t2     | Lee: 10, suma, escribe 11         | 11
  t3     | Suelta lock      |                  |
  t4     |                  | Adquiere lock    |
  t5     |                  | Lee: 11, suma, escribe 12 | 12 ✓
```

### Array: Parallelismo Data-Parallel

```python
resultado = Array('d', 100)  # 100 floats, shared

def calcular(resultado, inicio, fin):
    for i in range(inicio, fin):
        resultado[i] = math.sin(i * 0.01)

# Cada proceso accede a su región sin conflictos
# Array es seguro si no hay overlaps
```

### Bonus: Suma con Race Condition

```python
suma = Value('d', 0.0)

def calcular_con_suma(resultado, suma, inicio, fin):
    suma_local = sum(math.sin(i * 0.01) for i in range(inicio, fin))
    
    # PELIGRO: Race condition aquí
    suma.value += suma_local
```

### Resultados de Ejecución

**Ejercicio 5.1 (Carrera):**
```
Esperado: 400000
Obtenido: 399912
Perdidos: 88 (0.022%)
```

Varía según la carga del sistema. A mayor valor de N, mayor la probabilidad de detectar la race condition.

---

## Ejercicio 6: SharedMemory y ShareableList

### Descripción

Usa `multiprocessing.shared_memory` para máximo control:
- `SharedMemory`: Acceso bajo-nivel a caché de memoria
- `ShareableList`: Lista Python compartida

### Archivo: `ejercicio_6_shared_memory.py`

### SharedMemory vs Value/Array

```python
# Value/Array (alto nivel)
contador = Value('i', 0)
array = Array('d', 100)
# ✓ Simple
# ✗ Limitado a tipos básicos

# SharedMemory (bajo nivel)
shm = shared_memory.SharedMemory(create=True, size=1024)
# ✓ Máximo control
# ✗ Requiere gestión manual (unlink)
```

### Ciclo de Vida

```python
# CREADOR
shm = shared_memory.SharedMemory(create=True, size=1024)
nombre = shm.name  # "psm_abc123" (generado automáticamente)

# CONSUMIDOR (otro proceso)
shm = shared_memory.SharedMemory(name=nombre)

# LIMPIEZA (cuando termina el primero)
shm.close()        # Cerrar acceso
shm.unlink()       # Destruir la memoria (¡UNO SOLO DEBE HACERLO!)
```

### Comunicación: Polling vs Señales

**Polling** (simple pero ineficiente):
```python
while shm.buf[-1] != 1:
    time.sleep(0.01)  # "¿Terminaste? ¿Y ahora? ¿Y ahora?"
```

**Señales** (eficiente):
```python
from multiprocessing import Event
evento = Event()
evento.wait()  # Bloquea hasta que set()
```

### ShareableList: Tipos Mixtos

```python
sl = shared_memory.ShareableList(
    [0, 0.0, "          ", True]
)

# Acceso como lista normal
sl[0] = 42
sl[2] = "actualizado"

# Los tipos son fijados en creación:
# - int siempre int
# - float siempre float
# - str máximo largo del original
```

### Cuándo Usar Cada Una

```
┌──────────────┬────────────────────┬─────────────────────┐
│   Opción     │  Problema Resuelto │     Trade-off        │
├──────────────┼────────────────────┼─────────────────────┤
│ mmap         │ Archivos grandes   │ Requiere archivo    │
│ Value/Array  │ Tipos simples      │ Limitado, alto nivel│
│ SharedMemory │ Máximo control     │ Bajo nivel, verboso │
│ShareableList│ Tipos mixtos       │ Alto nivel, claro   │
└──────────────┴────────────────────┴─────────────────────┘
```

---

## Comparación de Tecnologías

### Matriz de Características

```
┌────────────────────┬────────┬──────────┬──────────┬────────┐
│ Característica     │ mmap   │ Value    │ SharedMem│Share.L │
├────────────────────┼────────┼──────────┼──────────┼────────┤
│ Persistencia       │ SÍ     │ NO       │ NO       │ NO     │
│ Portabilidad       │ BUENA  │ PERFECTA │ BUENA    │PERFECTA
│ Control            │ ALTO   │ BAJO     │ MÁXIMO   │ MEDIO  │
│ Facilidad          │ MEDIA  │ ALTA     │ BAJA     │ MEDIA  │
│ Tipo de datos      │ TODOS  │ BÁSICOS  │ TODOS    │ MIXTOS │
│ Lock automático    │ SÍ(OS) │ SÍ       │ NO       │ Parcial
│ Rendimiento        │ ÓPTIMO │ BUENO    │ ÓPTIMO   │ BUENO  │
│ Tamaño máximo      │ ∞      │ Limited  │ ∞        │ ∞      │
└────────────────────┴────────┴──────────┴──────────┴────────┘
```

### Casos de Uso Recomendados

| Tecnología   | Cuándo Usar |
|--------------|------------|
| **mmap**     | • Leer/escribir archivos grandes<br>• Datos que deben persistir<br>• Acceso directo sin syscalls |
| **Value**    | • Contador compartido<br>• Variable simple<br>• Máxima portabilidad |
| **Array**    | • Computación data-parallel<br>• Regiones no solapadas<br>• Acceso sin conflictos |
| **SharedMemory** | • Máximo control sobre memoria<br>• Interoperabilidad C/C++<br>• Sincronización manual |
| **ShareableList** | • Datos mixtos<br>• Acceso desde múltiples procesos<br>• Facilidad de uso |

---

## Mejores Prácticas

### 1. Sincronización

```python
# ✓ BIEN: Usar Lock para accesos conflictivos
from multiprocessing import Lock

contador = Value('i', 0)
lock = Lock()

def incrementar_seguro():
    with lock:
        contador.value += 1  # Protegido

# ✗ MAL: Sin sincronización
def incrementar_inseguro():
    contador.value += 1  # Race condition
```

### 2. Gestión de Memoria Compartida

```python
# ✓ BIEN: Limpieza en try/finally
try:
    shm = shared_memory.SharedMemory(create=True, size=1024)
    # ... usar shm ...
finally:
    shm.close()
    shm.unlink()

# ✗ MAL: Sin limpieza
shm = shared_memory.SharedMemory(create=True, size=1024)
# Si hay excepción, la memoria queda "zombi"
```

### 3. Tamaños Adecuados

```python
# ✓ BIEN: Reservar espacio suficiente
tamaño = NUM_ELEMENTOS * struct.calcsize('i ff 50s')
mm = mmap.mmap(-1, tamaño)

# ✗ MAL: Asumir tamaño
mm = mmap.mmap(-1, 100)  # ¿Suficiente? ¿Mucho?
```

### 4. Alineamiento de Datos

```python
# ✓ BIEN: Considerar alineamiento
# 'i' = 4 bytes, 'f' = 4 bytes, '20s' = 20 bytes
# Total = 28 bytes (bien alineado)

# ✗ MAL: Alineamiento incorrecto
struct.pack_into('i b f', mm, 0, 1, 2, 3.0)
# 'b' (1 byte) entre 'i' (4) y 'f' (4) → ineficiente
```

### 5. Depuración

```python
# ✓ Ver contenido del mmap
hex_dump = mm[:64].hex()
print(f"Bytes: {hex_dump}")

# ✓ Verificar estado del archivo
import os
stat = os.stat(archivo)
print(f"Tamaño: {stat.st_size}, Mtime: {stat.st_mtime}")

# ✓ Usar context managers
with open(archivo, 'r+b') as f:
    mm = mmap.mmap(f.fileno(), 0)
    # ... aquí ...
    # mm.close() automático al salir
```

### 6. Portabilidad

```python
# ✓ BIEN: Portable
value = Value('i', 0)       # Funciona en Unix/Windows
array = Array('d', 100)     # Funciona en Unix/Windows

# MAYORMENTE: Heramientas de bajo nivel
mm = mmap.mmap(-1, 1024)    # Funciona en Unix/Linux
# En Windows hace falta MAP_ANONYMOUS

# ✗ EVITAR: Asumir fork()
# Windows no tiene fork() nativo, usa spawn()
```

---

## Resumen de Archivos

```
ejercicio_1_mmap_basico.py        → Lectura, búsqueda, modificación
ejercicio_2_mmap_binario.py       → Estructuras binarias con struct
ejercicio_3_mmap_anonimo.py       → Comunicación padre-hijo
ejercicio_4_mmap_multiprocessing.py → multiprocessing.Process
ejercicio_5_value_array.py        → Value y Array, race conditions
ejercicio_6_shared_memory.py      → SharedMemory y ShareableList
DOCUMENTACION.md                  → Este archivo
```

---

## Ejecución de Pruebas

```bash
# Para ejecutar cada ejercicio:

cd /home/sanztincho/coding/Computacion-2/clase_06_mmap_memoria_compartida/practica

python3 ejercicio_1_mmap_basico.py
python3 ejercicio_2_mmap_binario.py
python3 ejercicio_3_mmap_anonimo.py
python3 ejercicio_4_mmap_multiprocessing.py
python3 ejercicio_5_value_array.py
python3 ejercicio_6_shared_memory.py
```

**Nota**: El ejercicio 5.1 puede mostrar diferentes resultados entre ejecuciones debido a las race conditions.

---

## Recursos Adicionales

- [Python mmap documentation](https://docs.python.org/3/library/mmap.html)
- [multiprocessing shared_memory](https://docs.python.org/3/library/multiprocessing.shared_memory.html)
- [struct — Interpret bytes as packed binary data](https://docs.python.org/3/library/struct.html)
- [mmap(2) - Man pages](https://man7.org/linux/man-pages/man2/mmap.2.html)

---

**Última actualización**: 12 de mayo de 2026
**Autor**: Soluciones de Ejercicios - Computación 2
