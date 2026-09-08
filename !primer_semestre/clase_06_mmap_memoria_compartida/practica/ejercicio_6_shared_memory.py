#!/usr/bin/env python3
"""
Ejercicio 6: SharedMemory y ShareableList
Compartir datos entre procesos con memory mapping de bajo nivel.
"""
from multiprocessing import Process, shared_memory
import struct
import time

print("=" * 60)
print("EJERCICIO 6.1: SharedMemory básico")
print("=" * 60)

def productor(shm_name, num_valores):
    """Produce valores en la memoria compartida."""
    shm = shared_memory.SharedMemory(name=shm_name)
    
    print(f"[PRODUCTOR] Escribiendo {num_valores} valores...")
    
    for i in range(num_valores):
        struct.pack_into('i', shm.buf, i * 4, i * i)
    
    # Marcar como listo (último byte)
    shm.buf[-1] = 1
    
    print(f"[PRODUCTOR] Datos escritos, marco como listo")
    shm.close()

def consumidor(shm_name, num_valores):
    """Lee valores de la memoria compartida."""
    shm = shared_memory.SharedMemory(name=shm_name)
    
    print(f"[CONSUMIDOR] Esperando datos...")
    
    # Esperar a que el productor termine (polling simple)
    attempt = 0
    while shm.buf[-1] != 1:
        time.sleep(0.01)
        attempt += 1
        if attempt % 100 == 0:
            print(f"  ... esperando ({attempt * 0.01:.2f}s)")
    
    valores = []
    for i in range(num_valores):
        val = struct.unpack_from('i', shm.buf, i * 4)[0]
        valores.append(val)
    
    print(f"[CONSUMIDOR] Datos leídos: {valores[:5]}... (mostrando primeros 5)")
    shm.close()

# Crear memoria compartida
NUM = 10
print(f"\nCreando SharedMemory con capacidad para {NUM} enteros + 1 byte de sincronización")

shm = shared_memory.SharedMemory(create=True, size=NUM * 4 + 1)
print(f"SharedMemory creado: {shm.name} (tamaño: {NUM * 4 + 1} bytes)")

p_cons = Process(target=consumidor, args=(shm.name, NUM))
p_prod = Process(target=productor, args=(shm.name, NUM))

print("\nIniciando procesos...")
p_cons.start()
time.sleep(0.1)  # Dar tiempo al consumidor para que inicie
p_prod.start()

p_prod.join()
p_cons.join()

print("\nLimpiando...")
shm.close()
shm.unlink()
print("SharedMemory destruido\n")

print("=" * 60)
print("EJERCICIO 6.2: ShareableList para datos mixtos")
print("=" * 60)

def actualizar_datos(nombre_shm):
    """Actualiza datos en la lista compartida."""
    sl = shared_memory.ShareableList(name=nombre_shm)
    
    print(f"[WORKER] Accedí a la lista compartida")
    print(f"[WORKER] Valores iniciales: {list(sl)}")
    
    # Modificar valores
    print(f"[WORKER] Modificando valores...")
    sl[0] = 42              # int
    sl[1] = 3.14159         # float
    sl[2] = "actualizado"   # str (máx largo del original)
    sl[3] = False           # bool
    
    print(f"[WORKER] Lista actualizada: {list(sl)}")
    sl.shm.close()

# Crear lista compartida con valores iniciales
print(f"\nCreando ShareableList con datos mixtos:")
sl = shared_memory.ShareableList(
    [0, 0.0, "          ", True],  # Espacios para strings
    name="mi_lista_comp"
)

print(f"Antes:   {list(sl)}")
print(f"    - sl[0] = {sl[0]} (int)")
print(f"    - sl[1] = {sl[1]} (float)")
print(f"    - sl[2] = '{sl[2]}' (str, max 10 chars)")
print(f"    - sl[3] = {sl[3]} (bool)")

p = Process(target=actualizar_datos, args=(sl.shm.name,))
p.start()
p.join()

print(f"\nDespués:  {list(sl)}")
print(f"    - sl[0] = {sl[0]} (int)")
print(f"    - sl[1] = {sl[1]:.5f} (float)")
print(f"    - sl[2] = '{sl[2]}' (str)")
print(f"    - sl[3] = {sl[3]} (bool)")

sl.shm.close()
sl.shm.unlink()

print("\n" + "=" * 60)
print("COMPARACIÓN: mmap vs SharedMemory vs Value/Array")
print("=" * 60)

print(f"""
┌─────────────────────────────────────────────────────────────┐
│                       COMPARACIÓN                           │
├─────────────────────────────────────────────────────────────┤
│ MMAP:                                                       │
│   ✓ Acceso a archivos arbitrarios en el sistema            │
│   ✓ Persistencia automática en disco                       │
│   ✓ Flexible, bajo nivel de control                        │
│   ✗ Requiere archivo en disco                              │
│                                                             │
│ SharedMemory:                                              │
│   ✓ Acceso a memoria sin archivo en disco                 │
│   ✓ Alto rendimiento, bajo nivel                          │
│   ✓ Control fino sobre sincronización                      │
│   ✗ Debe limpiarse explícitamente (unlink)               │
│   ✗ Más verboso que Value/Array                           │
│                                                             │
│ Value/Array:                                               │
│   ✓ API simple y de alto nivel                            │
│   ✓ Integración con multiprocessing                       │
│   ✓ Automático (sin unlink necesario)                     │
│   ✗ Menos flexible que SharedMemory                       │
│   ✗ Limitado a tipos básicos                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

CUÁNDO USAR CADA UNO:
  • MMAP:         Leer/escribir archivos grandes de forma eficiente
  • SharedMemory: Máximo control y compatibilidad con C/C++
  • Value/Array:  Comunicación rápida entre procesos Python
""")

print("Ejercicio 6 completado.")
