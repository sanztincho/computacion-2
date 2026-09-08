#!/usr/bin/env python3
import mmap
import os

ARCHIVO_TEST = "/tmp/ejercicio1_archivo.txt"

print("=" * 60)
print("EJERCICIO 1.1: Crear y mapear un archivo")
print("=" * 60)

# Crear archivo con 5 líneas de contenido
with open(ARCHIVO_TEST, "wb") as f:
    f.write(b"Linea 1: Hola mundo\n")
    f.write(b"Linea 2: Computacion II\n")
    f.write(b"Linea 3: mmap es genial\n")
    f.write(b"Linea 4: Python es poderoso\n")
    f.write(b"Linea 5: Memoria compartida\n")

print(f"\nArchivo creado: {ARCHIVO_TEST}")
print("\nContenido inicial:")
with open(ARCHIVO_TEST, "r") as f:
    print(f.read())

# Mapear el archivo y trabajar con él
with open(ARCHIVO_TEST, "r+b") as f:
    mm = mmap.mmap(f.fileno(), 0)

    # Leer todo el contenido
    print("\n" + "=" * 60)
    print("Contenido a través de mmap:")
    print("=" * 60)
    print(mm[:].decode())

    # Leer línea por línea
    print("=" * 60)
    print("Lectura línea por línea:")
    print("=" * 60)
    mm.seek(0)
    while True:
        linea = mm.readline()
        if not linea:
            break
        print(f"  {linea.decode().strip()}")

    # Buscar texto específico
    palabra_buscar = b"es"
    pos = mm.find(palabra_buscar)
    print(f"\n Palabra '{palabra_buscar.decode()}' encontrada en posición: {pos}")

    # Buscar todas las ocurrencias
    print(f"\nTodas las ocurrencias de '{palabra_buscar.decode()}':")
    mm.seek(0)
    posiciones = []
    while True:
        linea = mm.readline()
        if not linea:
            break
        if palabra_buscar in linea:
            posiciones.append(mm.tell() - len(linea))

    for pos in posiciones:
        mm.seek(pos)
        linea = mm.readline()
        print(f"  Posición {pos}: {linea.decode().strip()}")

    # Reemplazar una palabra por otra del mismo largo
    palabra_original = b"genial"  # 6 caracteres
    palabra_nueva = b"increible"  # Tiene 9 caracteres, necesitamos 6
    palabra_nueva_ajustada = b"molon!"  # Ahora tiene 6 caracteres

    mm.seek(0)
    pos = mm.find(palabra_original)
    
    if pos != -1:
        print(f"\n" + "=" * 60)
        print(f"Reemplazando '{palabra_original.decode()}' por '{palabra_nueva_ajustada.decode()}'")
        print("=" * 60)
        mm.seek(pos)
        mm.write(palabra_nueva_ajustada)
        
        # Ver resultado
        mm.seek(0)
        print("\nContenido después de modificar:")
        print(mm[:].decode())
    
    mm.close()

print("\n" + "=" * 60)
print("EJERCICIO 1.2: mmap en modo solo lectura")
print("=" * 60)

with open(ARCHIVO_TEST, "rb") as f:
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

    # Esto funciona:
    print(f"\nContenido (primeros 40 bytes): {mm[:40]}")
    print(f"Tamaño del archivo: {mm.size()} bytes")
    print(f"Tipo de acceso: READ-ONLY")

    # Esto lanza excepción:
    try:
        mm[0:4] = b"TEST"
        print("Escritura exitosa (no debería llegar aquí)")
    except TypeError as e:
        print(f"\nIntento de escritura bloqueado ✓")
        print(f"Error esperado: {e}")

    mm.close()

print("\n" + "=" * 60)
print("Verificación con cat:")
print("=" * 60)
os.system(f"cat {ARCHIVO_TEST}")

# Limpiar
os.unlink(ARCHIVO_TEST)
print("\nArchivo de prueba eliminado.")
