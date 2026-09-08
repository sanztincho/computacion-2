#!/usr/bin/env python3
"""
Ejercicio 2: mmap como estructura de datos binaria
Tarea: Almacenar un "registro" con: entero (id), float (nota) y 20 bytes de texto (nombre).
Escribir 5 registros y leerlos.
"""
import mmap
import struct
import os

print("=" * 60)
print("EJERCICIO 2: mmap como estructura de datos binaria")
print("=" * 60)

# Definición de registro
# Formato: 'i f 20s' = entero (4 bytes) + float (4 bytes) + texto (20 bytes) = 28 bytes
FORMATO = 'i f 20s'
TAMAÑO_REGISTRO = struct.calcsize(FORMATO)  # 28 bytes
NUM_REGISTROS = 5
TAMAÑO_TOTAL = TAMAÑO_REGISTRO * NUM_REGISTROS

ARCHIVO = "/tmp/registros.bin"

print(f"\nConfiguración:")
print(f"  Formato: {FORMATO}")
print(f"  Tamaño por registro: {TAMAÑO_REGISTRO} bytes")
print(f"  Cantidad de registros: {NUM_REGISTROS}")
print(f"  Tamaño total: {TAMAÑO_TOTAL} bytes")

# Crear archivo vacío
with open(ARCHIVO, "wb") as f:
    f.write(b'\x00' * TAMAÑO_TOTAL)

print(f"\nArchivo creado: {ARCHIVO}")

# Datos a escribir
datos_registros = [
    (1, 85.5, "Alice Johnson"),
    (2, 92.3, "Bob Smith"),
    (3, 78.9, "Carol White"),
    (4, 88.7, "David Brown"),
    (5, 95.2, "Eve Miller"),
]

print("\n" + "=" * 60)
print("ESCRITURA de registros")
print("=" * 60)

with open(ARCHIVO, "r+b") as f:
    mm = mmap.mmap(f.fileno(), TAMAÑO_TOTAL)

    for indice, (id_val, nota, nombre) in enumerate(datos_registros):
        offset = indice * TAMAÑO_REGISTRO
        
        # Preparar el nombre (máximo 20 bytes)
        nombre_bytes = nombre.encode()[:20]
        
        # Empacar: id (i), nota (f), nombre (20s)
        struct.pack_into(FORMATO, mm, offset, id_val, nota, nombre_bytes)
        
        print(f"  Registro {indice}: ID={id_val}, Nota={nota}, Nombre='{nombre}'")
    
    mm.close()

print("\n" + "=" * 60)
print("LECTURA de registros")
print("=" * 60)

with open(ARCHIVO, "r+b") as f:
    mm = mmap.mmap(f.fileno(), TAMAÑO_TOTAL)

    promedio_notas = 0
    for indice in range(NUM_REGISTROS):
        offset = indice * TAMAÑO_REGISTRO
        
        # Desempacar
        id_val, nota, nombre_bytes = struct.unpack_from(FORMATO, mm, offset)
        nombre = nombre_bytes.decode().rstrip('\x00')
        
        promedio_notas += nota
        print(f"  Registro {indice}: ID={id_val}, Nota={nota:6.1f}, Nombre='{nombre}'")
    
    promedio_notas /= NUM_REGISTROS
    print(f"\n  Promedio de notas: {promedio_notas:.2f}")
    
    mm.close()

print("\n" + "=" * 60)
print("MODIFICACIÓN de un registro")
print("=" * 60)

with open(ARCHIVO, "r+b") as f:
    mm = mmap.mmap(f.fileno(), TAMAÑO_TOTAL)
    
    # Modificar el registro 2 (índice 2)
    offset = 2 * TAMAÑO_REGISTRO
    
    # Leer el original
    id_val, nota_vieja, nombre_bytes = struct.unpack_from(FORMATO, mm, offset)
    nombre = nombre_bytes.decode().rstrip('\x00')
    
    print(f"\nRegistro original:")
    print(f"  ID={id_val}, Nota={nota_vieja}, Nombre='{nombre}'")
    
    # Modificar
    nota_nueva = 99.5
    struct.pack_into(FORMATO, mm, offset, id_val, nota_nueva, nombre_bytes)
    
    # Verificar
    id_val, nota_leida, _ = struct.unpack_from(FORMATO, mm, offset)
    print(f"\nRegistro modificado:")
    print(f"  ID={id_val}, Nota={nota_leida}, Nombre='{nombre}'")
    
    mm.close()

print("\n" + "=" * 60)
print("ANÁLISIS de tamaños")
print("=" * 60)

print(f"\nDetalles de cada campo en el registro:")
print(f"  'i' (int):     4 bytes - ID del estudiante")
print(f"  'f' (float):   4 bytes - Calificación (0.0 - 100.0)")
print(f"  '20s' (str):  20 bytes - Nombre (máximo)")
print(f"  ---")
print(f"  TOTAL:        28 bytes por registro")
print(f"\nObservaciónes:")
print(f"  - Los strings se rellenan con null bytes if menor que 20 bytes")
print(f"  - El acceso es O(1) sin necesidad de parsear")
print(f"  - Perfectamente alineado para lectura/escritura eficiente")

# Limpiar
os.unlink(ARCHIVO)
print(f"\nArchivo de prueba eliminado.")
