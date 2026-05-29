#!/usr/bin/env python3
"""
Ejercicio 3: mmap anónimo entre padre e hijo
Tarea: Modificar 3.2 para que cada hijo calcule la suma de un rango de números
y escriba el resultado en su región. El padre lee todos y calcula la suma total.
"""
import mmap
import os
import struct
import time

print("=" * 60)
print("EJERCICIO 3.1: Comunicación simple con fork")
print("=" * 60)

# Crear mmap anónimo
mm_3_1 = mmap.mmap(-1, 256)

pid = os.fork()

if pid == 0:
    # === HIJO ===
    print(f"[HIJO {os.getpid()}] Escribiendo datos...")

    # Escribir un entero
    struct.pack_into('i', mm_3_1, 0, 42)

    # Escribir un string
    mensaje = b"Hola desde el hijo!"
    struct.pack_into('i', mm_3_1, 4, len(mensaje))  # largo
    mm_3_1[8:8+len(mensaje)] = mensaje

    print("[HIJO] Datos escritos, terminando")
    mm_3_1.close()
    os._exit(0)

else:
    # === PADRE ===
    os.wait()
    print(f"[PADRE] Hijo terminó, leyendo datos...")

    # Leer entero
    numero = struct.unpack_from('i', mm_3_1, 0)[0]
    print(f"[PADRE] Número: {numero}")

    # Leer string
    largo = struct.unpack_from('i', mm_3_1, 4)[0]
    mensaje = bytes(mm_3_1[8:8+largo]).decode()
    print(f"[PADRE] Mensaje: {mensaje}")

    mm_3_1.close()

print("\n" + "=" * 60)
print("EJERCICIO 3.2: Múltiples hijos - Suma de rangos")
print("=" * 60)

NUM_HIJOS = 4
TAMAÑO_POR_HIJO = 128  # Aumentado para resultados
TAMAÑO_TOTAL = NUM_HIJOS * TAMAÑO_POR_HIJO

mm = mmap.mmap(-1, TAMAÑO_TOTAL)

# Definir rangos y tamaño del rango
RANGO_TOTAL = 100
RANGO_POR_HIJO = RANGO_TOTAL // NUM_HIJOS

print(f"\nConfiguración:")
print(f"  Total de hijos: {NUM_HIJOS}")
print(f"  Rango a sumar: 1 a {RANGO_TOTAL}")
print(f"  Rango por hijo: {RANGO_POR_HIJO} números")
print(f"  Tamaño mmap: {TAMAÑO_TOTAL} bytes")

hijos = []
for i in range(NUM_HIJOS):
    pid = os.fork()
    if pid == 0:
        # === HIJO ===
        offset = i * TAMAÑO_POR_HIJO
        
        # Rango a procesar: [inicio, fin)
        inicio = i * RANGO_POR_HIJO + 1
        fin = (i + 1) * RANGO_POR_HIJO + 1
        
        if i == NUM_HIJOS - 1:  # Última hijo procesa el resto
            fin = RANGO_TOTAL + 1
        
        # Calcular suma del rango
        suma = sum(range(inicio, fin))
        
        # Escribir ID del hijo
        struct.pack_into('i', mm, offset, i)
        
        # Escribir PID
        struct.pack_into('i', mm, offset + 4, os.getpid())
        
        # Escribir rango de inicio y fin
        struct.pack_into('i', mm, offset + 8, inicio)
        struct.pack_into('i', mm, offset + 12, fin - 1)
        
        # Escribir suma total
        struct.pack_into('q', mm, offset + 16, suma)
        
        # Escribir un mensaje
        msg = f"Rango {inicio}-{fin-1}: suma={suma}".encode()
        mm[offset+24:offset+24+len(msg)] = msg
        
        os._exit(0)
    else:
        hijos.append(pid)

# Padre espera a todos
for pid in hijos:
    os.waitpid(pid, 0)

# Leer resultados
print("\n" + "=" * 60)
print("RESULTADOS")
print("=" * 60)

suma_total = 0
suma_esperada = (RANGO_TOTAL * (RANGO_TOTAL + 1)) // 2

for i in range(NUM_HIJOS):
    offset = i * TAMAÑO_POR_HIJO
    hijo_id = struct.unpack_from('i', mm, offset)[0]
    hijo_pid = struct.unpack_from('i', mm, offset + 4)[0]
    inicio = struct.unpack_from('i', mm, offset + 8)[0]
    fin = struct.unpack_from('i', mm, offset + 12)[0]
    suma_parcial = struct.unpack_from('q', mm, offset + 16)[0]
    msg = bytes(mm[offset+24:offset+TAMAÑO_POR_HIJO]).split(b'\x00')[0].decode()
    
    suma_total += suma_parcial
    
    print(f"  Hijo {hijo_id} (PID {hijo_pid}): {msg}")

print(f"\n  Suma total calculada: {suma_total}")
print(f"  Suma esperada:       {suma_esperada}")
print(f"  Coincide: {'✓ SÍ' if suma_total == suma_esperada else '✗ NO'}")

mm.close()

print("\nEjercicio 3 completado.")
