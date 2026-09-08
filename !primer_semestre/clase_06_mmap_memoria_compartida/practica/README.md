# README - Ejercicios de mmap y Memoria Compartida

## 📋 Descripción General

Este directorio contiene soluciones completas y documentadas para los ejercicios de **mmap** (memory mapping) y **memoria compartida** en Python.

Cubre desde conceptos básicos (mapear archivos) hasta IPC avanzado con múltiples procesos y sincronización.

---

## 📁 Contenido

### Ejercicios Resueltos

| Archivo | Tema | Dificultad |
|---------|------|-----------|
| `ejercicio_1_mmap_basico.py` | Mapeo de archivos, lectura/escritura, modo solo-lectura | ⭐ Básico |
| `ejercicio_2_mmap_binario.py` | Estructuras binarias con `struct`, registros fijos | ⭐⭐ Intermedio |
| `ejercicio_3_mmap_anonimo.py` | Comunicación padre-hijo con fork, cálculo paralelo | ⭐⭐⭐ Avanzado |
| `ejercicio_4_mmap_multiprocessing.py` | `multiprocessing.Process` con archivos compartidos | ⭐⭐ Intermedio |
| `ejercicio_5_value_array.py` | Value y Array compartidos, race conditions | ⭐⭐⭐ Avanzado |
| `ejercicio_6_shared_memory.py` | SharedMemory y ShareableList de bajo nivel | ⭐⭐⭐ Avanzado |

### Documentación

- **`DOCUMENTACION.md`**: Guía completa con explicaciones técnicas de cada ejercicio
- **`README.md`**: Este archivo - guía rápida

---

## 🚀 Cómo Ejecutar

### Requisitos
- Python 3.6+
- Linux/Unix (algunos ejercicios requieren `fork()`)
- Terminal/Shell

### Ejecución Individual

```bash
# Navegar al directorio
cd /home/sanztincho/coding/Computacion-2/clase_06_mmap_memoria_compartida/practica

# Ejecutar un ejercicio específico
python3 ejercicio_1_mmap_basico.py

# O todos en secuencia
for i in 1 2 3 4 5 6; do
    echo "=== EJERCICIO $i ==="
    python3 ejercicio_${i}_*.py
    echo ""
done
```

### Ejecución con Depuración

```bash
# Con traceback detallado
python3 -u ejercicio_1_mmap_basico.py

# Con debug statements
python3 -v ejercicio_3_mmap_anonimo.py  # Muy verboso
```

---

## 📊 Resumen de Aprendizaje

### Ejercicio 1: Fundamentos de mmap
```
✓ Aprendes:  Mapear archivos en memoria
✓ Prácticas: Lectura, búsqueda, modificación
✓ Duración:  ~5 minutos
```

**Output esperado:**
```
Contenido a través de mmap:
Linea 1: Hola mundo
Linea 2: Computacion II
...

Palabra 'es' encontrada en posición: 47
Reemplazando 'genial' por 'molon!'
```

---

### Ejercicio 2: Datos Estructurados
```
✓ Aprendes:  Almacenar estructuras binarias
✓ Prácticas: struct.pack_into/unpack_from
✓ Duración:  ~5 minutos
```

**Output esperado:**
```
ESCRITURA de registros
  Registro 0: ID=1, Nota=85.5, Nombre='Alice Johnson'
  Registro 1: ID=2, Nota=92.3, Nombre='Bob Smith'
...

Promedio de notas: 88.12
```

---

### Ejercicio 3: IPC entre Procesos
```
✓ Aprendes:  Comunicación padre-hijo con fork()
✓ Prácticas: Cálculo paralelo, sincronización básica
✓ Duración:  ~10 minutos
```

**Output esperado:**
```
[HIJO ...] Escribiendo datos...
[PADRE] Hijo terminó, leyendo datos...
[PADRE] Número: 42
[PADRE] Mensaje: Hola desde el hijo!

Suma total calculada: 5050
Suma esperada:       5050
Coincide: ✓ SÍ
```

---

### Ejercicio 4: Multiprocessing
```
✓ Aprendes:  multiprocessing.Process con archivos compartidos
✓ Prácticas: Escritura desde múltiples procesos
✓ Duración:  ~10 minutos
```

**Output esperado:**
```
[Proceso 0] Escribí: 'Hola desde proceso 0' (PID: 12345)
[Proceso 1] Escribí: 'Saludos del proceso 1' (PID: 12346)
...

Datos escritos:
  Entrada 0: ID=0, PID=12345, Mensaje='Hola desde proceso 0'
```

---

### Ejercicio 5: Race Conditions
```
✓ Aprendes:  Condiciones de carrera en memoria compartida
✓ Prácticas: Detectar y analizar race conditions
✓ Duración:  ~15 minutos
```

**Output esperado (varía por race condition):**
```
Esperado: 400000
Obtenido: 399912
Diferencia: 88 (incrementos perdidos)
Porcentaje perdido: 0.02%

⚠️  RACE CONDITION DETECTADA:
    Los procesos interfieren entre sí...
```

---

### Ejercicio 6: SharedMemory
```
✓ Aprendes:  SharedMemory y ShareableList
✓ Prácticas: Control bajo-nivel de memoria
✓ Duración:  ~10 minutos
```

**Output esperado:**
```
[CONSUMIDOR] Esperando datos...
[PRODUCTOR] Escribiendo 10 valores...
[PRODUCTOR] Datos escritos, marco como listo

[CONSUMIDOR] Datos leídos: [0, 1, 4, 9, 16]... (mostrando primeros 5)

Antes:   [0, 0.0, '          ', True]
Después: [42, 3.14159, 'actualizado', False]
```

---

## 🔍 Puntos Clave a Recordar

### mmap
- Mapea archivos (o memoria) en el espacio de direcciones
- Acceso transparente como memoria normal
- Con `mmap(-1, ...)` = anónimo (se hereda con `fork()`)
- Cambios se reflejan inmediatamente en el archivo

### Structs Binarios
- `struct.pack_into(fmt, buffer, offset, *values)` = escribir
- `struct.unpack_from(fmt, buffer, offset)` = leer
- Formatos: `'i'` (int), `'f'` (float), `'d'` (double), `'20s'` (string de 20 bytes)

### Multiprocessing
- `Value`: Una variable compartida
- `Array`: Un array compartido
- `SharedMemory`: Control bajo-nivel
- SIEMPRE usar `lock` para acceso sincronizado a datos mutables

### Common Pitfalls
```python
# ❌ Sin sincronización
valor.value += 1  # RACE CONDITION

# ✅ Con sincronización
with lock:
    valor.value += 1

# ❌ Memory leak
shm = shared_memory.SharedMemory(create=True, size=1024)
# Si sale la función sin unlink, la memoria queda ocupada

# ✅ Limpieza adecuada
try:
    shm = shared_memory.SharedMemory(create=True, size=1024)
    # ... usar ...
finally:
    shm.close()
    shm.unlink()
```

---

## 📚 Documentación Detallada

Para explicaciones profundas de cada ejercicio, ver:

**[DOCUMENTACION.md](DOCUMENTACION.md)**

Este archivo incluye:
- Conceptos fundamentales
- Flujos de ejecución paso a paso
- Explicación de cada técnica
- Comparación de tecnologías
- Mejores prácticas
- Tablas de referencia

---

## 🐛 Troubleshooting

### "no module named 'multiprocessing'"
```bash
# En sistemas Debian/Ubuntu
sudo apt install python3-dev
```

### "PermissionError: [Errno 13] Permission denied"
```bash
# Algunos sistemas restriccionan /tmp
# Cambiar ARCHIVO = "/tmp/..." a ARCHIVO = "/dev/shm/..."
```

### "OSError: [Errno 28] No space left on device"
```bash
# El archivo compartido es muy grande
# Reducir tamaño o liberar espacio en /tmp
```

### Race condition no se ve
```bash
# Aumentar N en ejercicio 5.1
N = 1000000  # en lugar de 100000
```

---

## 🎯 Próximas Pasos

Después de estos ejercicios, interesantes tópicos para explorar:

1. **Locks y Semaphores** en multiprocessing
2. **Queues** para comunicación entre procesos
3. **Pipes** para flujos de datos
4. **Signals** para manejo de eventos
5. **Async/await** con multiprocessing

---

## 📖 Referencias

- [Python mmap docs](https://docs.python.org/3/library/mmap.html)
- [multiprocessing docs](https://docs.python.org/3/library/multiprocessing.html)
- [struct docs](https://docs.python.org/3/library/struct.html)
- Linux man pages: `man mmap`, `man fork`

---

**Creado**: 12 de mayo de 2026 | **Estado**: Completo y Documentado ✓
