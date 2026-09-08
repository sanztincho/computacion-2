#!/usr/bin/env python3
"""
Ejercicio 4: mmap entre procesos con multiprocessing
Usa multiprocessing.Process para escribir en un archivo mmap compartido.
"""
import mmap
import struct
from multiprocessing import Process
import os
import time

print("=" * 60)
print("EJERCICIO 4: mmap con multiprocessing.Process")
print("=" * 60)

ARCHIVO = "/tmp/mmap_mp.bin"
TAMAÑO = 256
NUM_PROCESOS = 4

# Crear archivo inicial
with open(ARCHIVO, "wb") as f:
    f.write(b'\x00' * TAMAÑO)

print(f"\nArchivo compartido: {ARCHIVO}")
print(f"Tamaño: {TAMAÑO} bytes")
print(f"Procesos: {NUM_PROCESOS}")

def escribir_en_mmap(archivo, offset, proceso_id, mensaje):
    """Cada proceso abre el archivo y escribe datos."""
    with open(archivo, "r+b") as f:
        mm = mmap.mmap(f.fileno(), TAMAÑO)
        
        # Escribir ID del proceso
        struct.pack_into('i', mm, offset, proceso_id)
        
        # Escribir PID
        struct.pack_into('i', mm, offset + 4, os.getpid())
        
        # Escribir el mensaje
        encoded = mensaje.encode()
        struct.pack_into('i', mm, offset + 8, len(encoded))
        mm[offset+12:offset+12+len(encoded)] = encoded
        
        print(f"[Proceso {proceso_id}] Escribí: '{mensaje}' (PID: {os.getpid()})")
        
        mm.close()

print("\n" + "=" * 60)
print("ESCRITURA desde múltiples procesos")
print("=" * 60)

mensajes = [
    ("Hola desde proceso 0", 0),
    ("Saludos del proceso 1", 1),
    ("Proceso 2 presente", 2),
    ("Proceso 3 reportando", 3),
]

procesos = []
for proceso_id, (msg, idx) in enumerate(zip([m[0] for m in mensajes], range(NUM_PROCESOS))):
    offset = idx * 64  # 64 bytes por proceso
    p = Process(target=escribir_en_mmap, args=(ARCHIVO, offset, idx, msg))
    p.start()
    procesos.append(p)

# Esperar a que todos terminen
for p in procesos:
    p.join()

print("\nTodos los procesos terminaron.")

# Leer resultados desde el padre
print("\n" + "=" * 60)
print("LECTURA desde el proceso padre")
print("=" * 60)

with open(ARCHIVO, "r+b") as f:
    mm = mmap.mmap(f.fileno(), TAMAÑO)
    
    print("\nDatos escritos:")
    for i in range(NUM_PROCESOS):
        offset = i * 64
        proc_id = struct.unpack_from('i', mm, offset)[0]
        proc_pid = struct.unpack_from('i', mm, offset + 4)[0]
        msg_len = struct.unpack_from('i', mm, offset + 8)[0]
        
        if msg_len > 0:
            msg = bytes(mm[offset+12:offset+12+msg_len]).decode()
            print(f"  Entrada {i}: ID={proc_id}, PID={proc_pid}, Mensaje='{msg}'")
    
    mm.close()

# Limpiar
os.unlink(ARCHIVO)
print("\nArchivo de prueba eliminado.")

print("\n" + "=" * 60)
print("VARIACIÓN: Procesos escribiendo en regiones alternadas")
print("=" * 60)

ARCHIVO2 = "/tmp/mmap_mp_alternado.bin"
with open(ARCHIVO2, "wb") as f:
    f.write(b'\x00' * 512)

def escribir_en_posiciones(archivo, proceso_id, n_valores):
    """Cada proceso escribe N valores en posiciones intercaladas."""
    with open(archivo, "r+b") as f:
        mm = mmap.mmap(f.fileno(), 512)
        
        # Escribir en posiciones intercaladas
        base_offset = proceso_id * 4
        
        for i in range(n_valores):
            offset = base_offset + (i * NUM_PROCESOS * 4)
            valor = proceso_id * 1000 + i
            
            struct.pack_into('i', mm, offset, valor)
        
        print(f"[Proceso {proceso_id}] Escribí {n_valores} valores intercalados")
        mm.close()

print("\nEscrituras intercaladas:")

procesos2 = []
for i in range(NUM_PROCESOS):
    p = Process(target=escribir_en_posiciones, args=(ARCHIVO2, i, 5))
    p.start()
    procesos2.append(p)

for p in procesos2:
    p.join()

# Leer intercalados
print("\nValores intercalados escritos:")
with open(ARCHIVO2, "r+b") as f:
    mm = mmap.mmap(f.fileno(), 512)
    
    print("  Posición | Proc 0 | Proc 1 | Proc 2 | Proc 3")
    print("  " + "-" * 45)
    
    for i in range(5):
        print(f"  {i:8d}", end="")
        for j in range(NUM_PROCESOS):
            offset = j * 4 + (i * NUM_PROCESOS * 4)
            valor = struct.unpack_from('i', mm, offset)[0]
            print(f" {valor:6d}", end="")
        print()
    
    mm.close()

os.unlink(ARCHIVO2)
print("\nArchivo de prueba eliminado.")
